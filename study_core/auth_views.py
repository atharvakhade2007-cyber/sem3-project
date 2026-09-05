"""
JWT authentication endpoints (djangorestframework-simplejwt).

Design:
- Access tokens are short-lived, returned in the JSON body, and sent back by
  the client as `Authorization: Bearer <access>`.
- Refresh tokens are long-lived and stored ONLY in an httpOnly, SameSite=Lax
  cookie scoped to /api/auth/ (never exposed to JavaScript). They are rotated
  on every refresh; the previous one is blacklisted.
- Logout blacklists the active refresh token and clears the cookie.
"""
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)

logger = logging.getLogger(__name__)


# ── Cookie helpers ───────────────────────────────────────────────


def _refresh_cookie_name():
    return settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH']


def _refresh_cookie_params():
    jwt = settings.SIMPLE_JWT
    return {
        'httponly': jwt['AUTH_COOKIE_HTTP_ONLY'],
        'secure': jwt['AUTH_COOKIE_SECURE'],
        'samesite': jwt['AUTH_COOKIE_SAMESITE'],
        'path': jwt['AUTH_COOKIE_PATH'],
    }


def _set_refresh_cookie(response, refresh_token, remember_me=False):
    """Attach the refresh token as an httpOnly cookie.

    remember_me=True keeps it for the full REFRESH_TOKEN_LIFETIME; otherwise
    it becomes a session cookie that dies with the browser.
    """
    kwargs = _refresh_cookie_params()
    if remember_me:
        kwargs['max_age'] = int(
            settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
        )
    response.set_cookie(_refresh_cookie_name(), refresh_token, **kwargs)


def _clear_refresh_cookie(response):
    jwt = settings.SIMPLE_JWT
    response.delete_cookie(
        _refresh_cookie_name(),
        path=jwt['AUTH_COOKIE_PATH'],
        samesite=jwt['AUTH_COOKIE_SAMESITE'],
    )


def _profile_payload(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return UserProfileSerializer(profile).data


def _get_refresh_from_request(request):
    return request.COOKIES.get(_refresh_cookie_name())


# ── POST /api/auth/signup/ ───────────────────────────────────────


class SignupView(APIView):
    """Validate and create a user + linked UserProfile. Auto-logs in."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'access': str(refresh.access_token),
                'user': _profile_payload(user),
            },
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, str(refresh), remember_me=True)
        return response


# ── POST /api/auth/login/ ────────────────────────────────────────


class LoginView(APIView):
    """Validate credentials (username OR email), issue JWT pair."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data['username_or_email'].strip()
        password = serializer.validated_data['password']
        remember_me = serializer.validated_data['remember_me']

        # Resolve username-or-email to a username for Django's authenticate().
        username = identifier
        if '@' in identifier:
            try:
                username = User.objects.get(email__iexact=identifier).username
            except User.DoesNotExist:
                username = '__no_such_user__'

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'error': 'Invalid username/email or password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'access': str(refresh.access_token),
                'user': _profile_payload(user),
            },
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, str(refresh), remember_me=remember_me)
        return response


# ── POST /api/auth/logout/ ───────────────────────────────────────


class LogoutView(APIView):
    """Blacklist the active refresh token and clear the cookie.

    Uses AllowAny so logout works even if the access token has expired.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = _get_refresh_from_request(request)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError as e:
                logger.debug('Logout with unusable refresh token: %s', e)
        response = Response({'detail': 'Logged out successfully.'})
        _clear_refresh_cookie(response)
        return response


# ── POST /api/auth/refresh/ ──────────────────────────────────────


class RefreshView(APIView):
    """Rotate the refresh cookie and return a fresh access token.

    ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION mean each refresh
    invalidates the previous refresh token and issues a new one in the cookie.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = _get_refresh_from_request(request)
        if not refresh_token:
            return Response(
                {'error': 'No refresh token provided.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            refresh = RefreshToken(refresh_token)
        except TokenError as e:
            return Response(
                {'error': f'Invalid refresh token: {str(e)}'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION'):
            try:
                refresh.blacklist()
            except AttributeError:
                pass

        if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
            refresh.set_jti()
            refresh.set_exp()
            new_refresh = str(refresh)
        else:
            new_refresh = None

        response = Response({'access': str(refresh.access_token)})
        if new_refresh:
            _set_refresh_cookie(response, new_refresh, remember_me=True)
        return response


# ── Password reset (dev stub) ────────────────────────────────────


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/

    Dev-only stub: validates the email, generates a reset token, logs it, and
    (when settings.DEBUG) returns uid/token in the response so the confirm
    flow can be exercised without an email backend. Always returns the same
    public message so emails can't be enumerated.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        data = {
            'detail': 'If an account exists for that email, a reset link has been sent.',
        }

        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            logger.info(
                'Password reset requested for %s (uid=%s, token=%s)',
                user.username, uid, token,
            )
            if settings.DEBUG:
                data['dev_reset'] = {'uid': uid, 'token': token}

        return Response(data, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset-confirm/ — uid + token + new password."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, serializer.validated_data['token']):
            return Response(
                {'error': 'Invalid or expired reset link.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password has been reset. You can now sign in.'})


# ── Profile ──────────────────────────────────────────────────────


class ProfileView(APIView):
    """GET /api/user/profile/ — full profile incl. stats."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_profile_payload(request.user))


class ProfileUpdateView(APIView):
    """PATCH /api/user/profile/update/ — username, email, bio, avatar."""

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileUpdateSerializer(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_profile_payload(request.user))


class ChangePasswordView(APIView):
    """POST /api/user/change-password/ — validate old, set new."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'error': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password changed successfully.'})