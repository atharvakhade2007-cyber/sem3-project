from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase, override_settings

from .models import UserProfile


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    # ── Signup ──────────────────────────────────────────────────

    def test_signup_creates_user_and_profile(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'alice',
            'email': 'alice@example.com',
            'password': 'StrongPass1!',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='alice').exists())
        self.assertTrue(UserProfile.objects.filter(user__username='alice').exists())
        self.assertIn('access', res.data)
        # Refresh token lives in an httpOnly cookie
        cookie = res.cookies.get('refresh_token')
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie.get('httponly', False))

    def test_signup_rejects_weak_password(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'bob',
            'email': 'bob@example.com',
            'password': 'short',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)

    def test_signup_rejects_password_without_symbol(self):
        res = self.client.post('/api/auth/signup/', {
            'username': 'carol',
            'email': 'carol@example.com',
            'password': 'OnlyLettersAndDigits123',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)

    def test_signup_rejects_duplicate_username_and_email(self):
        User.objects.create_user('dave', 'dave@example.com', 'StrongPass1!')
        res = self.client.post('/api/auth/signup/', {
            'username': 'dave',
            'email': 'other@example.com',
            'password': 'StrongPass1!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', res.data)

        res = self.client.post('/api/auth/signup/', {
            'username': 'other',
            'email': 'dave@example.com',
            'password': 'StrongPass1!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res.data)

    # ── Login ───────────────────────────────────────────────────

    def test_login_username_and_email(self):
        User.objects.create_user('erin', 'erin@example.com', 'StrongPass1!')
        for identifier in ['erin', 'erin@example.com']:
            res = self.client.post('/api/auth/login/', {
                'username_or_email': identifier,
                'password': 'StrongPass1!',
            })
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertIn('access', res.data)
            self.assertEqual(res.data['user']['username'], 'erin')
            self.assertIsNotNone(res.cookies.get('refresh_token'))

    def test_login_wrong_password(self):
        User.objects.create_user('frank', 'frank@example.com', 'StrongPass1!')
        res = self.client.post('/api/auth/login/', {
            'username_or_email': 'frank',
            'password': 'WrongPass1!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Refresh / Logout / blacklist ────────────────────────────

    def test_refresh_rotates_token_and_logout_blacklists(self):
        User.objects.create_user('grace', 'grace@example.com', 'StrongPass1!')
        login = self.client.post('/api/auth/login/', {
            'username_or_email': 'grace',
            'password': 'StrongPass1!',
        })
        old_refresh = login.cookies['refresh_token'].value

        # Refreshing rotates the refresh cookie
        refresh_res = self.client.post('/api/auth/refresh/')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_res.data)
        new_refresh = refresh_res.cookies['refresh_token'].value
        self.assertNotEqual(new_refresh, old_refresh)

        # Old refresh is blacklisted → refresh with it fails
        self.client.cookies.clear()
        self.client.cookies['refresh_token'] = old_refresh
        res = self.client.post('/api/auth/refresh/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Logout blacklists the active refresh and clears the cookie
        self.client.cookies.clear()
        self.client.cookies['refresh_token'] = new_refresh
        logout = self.client.post('/api/auth/logout/')
        self.assertEqual(logout.status_code, status.HTTP_200_OK)
        # Cookie is cleared (empty value = deleted marker)
        self.assertEqual(
            self.client.cookies['refresh_token'].value, ''
        )

        # The blacklisted refresh can no longer be used
        self.client.cookies['refresh_token'] = new_refresh
        res = self.client.post('/api/auth/refresh/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Profile ─────────────────────────────────────────────────

    def test_profile_requires_auth(self):
        res = self.client.get('/api/user/profile/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def _authed_client(self):
        User.objects.create_user('henry', 'henry@example.com', 'StrongPass1!')
        login = self.client.post('/api/auth/login/', {
            'username_or_email': 'henry',
            'password': 'StrongPass1!',
        })
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client, login.data['user']

    def test_profile_get_returns_stats(self):
        client, _ = self._authed_client()
        res = client.get('/api/user/profile/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['username'], 'henry')
        self.assertIn('current_streak', res.data)
        self.assertIn('total_quizzes_completed', res.data)
        self.assertEqual(res.data['avatar'], 'owl')

    def test_profile_update(self):
        client, _ = self._authed_client()
        res = client.patch('/api/user/profile/update/', {
            'bio': 'Learning every day!',
            'avatar': 'rocket',
            'username': 'henry2',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['bio'], 'Learning every day!')
        self.assertEqual(res.data['avatar'], 'rocket')
        self.assertEqual(res.data['username'], 'henry2')

    def test_profile_update_rejects_duplicate_email(self):
        User.objects.create_user('other', 'other@example.com', 'StrongPass1!')
        client, _ = self._authed_client()
        res = client.patch('/api/user/profile/update/', {
            'email': 'other@example.com',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', res.data)

    # ── Change password ─────────────────────────────────────────

    def test_change_password(self):
        client, _ = self._authed_client()
        res = client.post('/api/user/change-password/', {
            'old_password': 'StrongPass1!',
            'new_password': 'NewStrongPass2@',
            'confirm_password': 'NewStrongPass2@',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            User.objects.get(username='henry').check_password('NewStrongPass2@')
        )

    def test_change_password_wrong_old(self):
        client, _ = self._authed_client()
        res = client.post('/api/user/change-password/', {
            'old_password': 'NopeWrong1!',
            'new_password': 'NewStrongPass2@',
            'confirm_password': 'NewStrongPass2@',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Password reset (dev stub) ───────────────────────────────

    @override_settings(DEBUG=True)
    def test_password_reset_flow(self):
        User.objects.create_user('iris', 'iris@example.com', 'StrongPass1!')
        res = self.client.post('/api/auth/password-reset/', {
            'email': 'iris@example.com',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # DEBUG=True → dev_reset payload with uid/token
        dev = res.data.get('dev_reset')
        self.assertIsNotNone(dev)

        confirm = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': dev['uid'],
            'token': dev['token'],
            'new_password': 'ResetPass3#',
        }, format='json')
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertTrue(
            User.objects.get(username='iris').check_password('ResetPass3#')
        )

    def test_password_reset_confirm_bad_token(self):
        User.objects.create_user('jack', 'jack@example.com', 'StrongPass1!')
        res = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': 'MQ==',  # pk=1 (may not exist) → invalid link
            'token': 'bogus',
            'new_password': 'ResetPass3#',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Auth enforcement on existing endpoints ──────────────────

    def test_existing_endpoints_require_auth(self):
        res = self.client.get('/api/v2/daily-quiz/leaderboard/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        res = self.client.post('/api/documents/upload/', {}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)