import uuid as uuid_mod
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Friendship, QuizChallenge, TestSession
from .serializers import (
    QuizChallengeSerializer,
    ChallengeCreateSerializer,
    ChallengeSubmitSerializer,
)

# Pending duels expire after this long (default 1 hour — matches the product
# decision of "30 min – 1 hr" for a friend to respond).
CHALLENGE_TTL = timedelta(minutes=60)


def _me(request):
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        return request.user
    raise AuthenticationFailed('Authentication required.')


def _expire_stale():
    """Lazily flip overdue pending duels to expired."""
    QuizChallenge.objects.filter(
        status=QuizChallenge.Status.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=QuizChallenge.Status.EXPIRED)


def _snapshot_from_responses(responses):
    """Build the self-contained duel snapshot from answered questions.

    Works with EITHER question/session stack: ``responses`` is an iterable of
    session-response rows exposing ``.is_correct``, ``.time_taken_sec`` and a
    ``.question`` with ``.id`` / ``.question_text`` / ``.options`` /
    ``.correct_index``.
    """
    snapshot = []
    question_ids = []
    score = 0
    total_time = 0.0
    for r in responses:
        q = r.question
        snapshot.append({
            'id': str(q.id),
            'question_text': q.question_text,
            'options': list(q.options or []),
            'correct_index': q.correct_index,
        })
        question_ids.append(str(q.id))
        if r.is_correct:
            score += 1
        total_time += float(r.time_taken_sec or 0)
    return snapshot, question_ids, score, round(total_time, 2)


def _resolve_user_session(user, session_id):
    """Resolve a session_id against the pages-legacy stack first, then study_core.

    Returns a tuple ``(kind, session, document_filename)`` or ``None``.
    The adaptive-test UI (PDF workspace) runs on the legacy ``pages`` models
    with integer ids; study_core sessions are UUID-keyed.
    """
    sid = str(session_id).strip()

    # 1) Legacy pages stack (integer ids) — what the PDF workspace uses.
    try:
        from pages.models import TestSession as LegacyTestSession

        int_id = int(sid)
    except (ImportError, ValueError):
        int_id = None

    if int_id is not None:
        try:
            legacy = LegacyTestSession.objects.select_related('document').get(
                id=int_id, user=user
            )
            return 'legacy', legacy, _filename(legacy.document)
        except LegacyTestSession.DoesNotExist:
            pass

    # 2) study_core stack (UUID ids).
    try:
        parsed = uuid_mod.UUID(sid)
    except (ValueError, AttributeError):
        parsed = None
    if parsed is not None:
        core = TestSession.objects.select_related('document').filter(
            id=parsed, user=user
        ).first()
        if core is not None:
            return 'core', core, _filename(core.document)
    return None


def _filename(document):
    """Extract a friendly filename from either Document model."""
    if document is None:
        return ''
    name = getattr(document, 'filename', None)
    if name:
        return name
    file_field = getattr(document, 'file', None)
    if file_field:
        return str(file_field.name).split('/')[-1].split('\\')[-1]
    return ''


def _responses_of(session, kind):
    if kind == 'legacy':
        return session.responses.select_related('question').order_by('id')
    return session.responses.select_related('question').order_by('id')


