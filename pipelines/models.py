from django.db import models


class Pipeline(models.Model):
    """A pipeline definition (the template). Running it creates a Run."""

    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Task(models.Model):
    """One step in a pipeline.

    Tasks are simulated: they sleep for `duration` seconds and then fail
    with probability `fail_rate` (0.0 - 1.0).
    """

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="tasks")
    name = models.CharField(max_length=200)
    duration = models.FloatField(default=1.0)
    fail_rate = models.FloatField(default=0.0)
    depends_on = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="dependents")

    class Meta:
        unique_together = [("pipeline", "name")]

    def __str__(self):
        return self.name


class Run(models.Model):
    """One execution of a pipeline."""

    QUEUED, RUNNING, SUCCESS, FAILED = "queued", "running", "success", "failed"
    STATUSES = [(s, s) for s in (QUEUED, RUNNING, SUCCESS, FAILED)]

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=20, choices=STATUSES, default=QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)


class TaskRun(models.Model):
    """The state of one task inside one run."""

    PENDING, RUNNING, SUCCESS, FAILED, SKIPPED = "pending", "running", "success", "failed", "skipped"
    STATUSES = [(s, s) for s in (PENDING, RUNNING, SUCCESS, FAILED, SKIPPED)]
    FINISHED = (SUCCESS, FAILED, SKIPPED)

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="task_runs")
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUSES, default=PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    @property
    def duration(self):
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 2)
        return None
