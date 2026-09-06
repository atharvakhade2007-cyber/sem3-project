from django.urls import path

from . import auth_views
from . import views_analytics

app_name = 'study_core_user'

urlpatterns = [
    path('profile/', auth_views.ProfileView.as_view(), name='user-profile'),
    path(
        'profile/update/',
        auth_views.ProfileUpdateView.as_view(),
        name='user-profile-update',
    ),
    path(
        'change-password/',
        auth_views.ChangePasswordView.as_view(),
        name='user-change-password',
    ),
    path(
        'analytics/',
        views_analytics.UserAnalyticsView.as_view(),
        name='user-analytics',
    ),
]