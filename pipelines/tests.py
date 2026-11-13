import json
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.test import TestCase

from .models import Run, TaskRun
from .runner import execute_run
from .validation import ValidationError, validate_pipeline


def make_pipeline(client, tasks, name="test"):
    res = client.post("/api/pipelines/", json.dumps({"name": name, "tasks": tasks}), content_type="application/json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


def make_run(client, pipeline_id):
    """Create a run without starting the background worker."""
    with mock.patch("pipelines.views.runner.enqueue"):
        return client.post(f"/api/pipelines/{pipeline_id}/run/").json()["id"]


def statuses(run_id):
    return {tr.task.name: tr.status for tr in TaskRun.objects.filter(run_id=run_id).select_related("task")}


class ValidationTests(TestCase):
    def test_valid(self):
        validate_pipeline({"name": "p", "tasks": [{"name": "a"}, {"name": "b", "depends_on": ["a"]}]})

    def test_cycle(self):
        with self.assertRaisesRegex(ValidationError, "cycle"):
            validate_pipeline({"name": "p", "tasks": [
                {"name": "a", "depends_on": ["c"]},
                {"name": "b", "depends_on": ["a"]},
                {"name": "c", "depends_on": ["b"]},
            ]})

    def test_unknown_dependency(self):
        with self.assertRaisesRegex(ValidationError, "unknown"):
            validate_pipeline({"name": "p", "tasks": [{"name": "a", "depends_on": ["x"]}]})

    def test_duplicate_and_self(self):
        with self.assertRaises(ValidationError):
            validate_pipeline({"name": "p", "tasks": [{"name": "a"}, {"name": "a"}]})
        with self.assertRaises(ValidationError):
            validate_pipeline({"name": "p", "tasks": [{"name": "a", "depends_on": ["a"]}]})

    def test_api_rejects_bad_pipeline(self):
        res = self.client.post("/api/pipelines/", json.dumps({"name": "", "tasks": []}), content_type="application/json")
        self.assertEqual(res.status_code, 400)


class RunnerTests(TestCase):
    def setUp(self):
        self.pool = ThreadPoolExecutor(max_workers=4)

    def tearDown(self):
        self.pool.shutdown()

    def test_diamond_runs_in_order_and_in_parallel(self):
        #   a -> b, c -> d
        pid = make_pipeline(self.client, [
            {"name": "a", "duration": 0.1},
            {"name": "b", "duration": 0.3, "depends_on": ["a"]},
            {"name": "c", "duration": 0.3, "depends_on": ["a"]},
            {"name": "d", "duration": 0.1, "depends_on": ["b", "c"]},
        ])
        run_id = make_run(self.client, pid)
        execute_run(run_id, pool=self.pool)

        self.assertEqual(Run.objects.get(id=run_id).status, Run.SUCCESS)
        trs = {tr.task.name: tr for tr in TaskRun.objects.filter(run_id=run_id).select_related("task")}
        # b and c start only after a finished
        self.assertGreaterEqual(trs["b"].started_at, trs["a"].finished_at)
        self.assertGreaterEqual(trs["c"].started_at, trs["a"].finished_at)
        # b and c overlapped (ran in parallel)
        self.assertLess(trs["c"].started_at, trs["b"].finished_at)
        self.assertLess(trs["b"].started_at, trs["c"].finished_at)
        # d waited for both
        self.assertGreaterEqual(trs["d"].started_at, max(trs["b"].finished_at, trs["c"].finished_at))

    def test_failure_skips_dependents_but_not_other_branches(self):
        pid = make_pipeline(self.client, [
            {"name": "a", "duration": 0},
            {"name": "bad", "duration": 0, "fail_rate": 1, "depends_on": ["a"]},
            {"name": "after-bad", "duration": 0, "depends_on": ["bad"]},
            {"name": "after-after", "duration": 0, "depends_on": ["after-bad"]},
            {"name": "other", "duration": 0.1, "depends_on": ["a"]},
        ])
        run_id = make_run(self.client, pid)
        execute_run(run_id, pool=self.pool)

        self.assertEqual(statuses(run_id), {
            "a": "success",
            "bad": "failed",
            "after-bad": "skipped",
            "after-after": "skipped",
            "other": "success",
        })
        run = Run.objects.get(id=run_id)
        self.assertEqual(run.status, Run.FAILED)
        self.assertIsNotNone(run.finished_at)
        self.assertIn("Simulated failure", TaskRun.objects.get(run_id=run_id, task__name="bad").error)

    def test_unexpected_runner_error_leaves_clean_state(self):
        pid = make_pipeline(self.client, [{"name": "a", "duration": 0}, {"name": "b", "depends_on": ["a"]}])
        run_id = make_run(self.client, pid)
        with mock.patch("pipelines.runner._schedule", side_effect=RuntimeError("boom")):
            execute_run(run_id, pool=self.pool)

        run = Run.objects.get(id=run_id)
        self.assertEqual(run.status, Run.FAILED)
        self.assertIn("boom", run.error)
        for s in statuses(run_id).values():
            self.assertIn(s, TaskRun.FINISHED)  # nothing stuck in pending/running

    def test_recover_interrupted_runs(self):
        from .runner import recover_interrupted_runs

        pid = make_pipeline(self.client, [{"name": "a"}])
        run_id = make_run(self.client, pid)
        TaskRun.objects.filter(run_id=run_id).update(status=TaskRun.RUNNING)
        Run.objects.filter(id=run_id).update(status=Run.RUNNING)

        recover_interrupted_runs()
        self.assertEqual(Run.objects.get(id=run_id).status, Run.FAILED)
        self.assertEqual(statuses(run_id), {"a": "failed"})


class DeleteTests(TestCase):
    def test_delete_pipeline_removes_runs(self):
        pid = make_pipeline(self.client, [{"name": "a"}])
        run_id = make_run(self.client, pid)
        Run.objects.filter(id=run_id).update(status=Run.SUCCESS)
        res = self.client.delete(f"/api/pipelines/{pid}/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Run.objects.filter(id=run_id).exists())

    def test_cannot_delete_while_running(self):
        pid = make_pipeline(self.client, [{"name": "a"}])
        make_run(self.client, pid)  # stays "queued"
        res = self.client.delete(f"/api/pipelines/{pid}/")
        self.assertEqual(res.status_code, 409)
