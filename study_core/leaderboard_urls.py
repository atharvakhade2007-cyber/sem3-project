from django.urls import path

from .views import leaderboard

app_name = 'study_core_leaderboard'

urlpatterns = [
    path('friends/', leaderboard.FriendLeaderboardView.as_view(), name='leaderboard-friends'),
]
