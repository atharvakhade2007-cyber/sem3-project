"""
Celery application for the mysite project.

Run the worker (processes queued tasks):
    celery -A mysite worker -l info

Run the beat scheduler (fires the 00:00 IST daily quiz cron):
    celery -A mysite beat -l info

Start both in one process during development:
    celery -A mysite worker --beat -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

app = Celery("mysite")

# Read config (CELERY_BROKER_URL, CELERY_BEAT_SCHEDULE, ...) from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Pick up @shared_task definitions from installed apps (e.g. study_core.tasks).
app.autodiscover_tasks()
