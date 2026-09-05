from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Friendship, UserProfile, QuizChallenge
from .serializers import (
    FriendshipSerializer,
    SocialProfileSerializer,
    SendFriendRequestSerializer,
    RespondFriendRequestSerializer,
    ManageFriendSerializer,
)


def _me(request):
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        return request.user
    raise AuthenticationFailed('Authentication required.')


def _serialized_profile(user, context):
    try:
        profile = user.study_profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    return SocialProfileSerializer(profile, context=context).data


class FriendsListView(APIView):
    """GET /api/social/friends/ — confirmed friends with streak/tier/online state."""

    def get(self, request):
        me = _me(request)
        rows = (
            Friendship.objects.select_related(
                'sender', 'receiver', 'sender__study_profile',
                'receiver__study_profile',
            )
            .filter(
                status=Friendship.Status.ACCEPTED,
            )
            .filter(Q(sender=me) | Q(receiver=me))
            .order_by('-updated_at')
        )
        serializer = FriendshipSerializer(
            rows, many=True, context={'request': request}
        )
        return Response({
            'friends': serializer.data,
            'count': len(serializer.data),
        })


class FriendRequestsView(APIView):
    """GET /api/social/requests/ — incoming + outgoing pending requests."""

    def get(self, request):
        me = _me(request)
        rows = (
            Friendship.objects.select_related(
                'sender', 'receiver', 'initiator', 'sender__study_profile',
                'receiver__study_profile',
            )
            .filter(status=Friendship.Status.PENDING)
            .filter(Q(sender=me) | Q(receiver=me))
            .order_by('-created_at')
        )
        serializer = FriendshipSerializer(
            rows, many=True, context={'request': request}
        )
        incoming = [d for d in serializer.data if d['direction'] == 'incoming']
        outgoing = [d for d in serializer.data if d['direction'] == 'outgoing']
        return Response({'incoming': incoming, 'outgoing': outgoing})


class PendingCountView(APIView):
    """GET /api/social/pending-count/ — badge numbers for the navbar bell."""

    def get(self, request):
        me = _me(request)
        friend_requests = Friendship.objects.filter(
            Q(sender=me) | Q(receiver=me),
            status=Friendship.Status.PENDING,
        ).exclude(initiator=me).count()
        incoming_challenges = QuizChallenge.objects.filter(
            challenged_user=me, status=QuizChallenge.Status.PENDING,
        ).count()
        return Response({
            'friend_requests': friend_requests,
            'incoming_challenges': incoming_challenges,
            'total': friend_requests + incoming_challenges,
        })


