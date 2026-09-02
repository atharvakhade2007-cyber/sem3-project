"""
Management command to generate today's Daily GK Quiz.

Usage:
    python manage.py generate_daily_quiz
    python manage.py generate_daily_quiz --date 2026-09-02
"""

from datetime import date, datetime
from django.core.management.base import BaseCommand, CommandError

from study_core.models import DailyQuiz, DailyQuestion
from study_core.services.daily_quiz_service import generate_daily_gk_questions


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
        target_date = date.today()
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
            questions_data = generate_daily_gk_questions(target_date=target_date)
        except Exception as e:
            raise CommandError(f'Failed to generate questions: {e}')

        # Create quiz and questions in a transaction
        from django.db import transaction

        with transaction.atomic():
            quiz = DailyQuiz.objects.create(
                date=target_date,
                title=f'Daily GK & Current Affairs — {target_date.strftime("%B %d, %Y")}',
            )

            question_objects = []
            for i, q_data in enumerate(questions_data):
                question_objects.append(
                    DailyQuestion(
                        quiz=quiz,
                        question_text=q_data['question_text'],
                        options=q_data['options'],
                        correct_index=q_data['correct_index'],
                        explanation=q_data.get('explanation', ''),
                        order=i + 1,
                    )
                )

            DailyQuestion.objects.bulk_create(question_objects)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created quiz for {target_date} '
                f'with {len(question_objects)} questions.'
            )
        )
