from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    UserProfile, Document, Flashcard, Question,
    SharedChallenge, TestSession, SessionResponse,
)
from .serializers import (
    DocumentSerializer, DocumentDetailSerializer,
    FlashcardSerializer, QuestionBriefSerializer,
    SharedChallengeSerializer, TestSessionSerializer,
    SessionResponseSerializer, SummaryResponseSerializer,
    UploadDocumentSerializer, StartTestSerializer,
    SubmitAnswerSerializer, CompleteTestSerializer,
    LeaderboardEntrySerializer, UserProfileSerializer,
)
from .services.adaptive_engine import AdaptiveEloEngine
from .services import llm_service

from pages.utils.pdf_parser import extract_text_from_pdf


# ──────────────────────────────────────────────
#  Helper: resolve user (no-auth fallback)
# ──────────────────────────────────────────────


def _get_user(request):
    """Return the authenticated user or raise 401 (demo fallback removed)."""
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        return request.user
    raise AuthenticationFailed('Authentication required.')


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _get_document_for_user_or_challenge(doc_uuid, request):
    """
    Retrieve a Document either by ownership or via a valid SharedChallenge.
    Returns (document, challenge_or_None).
    """
    # Try direct ownership first
    try:
        doc = Document.objects.get(id=doc_uuid, user=_get_user(request))
        return doc, None
    except Document.DoesNotExist:
        pass

    # Try via active challenge
    try:
        challenge = SharedChallenge.objects.get(
            id=doc_uuid, is_active=True
        )
        return challenge.document, challenge
    except SharedChallenge.DoesNotExist:
        pass

    # Try any challenge referencing this doc
    try:
        challenge = SharedChallenge.objects.filter(
            document_id=doc_uuid, is_active=True
        ).first()
        if challenge:
            return challenge.document, challenge
    except Exception:
        pass

    raise get_object_or_404(Document, id=doc_uuid)


# ═══════════════════════════════════════════════
#  1. Content Generation
# ═══════════════════════════════════════════════


