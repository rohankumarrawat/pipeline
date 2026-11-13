# Pipeline Runner

A small workflow automation system. You define a **pipeline** as a set of tasks with dependencies (a directed acyclic graph), queue it for execution, and watch each task run live in the browser.

**Stack:** Django + SQLite on the backend. The frontend is plain HTML and JavaScript styled entirely with Bootstrap 5 (bundled locally in `static/vendor/`, so it works offline), with no build step.

## How to run

You need Python 3.10 or newer.

```bash
./run.sh
```

Then open http://127.0.0.1:8000.

`run.sh` creates a virtualenv, installs Django, runs the migrations, cleans up any runs that were interrupted, and starts the server.

Run the tests:

```bash
source .venv/bin/activate
python manage.py test
```

## How to use it

1. Under **New pipeline**, add your tasks, then click **Create pipeline**.
   - To see failure handling, set one task's fail chance to 100%: every task after it is skipped, while separate branches still succeed.
   - Each task has a name, a duration in seconds, a fail chance in percent, and the tasks it depends on (comma-separated names).
2. Click **Run** next to a pipeline. You'll be taken to the run page. Use **Delete** to remove a pipeline and all its runs (blocked while a run is in progress).
3. The run page updates by itself. It shows an overall progress bar, and for every task the status, start time, duration, a timeline bar, and the error if the task failed.

## How it works

```
Browser (HTML/JS, polls JSON API)
        │
Django views ── SQLite (pipelines, tasks, runs, task_runs)
        │
In-process runner: run queue → run workers → task thread pool
```

- **Models:** `Pipeline` and `Task` are the definition. `Run` and `TaskRun` record one execution and the state of each task inside it.
- **Validation** (`pipelines/validation.py`): rejects empty pipelines, duplicate task names, unknown or self dependencies, and cycles. Cycles are found with Kahn's algorithm.
- **Runner** (`pipelines/runner.py`):
  - When you trigger a run, it is put on a queue.
  - A run worker starts every task whose dependencies have all succeeded and hands it to a thread pool. Every time a task finishes, it checks what is ready next.
  - Independent tasks run at the same time. Up to 4 tasks run at once, and up to 2 runs are processed at once (configurable in `settings.py`).
- **Tasks are simulated:** each task sleeps for its duration, then fails at random according to its fail chance. Swap out `do_task_work()` to make tasks do real work.

### Failure handling

- When a task fails, its error is saved and every task downstream of it is marked **skipped**, with the reason. Branches that don't depend on the failed task keep running. The run ends as **failed**.
- Only the run's coordinator thread writes task state. The pool threads only do the work and return a result, so two threads never race on the same row.
- If the runner itself hits an unexpected error, every unfinished task is marked failed or skipped and the run is marked failed. Nothing is left stuck in `running`.
- If the server stops while runs are in progress, the next `./run.sh` marks those runs as failed with an "Interrupted" message. They are never left stuck as running.

### Live updates

The pipeline list polls every 2 seconds. The run page polls every second and stops once the run has finished.

## Tradeoffs

| Decision | Why | What I'd do with more time |
|---|---|---|
| **Polling** instead of WebSockets or SSE | Simple, works with plain Django and `runserver`, and one-second latency is fine here | Server-Sent Events or Django Channels for push updates |
| **In-process thread runner** instead of Celery/Redis | Keeps it to one process and one command, with no extra services | Celery or RQ with a real broker, so runs survive restarts and can scale to many workers |
| **In-memory queue** | Simple | Store the queue in the DB so queued runs resume after a restart (right now they're marked failed) |
| **SQLite** | Zero setup | Postgres for heavy concurrent writes |
| **Simulated tasks** | Easy to demo ordering, parallelism and failures | Real task types (shell command, HTTP call) with timeouts, retries and log capture |
| **No auth**; CSRF disabled on the JSON API | Out of scope for a local tool | Add user accounts so "my pipelines" means only your pipelines, and turn CSRF back on |
| **No editing** of pipelines | Keeps the UI small | Versioned pipelines (editing would create a new version so old runs stay accurate) |
| **No cancel or retry** buttons | Scope | Cancel a run, retry failed tasks only |
| **Dependencies typed as comma-separated names** | Simple form | Pick dependencies from a dropdown and show a visual DAG |

## Project layout

```
config/            Django settings and URLs
pipelines/
  models.py        Pipeline, Task, Run, TaskRun
  validation.py    DAG validation (cycle detection)
  runner.py        Background scheduler / executor
  views.py         Pages + JSON API
  tests.py         Tests
templates/         index.html, run.html
static/            common.js, index.js, run.js, vendor/bootstrap.min.css
run.sh             One-command start
```

## API

| Method | URL | Description |
|---|---|---|
| GET | `/api/pipelines/` | List pipelines with latest/recent run status |
| POST | `/api/pipelines/` | Create: `{"name": "...", "tasks": [{"name": "a", "duration": 1, "fail_rate": 0.1, "depends_on": []}]}` |
| POST | `/api/pipelines/<id>/run/` | Queue a new run |
| DELETE | `/api/pipelines/<id>/` | Delete a pipeline and its runs (409 if a run is in progress) |
| GET | `/api/runs/<id>/` | Run details with every task's state |
