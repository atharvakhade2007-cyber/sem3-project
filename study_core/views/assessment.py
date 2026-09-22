"""Adaptive PDF test views (start / submit-answer / complete)."""

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Document,
    Question,
    QuizSessionState,
    SessionResponse,
    TestSession,
)
from ..serializers import (
    QuestionBriefSerializer,
    StartTestSerializer,
    SubmitAnswerSerializer,
    CompleteTestSerializer,
)
from ..services import llm_service
from ..services import persona_engine
from ..services.adaptive_engine import AdaptiveEloEngine
from ..services.persona_engine import (
    clamp_pdf_elo,
    finalize_session_metrics,
)
from .common import _get_user, _get_or_create_profile
from .documents import _document_text


def _generate_question_bank(doc, requested):
    """Generate the document's question bank when it has none yet.

    Returns (questions_queryset, generated_count) or raises ValueError for
    document-level problems (client errors).
    """
    text = _document_text(doc)
    target_pool_size = (2 * requested) if (requested and requested > 0) else 20
    questions_data = llm_service.generate_question_bank(
        text=text, num_questions=target_pool_size
    )
    Question.objects.bulk_create([
        Question(
            document=doc,
            question_text=item['question'],
            options=item['options'],
            correct_index=item['correct_index'],
            explanation=item.get('explanation', ''),
            difficulty_rating=item['difficulty_rating'],
        )
        for item in questions_data
    ])
    questions = Question.objects.filter(document=doc)
    return questions, questions.count()


class TestStartView(APIView):
    """POST /api/v2/test/start/ — Two-tier adaptive PDF quiz start.

    When question_count is provided and > 0:
      - generates exactly 2 * question_count questions for the pool,
      - assigns/predicts the user's persona tier, and
      - serves exactly question_count questions using the persona sub-tier
        selection rules. Unused pool questions remain in the DB but are never
        shown in this session.

    When question_count is omitted the full-pool behavior is used instead.
    """

    def post(self, request):
        serializer = StartTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_id = serializer.validated_data['document_id']
        requested = serializer.validated_data.get('question_count')
        user = _get_user(request)
        profile = _get_or_create_profile(user)

        doc = get_object_or_404(Document, id=doc_id)

        # Decide persona tier via the two-tier rules from the spec.
        # Phase 1 (cold start): < 3 completed quizzes -> default persona.
        # Phase 2 (macro persona): otherwise -> ML prediction.
        persona_tier, persona_probs = persona_engine.determine_and_predict_persona(profile)

        # Generate or reuse the question bank.
        questions = Question.objects.filter(document=doc)
        generated_count = questions.count()

        if not questions.exists():
            try:
                questions, generated_count = _generate_question_bank(doc, requested)
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
        # dedupe_bank guards against duplicate rows left in banks generated
        # before LLM-side dedup was enforced.
        question, sub_tier, _reason = persona_engine.select_first_question(
            session, state, persona_engine.dedupe_bank(list(questions))
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
    """POST /api/v2/test/submit-answer/ — Submit answer, compute Elo/IRT, apply

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

        # Consistent Elo/IRT math from the existing engine.
        new_user_elo, new_question_elo = AdaptiveEloEngine.calculate_elo_update(
            user_elo=profile.elo_rating,
            question_elo=question.difficulty_rating,
            is_correct=is_correct,
            total_answered=profile.total_questions_answered,
            time_taken_sec=time_taken_sec,
        )

        # Enforce the PDF-assessment contract: Elo cannot go below 100.
        new_user_elo = clamp_pdf_elo(new_user_elo)

        # Record response.
        SessionResponse.objects.create(
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
        profile.current_elo_rating = clamp_pdf_elo(new_user_elo)
        profile.save()

        # Update persona sub-tier state.
        state = getattr(session, 'adaptive_state', None)
        sub_tier = state.active_sub_tier if state else session.persona_tier
        if state:
            new_sub_tier, _transition = persona_engine.update_session_state_after_answer(
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
            # sub-tier routing. dedupe_bank keeps legacy duplicate rows out
            # of the candidate pool.
            all_questions = persona_engine.dedupe_bank(
                list(Question.objects.filter(document=session.document))
            )
            next_q, next_sub_tier, _reason = persona_engine.select_next_question_for_session(
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
            finalize_session_metrics(session, profile, session.responses.all())
            result['session_completed'] = True

        return Response(result)


class TestCompleteView(APIView):
    """POST /api/v2/test/complete/ — Finalize session, return full review."""

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

        # Order by the server-side attempt timestamp so the review screen
        # lists questions in exactly the order they were answered (UUID PKs
        # sort randomly — 'id' ordering would scramble the sequence).
        responses = session.responses.select_related('question').order_by('answered_at', 'id')

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
