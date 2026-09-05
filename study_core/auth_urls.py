from django.urls import path

from . import auth_views

app_name = 'study_core_auth'

urlpatterns = [
    path('signup/', auth_views.SignupView.as_view(), name='auth-signup'),
    path('login/', auth_views.LoginView.as_view(), name='auth-login'),
    path('logout/', auth_views.LogoutView.as_view(), name='auth-logout'),
    path('refresh/', auth_views.RefreshView.as_view(), name='auth-refresh'),
    path(
        'password-reset/',
        auth_views.PasswordResetRequestView.as_view(),
        name='auth-password-reset',
    ),
    path(
        'password-reset-confirm/',
        auth_views.PasswordResetConfirmView.as_view(),
        name='auth-password-reset-confirm',
    ),
]