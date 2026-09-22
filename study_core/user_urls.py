from django.urls import path

from .views import auth
from .views import analytics

app_name = 'study_core_user'

urlpatterns = [
    path('profile/', auth.ProfileView.as_view(), name='user-profile'),
    path(
        'profile/update/',
        auth.ProfileUpdateView.as_view(),
        name='user-profile-update',
    ),
    path(
        'change-password/',
        auth.ChangePasswordView.as_view(),
        name='user-change-password',
    ),
    path(
        'analytics/',
        analytics.UserAnalyticsView.as_view(),
        name='user-analytics',
    ),
]