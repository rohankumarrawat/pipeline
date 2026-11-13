# Pipeline

A small workflow runner I built with Django. You create a pipeline out of tasks, say which tasks depend on which, hit Run, and watch them execute live. Tasks that don't depend on each other run in parallel, and if something fails, everything after it gets skipped instead of running on bad input.

**Live demo:** http://pipeline.rohankumarrawat.com

Backend is Django + SQLite. Frontend is plain HTML/JS with Bootstrap 5 (the CSS file is kept in `static/vendor/` so it works offline). No build step, no Node.

## Running it locally

You'll need Python 3.10+.

```bash
./run.sh
```

Then go to http://127.0.0.1:8000

The script sets up a virtualenv, installs Django, runs migrations and starts the server. That's it.

To run the tests:

```bash
source .venv/bin/activate
python manage.py test
```

## Using it

1. Fill in a pipeline name and add some tasks. Each task has a name, a duration (seconds), a fail chance (%), and a comma-separated list of tasks it depends on.
2. Click **Create pipeline**, then **Run** on it in the list.
3. You'll land on the run page, which updates on its own. You can see each task's status, when it started, how long it took, and the error if it failed.

Want to see a failure? Set one task's fail chance to 100. Anything that depends on it gets skipped, but other branches still finish.

You can delete a pipeline from the list too (not while it's running though).

## How it works

```
Browser (polls the JSON API)
        |
Django views --- SQLite
        |
Background runner: run queue -> run workers -> task thread pool
```

- `models.py` has four models. `Pipeline` and `Task` are the definition, `Run` and `TaskRun` store one execution and the state of each task in it.
- `validation.py` checks the pipeline before saving it: no empty pipelines, no duplicate names, no unknown deps, no cycles. Cycle check is Kahn's algorithm.
- `runner.py` does the actual scheduling. When a run starts, every task with no pending dependencies gets sent to a thread pool. Each time one finishes, it checks what's ready next. Up to 4 tasks run at a time and 2 runs at a time (you can change both in `settings.py`).
- Tasks are fake for now: they sleep for their duration and then fail randomly based on the fail chance. Replace `do_task_work()` if you want them to do real work.

### When things go wrong

- A failed task saves its error, and every task downstream is marked skipped with the reason. The run ends as failed.
- Only one thread (the run's coordinator) writes task state to the DB. Worker threads just do the work and hand back a result, so there are no race conditions on the same row.
- If the runner itself crashes mid-run, all unfinished tasks get marked failed/skipped so nothing is stuck on "running".
- If the server is stopped during a run, the next `./run.sh` marks that run as interrupted.

### Live updates

The pipeline list refreshes every 2 seconds, and the run page every second until the run finishes.

## Project structure

```
config/            settings and urls
pipelines/
  models.py
  validation.py    cycle detection etc.
  runner.py        background scheduler
  views.py         pages + JSON API
  tests.py
templates/         index.html, run.html
static/            JS files + bootstrap
run.sh             starts everything
```

## API

| Method | URL | What it does |
|---|---|---|
| GET | `/api/pipelines/` | List pipelines with their latest runs |
| POST | `/api/pipelines/` | Create a pipeline |
| DELETE | `/api/pipelines/<id>/` | Delete a pipeline and its runs |
| POST | `/api/pipelines/<id>/run/` | Start a new run |
| GET | `/api/runs/<id>/` | Get a run with every task's status |

Example body for creating a pipeline:

```json
{
  "name": "build",
  "tasks": [
    {"name": "checkout", "duration": 1, "fail_rate": 0, "depends_on": []},
    {"name": "test", "duration": 3, "fail_rate": 0.2, "depends_on": ["checkout"]}
  ]
}
```

---

Made by Rohan · [rohankumarrawat.com](https://rohankumarrawat.com)
