from django.urls import path

from . import challenge_views

app_name = 'study_core_challenges'

urlpatterns = [
    path('sessions/', challenge_views.CompletedSessionsView.as_view(), name='challenge-sessions'),
    path('create/', challenge_views.ChallengeCreateView.as_view(), name='challenge-create'),
    path('', challenge_views.ChallengeListView.as_view(), name='challenge-list'),
    path('<int:pk>/questions/', challenge_views.ChallengeQuestionsView.as_view(), name='challenge-questions'),
    path('<int:pk>/submit/', challenge_views.ChallengeSubmitView.as_view(), name='challenge-submit'),
]
