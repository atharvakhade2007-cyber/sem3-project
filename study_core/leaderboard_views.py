from django.db.models import Sum
from django.db.models.functions import Coalesce

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Friendship, UserProfile, DailyQuizSession


def _me(request):
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        return request.user
    raise AuthenticationFailed('Authentication required.')


class FriendLeaderboardView(APIView):
    """
    GET /api/leaderboard/friends/?metric=all_time|streak|elo&limit=20

    Rankings scoped to the authenticated user's confirmed friend network
    (the user themselves is included, and their comparative rank is returned
    via ``meta.my_rank`` / ``meta.total_users``).
    """

    METRICS = ('all_time', 'streak', 'elo')

    def get(self, request):
        me = _me(request)
        metric = request.query_params.get('metric', 'all_time')
        if metric not in self.METRICS:
            return Response(
                {'error': f'metric must be one of {list(self.METRICS)}'},
                status=400,
            )
        try:
            limit = int(request.query_params.get('limit', 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        friend_ids = Friendship.friend_ids(me)
        friend_ids.add(me.pk)

        profiles = {
            p.user_id: p
            for p in UserProfile.objects.select_related('user')
            .filter(user_id__in=friend_ids)
        }

        entries = []
        if metric == 'streak':
            ordered = sorted(
                profiles.values(),
                key=lambda p: (-p.current_streak, -p.longest_streak),
            )
            for rank, p in enumerate(ordered, start=1):
                entries.append(self._row(rank, p, p.current_streak, metric, me))
        elif metric == 'elo':
            ordered = sorted(profiles.values(), key=lambda p: -p.elo_rating)
            for rank, p in enumerate(ordered, start=1):
                entries.append(self._row(rank, p, round(p.elo_rating, 1), metric, me))
        else:  # all_time — total correct answers across every daily quiz played
            totals = {
                row['user_id']: row
                for row in DailyQuizSession.objects.filter(user_id__in=friend_ids)
                .values('user_id')
                .annotate(
                    total=Coalesce(Sum('score'), 0),
                    total_time=Coalesce(Sum('total_time_sec'), 0.0),
                )
            }
            ordered = sorted(
                totals.values(),
                key=lambda r: (-r['total'], r['total_time']),
            )
            for rank, row in enumerate(ordered, start=1):
                p = profiles.get(row['user_id'])
                if p is None:
                    continue
                entries.append(self._row(rank, p, row['total'], metric, me))

        my_rank = next(
            (e['rank'] for e in entries if e.get('is_me')), None
        )
        return Response({
            'scope': 'friends',
            'metric': metric,
            'leaderboard': entries[:limit],
            'meta': {
                'metric': metric,
                'total_users': len(entries),
                'my_rank': my_rank,
            },
        })

    def _row(self, rank, profile, value, metric, me):
        return {
            'rank': rank,
            'is_me': profile.user_id == me.pk,
            'username': profile.user.username,
            'user_id': profile.user_id,
            'avatar': profile.avatar,
            'avatar_emoji': profile.avatar_emoji,
            'gk_skill_tier': profile.gk_skill_tier,
            'current_streak': profile.current_streak,
            'longest_streak': profile.longest_streak,
            'elo_rating': round(profile.elo_rating, 1),
            'metric': metric,
            'metric_value': value,
        }