class SendFriendRequestView(APIView):
    """POST /api/social/request/send/ {user_id} — initiate (or auto-accept)."""

    def post(self, request):
        serializer = SendFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        me = _me(request)
        target = get_object_or_404(User, pk=serializer.validated_data['user_id'])

        if target.pk == me.pk:
            return Response(
                {'error': 'You cannot befriend yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row = Friendship.relationship_between(me, target)
        try:
            with transaction.atomic():
                if row is None:
                    Friendship.objects.create(
                        sender=me, receiver=target,
                        initiator=me, status=Friendship.Status.PENDING,
                    )
                    return Response({
                        'status': 'pending',
                        'message': f'Friend request sent to {target.username}.',
                    }, status=status.HTTP_201_CREATED)

                if row.status == Friendship.Status.ACCEPTED:
                    return Response(
                        {'error': f'You are already friends with {target.username}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if row.status == Friendship.Status.BLOCKED:
                    return Response(
                        {'error': 'This friendship is blocked.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if row.status == Friendship.Status.PENDING:
                    if row.initiator_id == me.pk:
                        return Response(
                            {'error': 'Request already sent — waiting for a reply.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    # They asked us first → sending back completes the friendship.
                    row.status = Friendship.Status.ACCEPTED
                    row.blocker = None
                    row.save(update_fields=['status', 'blocker', 'updated_at'])
                    return Response({
                        'status': 'accepted',
                        'message': f'You and {target.username} are now friends!',
                    })
                # DECLINED → re-request by flipping the initiator back to us.
                row.initiator = me
                row.status = Friendship.Status.PENDING
                row.blocker = None
                row.save(update_fields=['initiator', 'status', 'blocker', 'updated_at'])
                return Response({
                    'status': 'pending',
                    'message': f'Friend request sent to {target.username}.',
                }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {'error': 'Request could not be created — try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RespondFriendRequestView(APIView):
    """POST /api/social/request/<pk>/respond/ {action: accept|decline|block}."""

    def post(self, request, pk):
        serializer = RespondFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        me = _me(request)
        action = serializer.validated_data['action']

        row = get_object_or_404(
            Friendship, pk=pk, status=Friendship.Status.PENDING,
        )
        if row.sender_id != me.pk and row.receiver_id != me.pk:
            return Response(
                {'error': 'This request does not involve you.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if action in ('accept', 'decline') and row.initiator_id == me.pk:
            return Response(
                {'error': 'You cannot act on your own outgoing request.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == 'accept':
            row.status = Friendship.Status.ACCEPTED
            row.blocker = None
            row.save(update_fields=['status', 'blocker', 'updated_at'])
        elif action == 'decline':
            row.status = Friendship.Status.DECLINED
            row.save(update_fields=['status', 'updated_at'])
        else:  # block
            row.status = Friendship.Status.BLOCKED
            row.blocker = me
            row.save(update_fields=['status', 'blocker', 'updated_at'])

        return Response({
            'status': row.status,
            'message': f'Request {action}ed.',
        })


class CancelFriendRequestView(APIView):
    """POST /api/social/request/<pk>/cancel/ — withdraw an outgoing request."""

    def post(self, request, pk):
        me = _me(request)
        row = get_object_or_404(
            Friendship, pk=pk, status=Friendship.Status.PENDING,
        )
        if row.initiator_id != me.pk:
            return Response(
                {'error': 'You can only cancel requests you sent.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        row.delete()
        return Response({'message': 'Friend request cancelled.'})


class ManageFriendView(APIView):
    """POST /api/social/friends/manage/ {user_id, action: remove|block}."""

    def post(self, request):
        serializer = ManageFriendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        me = _me(request)
        action = serializer.validated_data['action']
        target = get_object_or_404(User, pk=serializer.validated_data['user_id'])

        row = Friendship.relationship_between(me, target)
        if action == 'remove':
            if row is None or row.status != Friendship.Status.ACCEPTED:
                return Response(
                    {'error': 'You are not friends with this user.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            row.delete()
            return Response({'message': f'{target.username} removed from friends.'})

        # block — works against friends, requesters, or strangers.
        if row is None:
            with transaction.atomic():
                Friendship.objects.create(
                    sender=me, receiver=target,
                    initiator=me, status=Friendship.Status.BLOCKED,
                    blocker=me,
                )
        else:
            row.status = Friendship.Status.BLOCKED
            row.blocker = me
            row.save(update_fields=['status', 'blocker', 'updated_at'])
        return Response({'message': f'{target.username} has been blocked.'})


class SearchUsersView(APIView):
    """GET /api/social/users/search/?q= — excludes self, friends, pending, blocked."""

    def get(self, request):
        me = _me(request)
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 1:
            return Response({'results': []})

        # Everyone already connected to me in a blocking way (friends, pending,
        # blocked — but NOT declined, since a declined request can be re-sent).
        rows = Friendship.objects.filter(
            Q(sender=me) | Q(receiver=me),
        ).exclude(status=Friendship.Status.DECLINED)
        excluded = {me.pk}
        for s, r in rows.values_list('sender_id', 'receiver_id'):
            excluded.add(r if s == me.pk else s)

        profiles = (
            UserProfile.objects.select_related('user')
            .filter(
                user__username__icontains=q,
            )
            .exclude(user_id__in=excluded)
            .order_by('user__username')[:20]
        )
        # Also match emails (excluding the requester's own rows are handled above).
        profiles = list(profiles)
        matched_ids = {p.user_id for p in profiles}
        if len(profiles) < 20:
            by_email = (
                UserProfile.objects.select_related('user')
                .filter(user__email__icontains=q)
                .exclude(user_id__in=excluded | matched_ids)
                .order_by('user__username')[: 20 - len(profiles)]
            )
            profiles.extend(by_email)

        serializer = SocialProfileSerializer(
            profiles, many=True, context={'request': request}
        )
        return Response({'results': serializer.data})
