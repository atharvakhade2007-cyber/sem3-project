from django.urls import path

from . import leaderboard_views

app_name = 'study_core_leaderboard'

urlpatterns = [
    path('friends/', leaderboard_views.FriendLeaderboardView.as_view(), name='leaderboard-friends'),
]
