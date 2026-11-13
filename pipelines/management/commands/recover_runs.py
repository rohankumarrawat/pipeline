from django.core.management.base import BaseCommand

from pipelines.runner import recover_interrupted_runs


class Command(BaseCommand):
    help = "Mark runs left queued/running by a previous shutdown as failed."

    def handle(self, *args, **options):
        recover_interrupted_runs()
        self.stdout.write("Recovered interrupted runs (if any).")
