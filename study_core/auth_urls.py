from django.urls import path

from .views import auth

app_name = 'study_core_auth'

urlpatterns = [
    path('signup/', auth.SignupView.as_view(), name='auth-signup'),
    path('login/', auth.LoginView.as_view(), name='auth-login'),
    path('logout/', auth.LogoutView.as_view(), name='auth-logout'),
    path('refresh/', auth.RefreshView.as_view(), name='auth-refresh'),
    path(
        'password-reset/',
        auth.PasswordResetRequestView.as_view(),
        name='auth-password-reset',
    ),
    path(
        'password-reset-confirm/',
        auth.PasswordResetConfirmView.as_view(),
        name='auth-password-reset-confirm',
    ),
]