class CompletedSessionsView(APIView):
    """GET /api/challenges/sessions/ — my completed adaptive sessions (duel sources)."""

    def get(self, request):
        me = _me(request)
        sessions = []

        # Legacy (pages) sessions — the PDF workspace.
        try:
            from pages.models import TestSession as LegacyTestSession

            legacy_qs = (
                LegacyTestSession.objects.filter(user=me, is_completed=True)
                .select_related('document')
                .prefetch_related('responses__question')
                .order_by('-created_at')[:50]
            )
            for s in legacy_qs:
                responses = list(s.responses.all())
                total = len(responses)
                correct = sum(1 for r in responses if r.is_correct)
                time_sec = round(sum(float(r.time_taken_sec or 0) for r in responses), 2)
                sessions.append({
                    'session_id': str(s.id),
                    'document_filename': _filename(s.document) or 'Study session',
                    'questions_answered': total,
                    'correct_count': correct,
                    'accuracy': round(correct / total * 100, 1) if total else 0.0,
                    'total_time_sec': time_sec,
                    'created_at': s.created_at.isoformat() if s.created_at else None,
                })
        except ImportError:
            pass

        # study_core sessions (UUID).
        core_qs = (
            TestSession.objects.filter(user=me, is_completed=True)
            .select_related('document')
            .prefetch_related('responses__question')
            .order_by('-created_at', '-id')[:50]
        )
        for s in core_qs:
            responses = list(s.responses.all())
            total = len(responses)
            correct = sum(1 for r in responses if r.is_correct)
            time_sec = round(sum(float(r.time_taken_sec or 0) for r in responses), 2)
            sessions.append({
                'session_id': str(s.id),
                'document_filename': _filename(s.document) or 'Study session',
                'questions_answered': total,
                'correct_count': correct,
                'accuracy': round(correct / total * 100, 1) if total else 0.0,
                'total_time_sec': time_sec,
                'created_at': s.created_at.isoformat() if s.created_at else None,
            })

        sessions.sort(key=lambda x: x['created_at'] or '', reverse=True)
        return Response({'sessions': sessions})


