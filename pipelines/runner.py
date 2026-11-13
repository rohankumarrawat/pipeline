"""Runs pipelines in the background.

How it works:
- `enqueue(run_id)` puts a run on an in-memory queue.
- A few "run worker" threads take runs off the queue and call `execute_run`.
- `execute_run` starts every task whose dependencies have all succeeded,
  hands it to a shared thread pool, and waits. When a task finishes it
  checks again what is now ready. Independent tasks run at the same time.
- If a task fails, every task that depends on it (directly or indirectly)
  is marked "skipped". Tasks in other branches keep running.

Only the run's coordinator thread writes to the database. The pool threads
just do the work and return a result, so there are no races on task state.
"""

import queue
import random
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import Run, TaskRun

_run_queue = queue.Queue()
_task_pool = None
_started = False
_start_lock = threading.Lock()


def do_task_work(duration, fail_rate):
    """The 'work' a task does. Simulated: sleep, then maybe fail."""
    time.sleep(duration)
    if random.random() < fail_rate:
        raise RuntimeError(f"Simulated failure (fail rate {int(fail_rate * 100)}%)")


def enqueue(run_id):
    _ensure_started()
    _run_queue.put(run_id)


def _ensure_started():
    global _task_pool, _started
    with _start_lock:
        if _started:
            return
        _task_pool = ThreadPoolExecutor(max_workers=settings.TASK_WORKERS, thread_name_prefix="task")
        for i in range(settings.RUN_WORKERS):
            threading.Thread(target=_run_worker_loop, name=f"run-worker-{i}", daemon=True).start()
        _started = True


def _run_worker_loop():
    while True:
        run_id = _run_queue.get()
        try:
            execute_run(run_id)
        finally:
            close_old_connections()


def execute_run(run_id, pool=None):
    """Execute one run to completion. Safe to call directly (used by tests)."""
    pool = pool or _task_pool
    run = Run.objects.get(id=run_id)
    run.status = Run.RUNNING
    run.started_at = timezone.now()
    run.save()

    try:
        _schedule(run, pool)
    except Exception as e:  # unexpected bug: never leave the run half-finished
        _fail_everything_left(run, f"Runner error: {e}")
        run.error = f"Runner error: {e}"

    statuses = set(run.task_runs.values_list("status", flat=True))
    run.status = Run.FAILED if statuses & {TaskRun.FAILED, TaskRun.SKIPPED} else Run.SUCCESS
    run.finished_at = timezone.now()
    run.save()


def _schedule(run, pool):
    task_runs = {tr.task_id: tr for tr in run.task_runs.select_related("task")}
    deps = {tr.task_id: set(tr.task.depends_on.values_list("id", flat=True)) for tr in task_runs.values()}
    in_flight = {}  # future -> TaskRun

    while True:
        _skip_blocked(task_runs, deps)

        # Start every pending task whose dependencies all succeeded.
        for task_id, tr in task_runs.items():
            if tr.status != TaskRun.PENDING:
                continue
            if all(task_runs[d].status == TaskRun.SUCCESS for d in deps[task_id]):
                tr.status = TaskRun.RUNNING
                tr.started_at = timezone.now()
                tr.save()
                future = pool.submit(do_task_work, tr.task.duration, tr.task.fail_rate)
                in_flight[future] = tr

        if not in_flight:
            break  # nothing running and nothing can start -> done

        done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
        for future in done:
            tr = in_flight.pop(future)
            try:
                future.result()
                tr.status = TaskRun.SUCCESS
            except Exception as e:
                tr.status = TaskRun.FAILED
                tr.error = str(e) or e.__class__.__name__
            tr.finished_at = timezone.now()
            tr.save()


def _skip_blocked(task_runs, deps):
    """Mark pending tasks as skipped if any dependency failed or was skipped.
    Loops until nothing changes so skips flow down the whole chain."""
    changed = True
    while changed:
        changed = False
        for task_id, tr in task_runs.items():
            if tr.status != TaskRun.PENDING:
                continue
            bad = [task_runs[d] for d in deps[task_id] if task_runs[d].status in (TaskRun.FAILED, TaskRun.SKIPPED)]
            if bad:
                tr.status = TaskRun.SKIPPED
                tr.error = f"Skipped because '{bad[0].task.name}' {bad[0].status}"
                tr.finished_at = timezone.now()
                tr.save()
                changed = True


def _fail_everything_left(run, reason):
    now = timezone.now()
    run.task_runs.filter(status=TaskRun.RUNNING).update(status=TaskRun.FAILED, error=reason, finished_at=now)
    run.task_runs.filter(status=TaskRun.PENDING).update(status=TaskRun.SKIPPED, error=reason, finished_at=now)


def recover_interrupted_runs():
    """Called on server start. Runs that were queued/running when the server
    stopped can't continue (the queue was in memory), so mark them failed
    clearly instead of leaving them stuck forever."""
    reason = "Interrupted: server restarted while this run was in progress"
    for run in Run.objects.filter(status__in=[Run.QUEUED, Run.RUNNING]):
        _fail_everything_left(run, reason)
        run.status = Run.FAILED
        run.error = reason
        run.finished_at = timezone.now()
        run.save()
