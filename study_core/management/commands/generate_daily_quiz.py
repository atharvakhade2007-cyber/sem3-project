"""
Management command to generate today's Daily GK Quiz (5 Current Affairs + 15 tiered GK).

Usage:
    python manage.py generate_daily_quiz
    python manage.py generate_daily_quiz --date 2026-09-02
"""

from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from study_core.models import DailyQuiz
from study_core.services.daily_quiz_service import create_daily_quiz_for_date


class Command(BaseCommand):
    help = 'Generate the Daily GK & Current Affairs Quiz for a given date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Date to generate quiz for (YYYY-MM-DD). Default: today.',
        )

    def handle(self, *args, **options):
        # "Today" follows the app's IST day boundary (not the server's
        # system clock), matching the 00:00 IST Celery cron.
        target_date = timezone.localdate()
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD.')

        # Check if quiz already exists
        if DailyQuiz.objects.filter(date=target_date).exists():
            self.stdout.write(
                self.style.WARNING(f'Quiz for {target_date} already exists. Skipping.')
            )
            return

        self.stdout.write(f'Generating Daily GK Quiz for {target_date}...')

        try:
            quiz = create_daily_quiz_for_date(target_date=target_date)
        except Exception as e:
            raise CommandError(f'Failed to generate questions: {e}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created quiz for {target_date} '
                f'with {quiz.questions.count()} questions.'
            )
        )
