"""Shared helpers for all study_core view modules."""

from rest_framework.exceptions import AuthenticationFailed

from ..models import UserProfile


def _get_user(request):
    """Return the authenticated user or raise 401 (demo fallback removed)."""
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        return request.user
    raise AuthenticationFailed('Authentication required.')


# Alias used by the social/challenge/leaderboard modules (same semantics).
_me = _get_user


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _serialized_profile(user, context):
    """Public profile payload for a user, creating the row if missing."""
    from ..serializers import SocialProfileSerializer

    try:
        profile = user.study_profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    return SocialProfileSerializer(profile, context=context).data