class UploadDocumentView(APIView):
    """POST /api/documents/upload/ — Upload PDF, parse text."""

    def post(self, request):
        serializer = UploadDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = _get_user(request)
        pdf_file = serializer.validated_data['file']

        doc = Document.objects.create(
            user=user,
            file=pdf_file,
            filename=pdf_file.name,
        )

        try:
            extracted_text = extract_text_from_pdf(doc.file.path)
            if not extracted_text.strip():
                raise ValueError("Extracted text from PDF is empty.")
            doc.raw_text = extracted_text
            doc.save()
        except Exception as e:
            return Response(
                {'error': f'Failed to process PDF: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentSummaryView(APIView):
    """GET /api/documents/<uuid>/summary/ — Generate/return structured summary."""

    def get(self, request, doc_id):
        doc, _ = _get_document_for_user_or_challenge(doc_id, request)

        # Return cached summary if available
        if doc.summary_data:
            return Response(doc.summary_data)

        try:
            text = doc.raw_text or extract_text_from_pdf(doc.file.path)
            if not text.strip():
                raise ValueError("Document has no extractable text.")

            summary_data = llm_service.generate_summary(text=text)
            doc.summary_data = summary_data
            doc.save()

            return Response(summary_data)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate summary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentFlashcardsView(APIView):
    """GET /api/documents/<uuid>/flashcards/ — Generate/return 20 flashcards."""

    def get(self, request, doc_id):
        doc, _ = _get_document_for_user_or_challenge(doc_id, request)

        # Return cached flashcards if available
        cached = doc.flashcards.all()
        if cached.exists():
            return Response(FlashcardSerializer(cached, many=True).data)

        try:
            text = doc.raw_text or extract_text_from_pdf(doc.file.path)
            if not text.strip():
                raise ValueError("Document has no extractable text.")

            cards_data = llm_service.generate_flashcards(text=text)
            flashcard_objects = [
                Flashcard(document=doc, front=c['front'], back=c['back'])
                for c in cards_data
            ]
            Flashcard.objects.bulk_create(flashcard_objects)

            return Response(
                FlashcardSerializer(doc.flashcards.all(), many=True).data
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to generate flashcards: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ═══════════════════════════════════════════════
#  2. Solo Testing Flow
# ═══════════════════════════════════════════════


class TestStartView(APIView):
    """POST /api/test/start/ — Create session, select first question."""

    def post(self, request):
        serializer = StartTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_id = serializer.validated_data['document_id']
        user = _get_user(request)
        profile = _get_or_create_profile(user)

        doc = get_object_or_404(Document, id=doc_id)

        # Auto-generate question bank if none exist
        questions = Question.objects.filter(document=doc)
        if not questions.exists():
            try:
                text = doc.raw_text or extract_text_from_pdf(doc.file.path)
                if not text.strip():
                    raise ValueError("Document has no extractable text.")

                questions_data = llm_service.generate_question_bank(text=text)
                question_objects = [
                    Question(
                        document=doc,
                        question_text=item['question'],
                        options=item['options'],
                        correct_index=item['correct_index'],
                        explanation=item.get('explanation', ''),
                        difficulty_rating=item['difficulty_rating'],
                    )
                    for item in questions_data
                ]
                Question.objects.bulk_create(question_objects)
                questions = Question.objects.filter(document=doc)
            except Exception as e:
                return Response(
                    {'error': f'Failed to generate questions: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Create session
        session = TestSession.objects.create(
            user=user,
            document=doc,
            start_elo=profile.elo_rating,
        )

        # Select optimal first question
        all_questions = list(questions.values('id', 'difficulty_rating'))
        selected = AdaptiveEloEngine.select_next_question(profile.elo_rating, all_questions)

        if not selected:
            return Response(
                {'error': 'No questions available for this document'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = Question.objects.get(id=selected['id'])

        return Response({
            'session_id': str(session.id),
            'document_id': str(doc.id),
            'start_elo': profile.elo_rating,
            'question': QuestionBriefSerializer(question).data,
            'total_questions_available': questions.count(),
        }, status=status.HTTP_201_CREATED)


class TestSubmitAnswerView(APIView):
    """POST /api/test/submit-answer/ — Submit answer, compute Elo, return next question."""

    def post(self, request):
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        question_id = serializer.validated_data['question_id']
        selected_index = serializer.validated_data['selected_index']
        time_taken_sec = serializer.validated_data['time_taken_sec']

        user = _get_user(request)
        session = get_object_or_404(TestSession, id=session_id, user=user)

        if session.is_completed:
            return Response(
                {'error': 'Session already completed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = get_object_or_404(Question, id=question_id)
        is_correct = selected_index == question.correct_index

        profile = _get_or_create_profile(user)

        # Calculate Elo update
        new_user_elo, new_question_elo = AdaptiveEloEngine.calculate_elo_update(
            user_elo=profile.elo_rating,
            question_elo=question.difficulty_rating,
            is_correct=is_correct,
            total_answered=profile.total_questions_answered,
            time_taken_sec=time_taken_sec,
        )

        # Record response
        response_obj = SessionResponse.objects.create(
            session=session,
            question=question,
            selected_index=selected_index,
            is_correct=is_correct,
            time_taken_sec=time_taken_sec,
            user_elo_after=new_user_elo,
            question_elo_after=new_question_elo,
        )

        # Update question stats
        question.times_served += 1
        if is_correct:
            question.times_correct += 1
        question.difficulty_rating = new_question_elo
        question.save()

        # Update user profile
        old_elo = profile.elo_rating
        profile.elo_rating = new_user_elo
        profile.total_questions_answered += 1
        profile.save()

        # Get next question
        answered_ids = session.responses.values_list('question_id', flat=True)
        available = list(
            Question.objects.filter(document=session.document)
            .exclude(id__in=answered_ids)
            .values('id', 'difficulty_rating')
        )
        next_question = AdaptiveEloEngine.select_next_question(new_user_elo, available)

        result = {
            'is_correct': is_correct,
            'correct_index': question.correct_index,
            'explanation': question.explanation,
            'selected_index': selected_index,
            'elo_change': new_user_elo - old_elo,
            'user_elo_after': new_user_elo,
            'question_elo_after': new_question_elo,
            'questions_answered': session.responses.count(),
            'total_available': Question.objects.filter(document=session.document).count(),
        }

        if next_question:
            q = Question.objects.get(id=next_question['id'])
            result['next_question'] = QuestionBriefSerializer(q).data
        else:
            session.is_completed = True
            session.end_elo = new_user_elo
            session.save()
            result['session_completed'] = True

        return Response(result)


class TestCompleteView(APIView):
    """POST /api/test/complete/ — Finalize session, return full review."""

    def post(self, request):
        serializer = CompleteTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        user = _get_user(request)
        session = get_object_or_404(TestSession, id=session_id, user=user)

        profile = _get_or_create_profile(user)

        if not session.is_completed:
            session.is_completed = True
            session.end_elo = profile.elo_rating
            session.save()

        responses = session.responses.select_related('question').all()

        total = responses.count()
        correct = responses.filter(is_correct=True).count()
        accuracy = (correct / total * 100) if total > 0 else 0.0

        breakdown = []
        for resp in responses:
            breakdown.append({
                'question_text': resp.question.question_text,
                'options': resp.question.options,
                'correct_index': resp.question.correct_index,
                'selected_index': resp.selected_index,
                'is_correct': resp.is_correct,
                'time_taken_sec': resp.time_taken_sec,
                'difficulty_label': resp.question.difficulty_label,
                'difficulty_rating': resp.question.difficulty_rating,
                'explanation': resp.question.explanation,
                'user_elo_after': resp.user_elo_after,
                'question_elo_after': resp.question_elo_after,
            })

        return Response({
            'session_id': str(session.id),
            'start_elo': session.start_elo,
            'end_elo': session.end_elo or profile.elo_rating,
            'accuracy': round(accuracy, 1),
            'correct_count': correct,
            'total_questions': total,
            'final_elo': profile.elo_rating,
            'breakdown': breakdown,
        })


# ═══════════════════════════════════════════════
#  3. Social Sharing & Challenges
# ═══════════════════════════════════════════════


class DocumentShareView(APIView):
    """POST /api/documents/<uuid>/share/ — Create SharedChallenge, return shareable link."""

    def post(self, request, doc_id):
        user = _get_user(request)
        doc = get_object_or_404(Document, id=doc_id)

        challenge = SharedChallenge.objects.create(
            document=doc,
            creator=user,
        )

        return Response({
            'challenge_id': str(challenge.id),
            'share_url': f'/challenge/{challenge.id}/',
            'document_filename': doc.filename,
            'creator': user.username,
            'created_at': challenge.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class ChallengeDetailView(APIView):
    """GET /api/challenge/<uuid>/ — Challenge metadata for the pre-test lobby."""

    def get(self, request, challenge_id):
        challenge = get_object_or_404(
            SharedChallenge, id=challenge_id, is_active=True
        )

        # Build leaderboard (top 3 by elo gained)
        sessions = TestSession.objects.filter(
            challenge=challenge, is_completed=True
        ).select_related('user')

        leaderboard = []
        for s in sessions:
            elo_gained = (s.end_elo or s.start_elo) - s.start_elo
            total = s.responses.count()
            correct = s.responses.filter(is_correct=True).count()
            accuracy = (correct / total * 100) if total > 0 else 0.0
            leaderboard.append({
                'username': s.user.username,
                'elo_gained': round(elo_gained, 1),
                'accuracy': round(accuracy, 1),
                'questions_answered': total,
            })

        leaderboard.sort(key=lambda x: x['elo_gained'], reverse=True)

        return Response({
            'challenge_id': str(challenge.id),
            'document_filename': challenge.document.filename,
            'creator_username': challenge.creator.username,
            'created_at': challenge.created_at.isoformat(),
            'leaderboard': leaderboard[:3],
        })


class ChallengeStartView(APIView):
    """POST /api/challenge/<uuid>/start/ — Start a session tied to the challenge."""

    def post(self, request, challenge_id):
        challenge = get_object_or_404(
            SharedChallenge, id=challenge_id, is_active=True
        )

        user = _get_user(request)
        profile = _get_or_create_profile(user)
        doc = challenge.document

        # Auto-generate questions if needed
        questions = Question.objects.filter(document=doc)
        if not questions.exists():
            try:
                text = doc.raw_text or extract_text_from_pdf(doc.file.path)
                if not text.strip():
                    raise ValueError("Document has no extractable text.")

                questions_data = llm_service.generate_question_bank(text=text)
                question_objects = [
                    Question(
                        document=doc,
                        question_text=item['question'],
                        options=item['options'],
                        correct_index=item['correct_index'],
                        explanation=item.get('explanation', ''),
                        difficulty_rating=item['difficulty_rating'],
                    )
                    for item in questions_data
                ]
                Question.objects.bulk_create(question_objects)
                questions = Question.objects.filter(document=doc)
            except Exception as e:
                return Response(
                    {'error': f'Failed to generate questions: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Create session linked to challenge
        session = TestSession.objects.create(
            user=user,
            document=doc,
            challenge=challenge,
            start_elo=profile.elo_rating,
        )

        # Select first question
        all_questions = list(questions.values('id', 'difficulty_rating'))
        selected = AdaptiveEloEngine.select_next_question(profile.elo_rating, all_questions)

        if not selected:
            return Response(
                {'error': 'No questions available'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = Question.objects.get(id=selected['id'])

        return Response({
            'session_id': str(session.id),
            'challenge_id': str(challenge.id),
            'document_id': str(doc.id),
            'start_elo': profile.elo_rating,
            'question': QuestionBriefSerializer(question).data,
            'total_questions_available': questions.count(),
        }, status=status.HTTP_201_CREATED)


class ChallengeLeaderboardView(APIView):
    """GET /api/challenge/<uuid>/leaderboard/ — All participants sorted by Elo gained."""

    def get(self, request, challenge_id):
        challenge = get_object_or_404(
            SharedChallenge, id=challenge_id, is_active=True
        )

        sessions = TestSession.objects.filter(
            challenge=challenge, is_completed=True
        ).select_related('user')

        leaderboard = []
        for s in sessions:
            elo_gained = (s.end_elo or s.start_elo) - s.start_elo
            total = s.responses.count()
            correct = s.responses.filter(is_correct=True).count()
            accuracy = (correct / total * 100) if total > 0 else 0.0
            leaderboard.append({
                'username': s.user.username,
                'start_elo': s.start_elo,
                'end_elo': s.end_elo or s.start_elo,
                'elo_gained': round(elo_gained, 1),
                'accuracy': round(accuracy, 1),
                'questions_answered': total,
            })

        # Sort by elo_gained desc, then accuracy desc
        leaderboard.sort(key=lambda x: (-x['elo_gained'], -x['accuracy']))

        return Response({
            'challenge_id': str(challenge.id),
            'document_filename': challenge.document.filename,
            'leaderboard': leaderboard,
        })


# ═══════════════════════════════════════════════
#  4. User Profile
# ═══════════════════════════════════════════════


class UserProfileView(APIView):
    """GET /api/profile/ — Return current user's profile."""

    def get(self, request):
        user = _get_user(request)
        profile = _get_or_create_profile(user)
        return Response(UserProfileSerializer(profile).data)


# ═══════════════════════════════════════════════
#  5. Daily GK Quiz
# ═══════════════════════════════════════════════

from django.utils import timezone
from django.db import transaction
from django.db import IntegrityError
from .models import DailyQuiz, DailyQuestion, DailyQuizSession, UserProfile
from .services.daily_quiz_service import (
    ensure_daily_quiz_for_date,
    questions_for_user,
    apply_quiz_completion,
)


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
    matching their gk_skill_tier. Includes streak stats and the mini leaderboard.
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
        tier = profile.gk_skill_tier

        # Check if user already completed today's quiz
        existing_session = DailyQuizSession.objects.filter(
            user=user, quiz=quiz
        ).first()

        # Serve 5 universal CA + 5 tier-matched GK (sanitized — no answers)
        served = questions_for_user(quiz, tier)
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

        return Response(result)


class DailyQuizSubmitView(APIView):
    """
    POST /api/v2/daily-quiz/submit/

    Validates responses, grades only the user's served questions (5 CA + 5
    tier-matched GK), computes the score, updates the daily streak and the
    adaptive GK skill tier, and writes the attempt record.
    Body: { answers: [{question_id, selected_index}, ...], total_time_sec: float }
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

        answers_data = request.data.get('answers', [])
        if not isinstance(answers_data, list) or not answers_data:
            return Response(
                {'error': 'answers array is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            total_time_sec = float(request.data.get('total_time_sec', 0) or 0)
        except (TypeError, ValueError):
            total_time_sec = 0.0

        # Grade ONLY the user's served questions (5 universal CA + their 5 GK),
        # so users on different difficulty tiers can't answer out-of-tier items.
        tier = profile.gk_skill_tier
        served = questions_for_user(quiz, tier)
        questions = {str(q.id): q for q in served}

        score = 0
        gk_correct = 0
        processed_answers = []

        for ans in answers_data:
            q_id = str(ans.get('question_id', ''))
            try:
                selected = int(ans.get('selected_index', -1))
            except (TypeError, ValueError):
                selected = -1

            q = questions.get(q_id)
            if q is None or selected not in {0, 1, 2, 3}:
                continue  # unknown question or invalid option → ignore

            is_correct = (selected == q.correct_index)
            if is_correct:
                score += 1
                if q.category == DailyQuestion.Category.GK:
                    gk_correct += 1

            processed_answers.append({
                'question_id': q_id,
                'selected_index': selected,
                'is_correct': is_correct,
            })

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
                apply_quiz_completion(profile, gk_correct, today)
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
