import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import runner
from .models import Pipeline, Run, Task, TaskRun
from .validation import ValidationError, validate_pipeline


def _iso(dt):
    return dt.isoformat() if dt else None


def _run_summary(run):
    if not run:
        return None
    return {
        "id": run.id,
        "status": run.status,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


# ---------- pages ----------

def index_page(request):
    return render(request, "index.html")


def run_page(request, run_id):
    get_object_or_404(Run, id=run_id)
    return render(request, "run.html", {"run_id": run_id})


# ---------- API ----------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def pipelines_api(request):
    if request.method == "GET":
        data = []
        for p in Pipeline.objects.prefetch_related("tasks").order_by("-created_at"):
            runs = list(p.runs.order_by("-created_at")[:5])
            data.append({
                "id": p.id,
                "name": p.name,
                "task_count": len(p.tasks.all()),
                "latest_run": _run_summary(runs[0] if runs else None),
                "recent_runs": [_run_summary(r) for r in runs],
            })
        return JsonResponse({"pipelines": data})

    # POST: create a pipeline
    try:
        body = json.loads(request.body or "{}")
        clean = validate_pipeline(body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    with transaction.atomic():
        pipeline = Pipeline.objects.create(name=clean["name"])
        by_name = {}
        for t in clean["tasks"]:
            by_name[t["name"]] = Task.objects.create(
                pipeline=pipeline, name=t["name"], duration=t["duration"], fail_rate=t["fail_rate"]
            )
        for t in clean["tasks"]:
            by_name[t["name"]].depends_on.set([by_name[d] for d in t["depends_on"]])

    return JsonResponse({"id": pipeline.id}, status=201)


@csrf_exempt
@require_POST
def trigger_run_api(request, pipeline_id):
    pipeline = get_object_or_404(Pipeline, id=pipeline_id)
    with transaction.atomic():
        run = Run.objects.create(pipeline=pipeline)
        TaskRun.objects.bulk_create([TaskRun(run=run, task=t) for t in pipeline.tasks.all()])
    # The atomic block has committed, so the worker will see all rows.
    runner.enqueue(run.id)
    return JsonResponse({"id": run.id, "status": run.status}, status=201)


@require_GET
def run_detail_api(request, run_id):
    run = get_object_or_404(Run.objects.select_related("pipeline"), id=run_id)
    tasks = []
    for tr in run.task_runs.select_related("task").prefetch_related("task__depends_on").order_by("task__id"):
        tasks.append({
            "name": tr.task.name,
            "status": tr.status,
            "depends_on": [d.name for d in tr.task.depends_on.all()],
            "started_at": _iso(tr.started_at),
            "finished_at": _iso(tr.finished_at),
            "duration": tr.duration,
            "error": tr.error,
        })
    data = _run_summary(run)
    data.update({"pipeline": {"id": run.pipeline.id, "name": run.pipeline.name}, "error": run.error, "tasks": tasks})
    return JsonResponse(data)
