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
    QuizSessionState,
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
from .services import persona_engine
from .services.persona_engine import (
    clamp_pdf_elo,
    finalize_session_metrics,
    initial_sub_tier_for_persona,
    select_first_question,
    select_next_question_for_session,
    update_session_state_after_answer,
    determine_and_predict_persona,
)

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
    """POST /api/test/start/ — Two-tier adaptive PDF quiz start.

    When question_count is provided and > 0:
      - generates exactly 2 * question_count questions for the pool,
      - assigns/predicts the user's persona tier, and
      - serves exactly question_count questions using the persona sub-tier
        selection rules. Unused pool questions remain in the DB but are never
      - shown in this session.

    When question_count is omitted the existing full-pool behavior is preserved
    for backward compatibility.
    """

    def post(self, request):
        serializer = StartTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_id = serializer.validated_data['document_id']
        requested = serializer.validated_data.get('question_count')
        user = _get_user(request)
        profile = _get_or_create_profile(user)

        # Accept both study_core Document (UUID) and legacy pages UploadedPDF (int).
        try:
            doc = get_object_or_404(Document, id=doc_id)
        except Exception:
            # Fallback: try legacy pages UploadedPDF by integer id.
            from pages.models import UploadedPDF
            try:
                uploaded_pdf = get_object_or_404(UploadedPDF, id=int(doc_id))
                # Create or find a study_core Document linked to this user.
                doc = Document.objects.filter(
                    user=user,
                    filename=uploaded_pdf.file.name,
                ).first()
                if not doc:
                    doc = Document.objects.create(
                        user=user,
                        file=uploaded_pdf.file,
                        filename=uploaded_pdf.file.name,
                    )
                    # Reuse raw_text if already extracted by the pages app.
                    if uploaded_pdf.raw_text.strip():
                        doc.raw_text = uploaded_pdf.raw_text
                        doc.save(update_fields=['raw_text'])
                    else:
                        try:
                            text = extract_text_from_pdf(doc.file.path)
                            if text.strip():
                                doc.raw_text = text
                                doc.save(update_fields=['raw_text'])
                        except Exception:
                            pass
            except Exception:
                raise

        # Decide persona tier via the two-tier rules from the spec.
        # Phase 1 (cold start): < 3 completed quizzes -> default persona.
        # Phase 2 (macro persona): otherwise -> ML prediction.
        persona_tier, persona_probs = persona_engine.determine_and_predict_persona(profile)

        # Generate or reuse the question bank.
        questions = Question.objects.filter(document=doc)
        generated_count = questions.count()

        if not questions.exists():
            try:
                text = doc.raw_text
                if not text or not text.strip():
                    text = extract_text_from_pdf(doc.file.path)
                    doc.raw_text = text or ''
                    doc.save(update_fields=['raw_text'])
                if not text or not text.strip():
                    raise ValueError("Document has no extractable text.")

                target_pool_size = (2 * requested) if (requested and requested > 0) else 20
                questions_data = llm_service.generate_question_bank(text=text, num_questions=target_pool_size)
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
                generated_count = questions.count()
            except ValueError as e:
                # Document-level problems are client errors.
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                return Response(
                    {'error': f'Failed to generate questions: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        requested_questions = requested if (requested and requested > 0) else generated_count
        if requested_questions > generated_count:
            requested_questions = generated_count

        # Create session + adaptive state.
        session = TestSession.objects.create(
            user=user,
            document=doc,
            start_elo=profile.elo_rating,
            persona_tier=persona_tier,
            requested_questions=requested_questions,
            generated_questions=generated_count,
        )

        state, created = QuizSessionState.objects.get_or_create(session=session)
        if created:
            state.active_sub_tier = persona_engine.initial_sub_tier_for_persona(persona_tier)
            state.save()

        # Select the first question using the persona sub-tier logic.
        question, sub_tier, reason = persona_engine.select_first_question(
            session, state, list(questions)
        )

        if not question:
            return Response(
                {'error': 'No questions available for this document'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'session_id': str(session.id),
            'document_id': str(doc.id),
            'start_elo': profile.elo_rating,
            'persona_tier': persona_tier,
            'persona_probabilities': persona_probs,
            'active_sub_tier': sub_tier,
            'requested_questions': requested_questions,
            'generated_questions': generated_count,
            'question': QuestionBriefSerializer(question).data,
            'total_questions_available': generated_count,
        }, status=status.HTTP_201_CREATED)


class TestSubmitAnswerView(APIView):
    """POST /api/test/submit-answer/ — Submit answer, compute Elo/IRT, apply

    two-tier persona sub-tier routing, and return the next question.

    The Elo/IRT math is still done by AdaptiveEloEngine; this view only adds
    the persona sub-tier promotion/demotion and the served-question tracking
    so the same question is never shown twice and unused pool questions stay
    unused.
    """

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

        # Clo sure close_consistent Elo/IRT math from the existing engine.
        new_user_elo, new_question_elo = AdaptiveEloEngine.calculate_elo_update(
            user_elo=profile.elo_rating,
            question_elo=question.difficulty_rating,
            is_correct=is_correct,
            total_answered=profile.total_questions_answered,
            time_taken_sec=time_taken_sec,
        )

        # Enforce the PDF-assessment contract: Elo cannot go below 100.
        new_user_elo = persona_engine.clamp_pdf_elo(new_user_elo)

        # Record response.
        response_obj = SessionResponse.objects.create(
            session=session,
            question=question,
            selected_index=selected_index,
            is_correct=is_correct,
            time_taken_sec=time_taken_sec,
            user_elo_after=new_user_elo,
            question_elo_after=new_question_elo,
        )

        # Update question stats.
        question.times_served += 1
        if is_correct:
            question.times_correct += 1
        question.difficulty_rating = new_question_elo
        question.save()

        # Update user profile.
        old_elo = profile.elo_rating
        profile.elo_rating = new_user_elo
        profile.total_questions_answered += 1
        profile.current_elo_rating = persona_engine.clamp_pdf_elo(new_user_elo)
        profile.save()

        # Update persona sub-tier state.
        state = getattr(session, 'adaptive_state', None)
        sub_tier = state.active_sub_tier if state else session.persona_tier
        if state:
            new_sub_tier, transition = persona_engine.update_session_state_after_answer(
                state, is_correct
            )
            sub_tier = new_sub_tier

        # Determine whether to serve a next question or finish.
        answered_ids = session.responses.values_list('question_id', flat=True)
        questions_to_answer = session.requested_questions
        answered_count = session.responses.count()
        finished = answered_count >= questions_to_answer if questions_to_answer else False

        result = {
            'is_correct': is_correct,
            'correct_index': question.correct_index,
            'explanation': question.explanation,
            'selected_index': selected_index,
            'elo_change': new_user_elo - old_elo,
            'user_elo_after': new_user_elo,
            'question_elo_after': question.difficulty_rating,
            'questions_answered': answered_count,
            'total_available': Question.objects.filter(document=session.document).count(),
            'active_sub_tier': sub_tier,
        }

        if not finished:
            # Select next question from the remaining pool using the persona
            # sub-tier routing.
            all_questions = list(Question.objects.filter(document=session.document))
            next_q, next_sub_tier, reason = persona_engine.select_next_question_for_session(
                session, state, all_questions, answered_ids
            )
            result['active_sub_tier'] = next_sub_tier or sub_tier
            if next_q:
                result['next_question'] = QuestionBriefSerializer(next_q).data
            else:
                finished = True

        if finished:
            session.is_completed = True
            session.end_elo = new_user_elo
            session.save()
            persona_engine.finalize_session_metrics(session, profile, session.responses.all())
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
from .models import (
    DailyQuiz, DailyQuestion, DailyQuizSession,
    DailyQuizAnswer, UserProfile,
)
from .services.daily_quiz_service import (
    ensure_daily_quiz_for_date,
    served_questions_for_user,
    select_gk_tier,
    apply_quiz_completion,
    record_daily_quiz_answer,
    recorded_answers_for_user,
    QuizAnswerConflict,
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
        # served_questions_for_user picks the tier from Elo via the IRT engine.
        served = served_questions_for_user(quiz, profile)
        questions = {str(q.id): q for q in served}

        score = 0
        gk_correct = 0
        processed_answers = []
        gk_answers = []  # (tier, is_correct) per answered GK question → Elo nudge

        # New flow: answers were locked one-by-one via /daily-quiz/check/, so
        # grade exclusively from the recorded rows (the payload carries no
        # authority and is ignored). Locked rows make the run immutable —
        # nothing can be changed after the correct answer was revealed.
        recorded = recorded_answers_for_user(quiz, user)
        if recorded:
            for answer in recorded:
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
        else:
            # Legacy fallback: grade from the submitted payload (older clients
            # that answer the whole quiz without per-question checks).
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
