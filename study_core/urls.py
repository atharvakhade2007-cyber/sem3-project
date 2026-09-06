from django.urls import path
from . import views

app_name = 'study_core'

urlpatterns = [
    # ── Content Generation ──
    path(
        'documents/upload/',
        views.UploadDocumentView.as_view(),
        name='document-upload',
    ),
    path(
        'documents/<uuid:doc_id>/summary/',
        views.DocumentSummaryView.as_view(),
        name='document-summary',
    ),
    path(
        'documents/<uuid:doc_id>/flashcards/',
        views.DocumentFlashcardsView.as_view(),
        name='document-flashcards',
    ),

    # ── Solo Testing Flow ──
    path(
        'test/start/',
        views.TestStartView.as_view(),
        name='test-start',
    ),
    path(
        'test/submit-answer/',
        views.TestSubmitAnswerView.as_view(),
        name='test-submit-answer',
    ),
    path(
        'test/complete/',
        views.TestCompleteView.as_view(),
        name='test-complete',
    ),

    # ── Social Sharing & Challenges ──
    path(
        'documents/<uuid:doc_id>/share/',
        views.DocumentShareView.as_view(),
        name='document-share',
    ),
    path(
        'challenge/<uuid:challenge_id>/',
        views.ChallengeDetailView.as_view(),
        name='challenge-detail',
    ),
    path(
        'challenge/<uuid:challenge_id>/start/',
        views.ChallengeStartView.as_view(),
        name='challenge-start',
    ),
    path(
        'challenge/<uuid:challenge_id>/leaderboard/',
        views.ChallengeLeaderboardView.as_view(),
        name='challenge-leaderboard',
    ),

    # ── User Profile ──
    path(
        'profile/',
        views.UserProfileView.as_view(),
        name='user-profile',
    ),
    # ── Daily GK Quiz ──
    path(
        'daily-quiz/today/',
        views.DailyQuizTodayView.as_view(),
        name='daily-quiz-today',
    ),
    path(
        'daily-quiz/check/',
        views.DailyQuizCheckView.as_view(),
        name='daily-quiz-check',
    ),
    path(
        'daily-quiz/submit/',
        views.DailyQuizSubmitView.as_view(),
        name='daily-quiz-submit',
    ),
    path(
        'daily-quiz/leaderboard/',
        views.DailyQuizLeaderboardView.as_view(),
        name='daily-quiz-leaderboard',
    ),
]
