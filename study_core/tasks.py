"""
Celery tasks for the daily gamified quiz system.

The beat schedule in mysite/settings.py fires generate_daily_quiz_task at
00:00 IST every night, pre-generating the 5 Current Affairs + 15 tiered GK
questions before users wake up.
"""

from celery import shared_task
from django.utils import timezone

from study_core.models import DailyQuiz
from study_core.services.daily_quiz_service import ensure_daily_quiz_for_date


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_daily_quiz_task(self):
    """
    Generate (or fetch, if already present) today's Daily Quiz.

    Idempotent: safe to run at 00:00 IST and to re-trigger manually later —
    if a quiz already exists for today it is left untouched.
    """
    today = timezone.localdate()

    existing = DailyQuiz.objects.filter(date=today).first()
    if existing is not None:
        return {
            'status': 'skipped',
            'date': str(today),
            'reason': 'quiz already exists',
            'quiz_id': str(existing.id),
            'question_count': existing.questions.count(),
        }

    try:
        quiz = ensure_daily_quiz_for_date(today)
    except Exception as exc:
        # Transient Gemini/network failures: retry a few times with backoff.
        raise self.retry(exc=exc)

    return {
        'status': 'created',
        'date': str(today),
        'quiz_id': str(quiz.id),
        'question_count': quiz.questions.count(),
    }
