from django.urls import path

from .views import challenges

app_name = 'study_core_challenges'

urlpatterns = [
    path('sessions/', challenges.CompletedSessionsView.as_view(), name='challenge-sessions'),
    path('create/', challenges.ChallengeCreateView.as_view(), name='challenge-create'),
    path('', challenges.ChallengeListView.as_view(), name='challenge-list'),
    path('<int:pk>/questions/', challenges.ChallengeQuestionsView.as_view(), name='challenge-questions'),
    path('<int:pk>/submit/', challenges.ChallengeSubmitView.as_view(), name='challenge-submit'),
]
