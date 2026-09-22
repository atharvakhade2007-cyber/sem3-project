"""Daily GK Quiz views (today / check / submit / leaderboard)."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    DailyQuiz,
    DailyQuestion,
    DailyQuizAnswer,
    DailyQuizSession,
    UserProfile,
)
from ..services.daily_quiz_service import (
    ensure_daily_quiz_for_date,
    served_questions_for_user,
    select_gk_tier,
    apply_quiz_completion,
    record_daily_quiz_answer,
    recorded_answers_for_user,
    QuizAnswerConflict,
)
from .common import _get_user, _get_or_create_profile


def _ensure_today_quiz():
    """
    Return today's quiz, auto-generating it on demand if the 00:00 IST Celery
    task hasn't run yet (lazy fallback keeps the feature working workerless).
    """
    return ensure_daily_quiz_for_date(timezone.localdate())


class DailyQuizTodayView(APIView):
    """
    GET /api/v2/daily-quiz/today/

    Returns today's quiz adapted to the requesting user's profile:
    5 universally-identical Current Affairs questions + the 5 GK questions
    matching their IRT-selected tier (θ from Elo, target 70% success).
    Includes streak stats and the mini leaderboard.
    Does NOT expose correct_index or explanation.
    """

    def get(self, request):
        try:
            quiz = _ensure_today_quiz()
        except Exception as e:
            return Response(
                {'error': f'Failed to generate today\'s quiz: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        user = _get_user(request)
        profile = _get_or_create_profile(user)

        # Check if user already completed today's quiz
        existing_session = DailyQuizSession.objects.filter(
            user=user, quiz=quiz
        ).first()

        # Serve 5 universal CA + 5 IRT-tier-matched GK (sanitized — no
        # answers). served_questions_for_user picks the tier from the user's
        # Elo (θ) and syncs profile.gk_skill_tier to the chosen tier.
        served = served_questions_for_user(quiz, profile)
        tier = profile.gk_skill_tier
        sanitized = [
            {
                'id': str(q.id),
                'order': q.order,
                'category': q.category,
                'difficulty_tier': q.difficulty_tier,
                'question_text': q.question_text,
                'options': q.options,
            }
            for q in served
        ]

        # Top 3 leaderboard
        top3 = DailyQuizSession.objects.filter(
            quiz=quiz
        ).select_related('user').order_by('-score', 'total_time_sec')[:3]

        leaderboard_top3 = [
            {
                'rank': i + 1,
                'username': s.user.username,
                'score': s.score,
                'time_sec': s.total_time_sec,
            }
            for i, s in enumerate(top3)
        ]

        result = {
            'quiz_id': str(quiz.id),
            'date': quiz.date.isoformat(),
            'title': quiz.title,
            'total_questions': len(sanitized),
            'questions': sanitized,
            'leaderboard_top3': leaderboard_top3,
            # ── Gamification state ──
            'gk_skill_tier': tier,
            'current_streak': profile.current_streak,
            'longest_streak': profile.longest_streak,
        }

        if existing_session:
            result['user_completed'] = True
            result['user_score'] = existing_session.score
            result['user_time_sec'] = existing_session.total_time_sec
            result['user_rank'] = DailyQuizSession.objects.filter(
                quiz=quiz, score__gt=existing_session.score
            ).count() + 1
            result['user_answers'] = existing_session.answers
            # Full review (only exposed to the user who already completed).
            answers_by_id = {
                str(a.get('question_id')): a for a in existing_session.answers
            }
            review = []
            for q in served:
                a = answers_by_id.get(str(q.id))
                if a is None:
                    continue
                review.append({
                    'question_id': str(q.id),
                    'question_text': q.question_text,
                    'options': q.options,
                    'correct_index': q.correct_index,
                    'selected_index': a.get('selected_index'),
                    'is_correct': a.get('is_correct'),
                    'category': q.category,
                    'difficulty_tier': q.difficulty_tier,
                    'explanation': q.explanation,
                })
            result['user_review'] = review
        else:
            result['user_completed'] = False
            # Resume support: answers already locked in this run (page refresh
            # mid-quiz) — each entry carries the revealed outcome so the client
            # can restore reviewed state without re-asking.
            result['checked_answers'] = [
                {
                    'question_id': str(a.question_id),
                    'selected_index': a.selected_index,
                    'is_correct': a.is_correct,
                    'correct_index': a.question.correct_index,
                    'explanation': a.question.explanation,
                    'category': a.question.category,
                    'difficulty_tier': a.question.difficulty_tier,
                }
                for a in recorded_answers_for_user(quiz, user)
            ]

        return Response(result)


class DailyQuizCheckView(APIView):
    """
    POST /api/v2/daily-quiz/check/

    Grades and LOCKS a single answer during a daily-quiz run. Returns the
    outcome (is_correct + correct_index + explanation) immediately so the UI
    can show per-question review before advancing. Because the server records
    the answer in the same request, the user cannot see the correct answer and
    then change their selection — each question has exactly one attempt.
    Body: { question_id: str, selected_index: int(0-3) }
    """

    def post(self, request):
        user = _get_user(request)
        profile = _get_or_create_profile(user)

        try:
            quiz = _ensure_today_quiz()
        except Exception as e:
            return Response(
                {'error': f'Failed to load quiz: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if DailyQuizSession.objects.filter(user=user, quiz=quiz).exists():
            return Response(
                {'error': 'You have already completed today\'s quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_id = str(request.data.get('question_id', '')).strip()
        try:
            selected_index = int(request.data.get('selected_index', -1))
        except (TypeError, ValueError):
            selected_index = -1

        if not question_id or selected_index not in {0, 1, 2, 3}:
            return Response(
                {'error': 'question_id and selected_index (0-3) are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only questions actually served to this user can be answered (5
        # universal CA + the 5 GK questions matching their IRT-chosen tier).
        served = served_questions_for_user(quiz, profile)
        question = next(
            (q for q in served if str(q.id) == question_id), None
        )
        if question is None:
            return Response(
                {'error': 'Question is not part of today\'s quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            answer = record_daily_quiz_answer(
                quiz, user, question, selected_index
            )
        except QuizAnswerConflict as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'question_id': question_id,
            'selected_index': answer.selected_index,
            'is_correct': answer.is_correct,
            'correct_index': question.correct_index,
            'explanation': question.explanation,
            'category': question.category,
            'difficulty_tier': question.difficulty_tier,
        }, status=status.HTTP_201_CREATED)


class DailyQuizSubmitView(APIView):
    """
    POST /api/v2/daily-quiz/submit/

    Grades the run exclusively from the answers locked via /daily-quiz/check/
    (the submitted payload carries no authority and is ignored), computes the
    score, updates the daily streak and the adaptive GK skill tier, and writes
    the attempt record.
    Body: { answers: [...], total_time_sec: float }  (answers are not trusted)
    """

    def post(self, request):
        user = _get_user(request)
        profile = _get_or_create_profile(user)

        try:
            quiz = _ensure_today_quiz()
        except Exception as e:
            return Response(
                {'error': f'Failed to load quiz: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Prevent multiple submissions
        if DailyQuizSession.objects.filter(user=user, quiz=quiz).exists():
            return Response(
                {'error': 'You have already completed today\'s quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            total_time_sec = float(request.data.get('total_time_sec', 0) or 0)
        except (TypeError, ValueError):
            total_time_sec = 0.0

        # Grade ONLY the user's served questions (5 universal CA + their 5 GK),
        # so users on different difficulty tiers can't answer out-of-tier items.
        # served_questions_for_user picks the tier from Elo via the IRT engine.
        served = served_questions_for_user(quiz, profile)
        questions = {str(q.id): q for q in served}

        score = 0
        gk_correct = 0
        processed_answers = []
        gk_answers = []  # (tier, is_correct) per answered GK question → Elo nudge

        # Answers were locked one-by-one via /daily-quiz/check/, so grading
        # uses only the recorded rows. Locked rows make the run immutable —
        # nothing can be changed after the correct answer was revealed.
        for answer in recorded_answers_for_user(quiz, user):
            q = answer.question
            if str(q.id) not in questions:
                continue  # tier/category drift guard
            is_correct = answer.is_correct
            if is_correct:
                score += 1
                if q.category == DailyQuestion.Category.GK:
                    gk_correct += 1

            processed_answers.append({
                'question_id': str(q.id),
                'selected_index': answer.selected_index,
                'is_correct': is_correct,
            })

            if q.category == DailyQuestion.Category.GK:
                gk_answers.append((q.difficulty_tier, is_correct))

        today = timezone.localdate()

        # Save session + update streak/tier atomically (unique user+quiz row
        # guards against double-submit races).
        try:
            with transaction.atomic():
                session = DailyQuizSession.objects.create(
                    user=user,
                    quiz=quiz,
                    score=score,
                    total_time_sec=total_time_sec,
                    answers=processed_answers,
                )
                apply_quiz_completion(profile, gk_answers, today)
                # Re-derive the tier from the updated Elo so the response (and
                # the profile badge) reflect the new adaptive state immediately.
                profile.gk_skill_tier = select_gk_tier(profile)
                profile.save()
        except IntegrityError:
            return Response(
                {'error': 'You have already completed today\'s quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build review with explanations
        review = []
        for ans in processed_answers:
            q = questions.get(ans['question_id'])
            if q:
                review.append({
                    'question_id': str(q.id),
                    'question_text': q.question_text,
                    'options': q.options,
                    'correct_index': q.correct_index,
                    'selected_index': ans['selected_index'],
                    'is_correct': ans['is_correct'],
                    'category': q.category,
                    'difficulty_tier': q.difficulty_tier,
                    'explanation': q.explanation,
                })

        # Calculate rank
        rank = DailyQuizSession.objects.filter(
            quiz=quiz, score__gt=score
        ).count() + 1

        return Response({
            'score': score,
            'total_questions': len(served),
            'total_time_sec': total_time_sec,
            'rank': rank,
            'gk_correct': gk_correct,
            'review': review,
            # ── Updated gamification state ──
            'current_streak': profile.current_streak,
            'longest_streak': profile.longest_streak,
            'gk_skill_tier': profile.gk_skill_tier,
        }, status=status.HTTP_201_CREATED)


class DailyQuizLeaderboardView(APIView):
    """
    GET /api/v2/daily-quiz/leaderboard/?tab=score&limit=10

    Daily rankings sorted by score DESC, then time_taken ASC (fastest wins
    ties), limited to the top-N for rapid client rendering.

    Query params:
    - tab: 'score' (default, today's quiz scores) | 'streak' (current streak ranking)
    - limit: top-N count (default 10, max 100)
    """

    def get(self, request):
        today = timezone.localdate()
        tab = request.query_params.get('tab', 'score')

        try:
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 100))

        # ── Tab: current streaks across all users ──
        if tab == 'streak':
            profiles = (
                UserProfile.objects.select_related('user')
                .filter(current_streak__gt=0)
                .order_by('-current_streak', '-longest_streak')[:limit]
            )
            leaderboard = [
                {
                    'rank': i + 1,
                    'username': p.user.username,
                    'current_streak': p.current_streak,
                    'longest_streak': p.longest_streak,
                    'gk_skill_tier': p.gk_skill_tier,
                }
                for i, p in enumerate(profiles)
            ]
            return Response({
                'type': 'streak',
                'leaderboard': leaderboard,
            })

        # ── Default tab: today's score leaderboard ──
        try:
            quiz = DailyQuiz.objects.get(date=today)
        except DailyQuiz.DoesNotExist:
            return Response({
                'type': 'score',
                'quiz_date': today.isoformat(),
                'leaderboard': [],
                'message': 'No quiz available for today yet.',
            })

        sessions = DailyQuizSession.objects.filter(
            quiz=quiz
        ).select_related('user').order_by('-score', 'total_time_sec')[:limit]

        leaderboard = [
            {
                'rank': i + 1,
                'username': s.user.username,
                'score': s.score,
                'total_time_sec': s.total_time_sec,
                'time_sec': s.total_time_sec,
                'completed_at': s.completed_at.isoformat(),
            }
            for i, s in enumerate(sessions)
        ]

        return Response({
            'type': 'score',
            'quiz_date': today.isoformat(),
            'leaderboard': leaderboard,
        })