class ChallengeCreateView(APIView):
    """
    POST /api/challenges/create/  {session_id, challenged_user_id}

    Snapshots the challenger's completed session (either the legacy PDF-workspace
    stack or study_core) into a self-contained duel question set. The target
    must be a confirmed friend.
    """

    def post(self, request):
        serializer = ChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        me = _me(request)

        session_id = serializer.validated_data['session_id']
        target_id = serializer.validated_data['challenged_user_id']

        resolved = _resolve_user_session(me, session_id)
        if resolved is None:
            return Response(
                {'error': 'Study session not found. Finish an adaptive test first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        kind, session, doc_filename = resolved
        if not session.is_completed:
            return Response(
                {'error': 'Finish your study session before turning it into a duel.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = get_object_or_404(User, pk=target_id)
        if not Friendship.are_friends(me, target):
            return Response(
                {'error': 'You can only challenge confirmed friends.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        responses = list(_responses_of(session, kind))
        if not responses:
            return Response(
                {'error': 'This session has no answered questions to duel with.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshot, question_ids, score, total_time = _snapshot_from_responses(responses)

        core_session = session if kind == 'core' else None
        core_document = session.document if kind == 'core' else None
        try:
            # Nested atomic → the IntegrityError rolls back only a savepoint,
            # leaving the surrounding transaction usable.
            with transaction.atomic():
                challenge = QuizChallenge.objects.create(
                    session=core_session,
                    document=core_document,
                    document_filename=doc_filename,
                    challenger=me,
                    challenged_user=target,
                    question_ids=question_ids,
                    question_data=snapshot,
                    challenger_score=score,
                    challenger_time_seconds=total_time,
                    expires_at=timezone.now() + CHALLENGE_TTL,
                )
        except IntegrityError:
            return Response(
                {'error': 'You already have a pending duel with this friend '
                          'on this session.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = QuizChallengeSerializer(
            challenge, context={'request': request}
        ).data
        return Response(data, status=status.HTTP_201_CREATED)


class ChallengeListView(APIView):
    """GET /api/challenges/ — incoming + outgoing duels for the user."""

    def get(self, request):
        _expire_stale()
        me = _me(request)
        qs = (
            QuizChallenge.objects.select_related(
                'challenger', 'challenged_user', 'document', 'winner',
            )
            .filter(Q(challenger=me) | Q(challenged_user=me))
            .order_by('-created_at')
        )
        serializer = QuizChallengeSerializer(
            qs, many=True, context={'request': request}
        )
        incoming = [d for d in serializer.data if d['role'] == 'incoming']
        outgoing = [d for d in serializer.data if d['role'] == 'outgoing']
        return Response({'incoming': incoming, 'outgoing': outgoing})


class ChallengeQuestionsView(APIView):
    """
    GET /api/challenges/<pk>/questions/

    The challenged user fetches the fixed question set (answers hidden) to
    play the duel. One-shot: rejects when already answered or expired.
    """

    def get(self, request, pk):
        _expire_stale()
        me = _me(request)
        challenge = get_object_or_404(QuizChallenge, pk=pk)

        if challenge.challenged_user_id != me.pk:
            return Response(
                {'error': 'Only the challenged user can play this duel.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if challenge.status == QuizChallenge.Status.EXPIRED:
            return Response(
                {'error': 'This duel has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if challenge.status != QuizChallenge.Status.PENDING:
            return Response(
                {'error': 'This duel is already finished.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if challenge.challenged_score is not None:
            return Response(
                {'error': 'You have already submitted this duel.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshot = challenge.question_data or []
        questions = [
            {
                'id': q['id'],
                'question_text': q['question_text'],
                'options': q['options'],
            }
            for q in snapshot
        ]

        return Response({
            'challenge_id': challenge.pk,
            'document_filename': challenge.document_filename or 'Study session',
            'challenger': challenge.challenger.username,
            'challenger_score': challenge.challenger_score,
            'challenger_time_seconds': challenge.challenger_time_seconds,
            'total_questions': len(questions),
            'questions': questions,
        })


class ChallengeSubmitView(APIView):
    """
    POST /api/challenges/<pk>/submit/  {answers: [{question_id,
    selected_index, time_taken_sec}, ...]}

    Grades the challenged user against the self-contained snapshot, resolves
    the winner (score, then time as tiebreaker), and completes the duel.
    """

    def post(self, request, pk):
        _expire_stale()
        me = _me(request)
        challenge = get_object_or_404(QuizChallenge, pk=pk)

        if challenge.challenged_user_id != me.pk:
            return Response(
                {'error': 'Only the challenged user can submit this duel.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if challenge.status == QuizChallenge.Status.EXPIRED:
            return Response(
                {'error': 'This duel has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if challenge.status != QuizChallenge.Status.PENDING \
                or challenge.challenged_score is not None:
            return Response(
                {'error': 'This duel is already finished.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChallengeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        snapshot = challenge.question_data or []
        if not snapshot:
            return Response(
                {'error': 'This duel has no questions.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        by_qid = {
            str(a['question_id']): a for a in serializer.validated_data['answers']
        }
        snapshot_qids = [str(q['id']) for q in snapshot]
        missing = [qid for qid in snapshot_qids if qid not in by_qid]
        if missing:
            return Response(
                {'error': f'You must answer every question ({len(snapshot)} total).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        score = 0
        total_time = 0.0
        review = []
        for q in snapshot:
            ans = by_qid[str(q['id'])]
            selected = ans['selected_index']
            total_time += ans['time_taken_sec']
            is_correct = selected == q['correct_index']
            if is_correct:
                score += 1
            review.append({
                'question_id': q['id'],
                'question_text': q['question_text'],
                'options': q['options'],
                'correct_index': q['correct_index'],
                'selected_index': selected,
                'is_correct': is_correct,
                'explanation': '',
            })

        # Winner: higher score; ties broken by faster total time.
        challenged_time = round(total_time, 2)
        if score > challenge.challenger_score:
            winner = me
        elif score < challenge.challenger_score:
            winner = challenge.challenger
        else:
            if challenged_time < challenge.challenger_time_seconds:
                winner = me
            elif challenge.challenger_time_seconds < challenged_time:
                winner = challenge.challenger
            else:
                winner = None

        challenge.challenged_score = score
        challenge.challenged_time_seconds = challenged_time
        challenge.status = QuizChallenge.Status.COMPLETED
        challenge.completed_at = timezone.now()
        if winner is not None:
            challenge.winner = winner
        challenge.save(update_fields=[
            'challenged_score', 'challenged_time_seconds', 'status',
            'completed_at', 'winner',
        ])

        if winner is None:
            verdict = 'draw'
            verdict_text = "It's a draw!"
        elif winner.pk == me.pk:
            verdict = 'won'
            verdict_text = 'You won the duel! 🏆'
        else:
            verdict = 'lost'
            verdict_text = f'{challenge.challenger.username} won this duel.'

        return Response({
            'verdict': verdict,
            'verdict_text': verdict_text,
            'challenger_score': challenge.challenger_score,
            'challenged_score': score,
            'challenger_time_seconds': challenge.challenger_time_seconds,
            'challenged_time_seconds': challenged_time,
            'winner_username': challenge.winner.username if challenge.winner else None,
            'review': review,
        }, status=status.HTTP_200_OK)
