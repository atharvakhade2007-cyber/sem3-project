"""study_core.views — view modules split by domain.

URL modules import from here (``from . import views`` then
``views.UploadDocumentView``), preserving the pre-refactor import style.
"""

from .auth import (
    SignupView,
    LoginView,
    LogoutView,
    RefreshView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ProfileView,
    ProfileUpdateView,
    ChangePasswordView,
    UserProfileView,
)
from .documents import (
    UploadDocumentView,
    DocumentSummaryView,
    DocumentFlashcardsView,
)
from .assessment import (
    TestStartView,
    TestSubmitAnswerView,
    TestCompleteView,
)
from .daily_quiz import (
    DailyQuizTodayView,
    DailyQuizCheckView,
    DailyQuizSubmitView,
    DailyQuizLeaderboardView,
)
from .social import (
    FriendsListView,
    FriendRequestsView,
    PendingCountView,
    SendFriendRequestView,
    RespondFriendRequestView,
    CancelFriendRequestView,
    ManageFriendView,
    SearchUsersView,
)
from .challenges import (
    CompletedSessionsView,
    ChallengeCreateView,
    ChallengeListView,
    ChallengeQuestionsView,
    ChallengeSubmitView,
)
from .leaderboard import FriendLeaderboardView
from .analytics import UserAnalyticsView

__all__ = [
    # auth
    'SignupView', 'LoginView', 'LogoutView', 'RefreshView',
    'PasswordResetRequestView', 'PasswordResetConfirmView',
    'ProfileView', 'ProfileUpdateView', 'ChangePasswordView',
    # documents
    'UploadDocumentView', 'DocumentSummaryView', 'DocumentFlashcardsView',
    # assessment
    'TestStartView', 'TestSubmitAnswerView', 'TestCompleteView',
    # daily quiz
    'DailyQuizTodayView', 'DailyQuizCheckView', 'DailyQuizSubmitView',
    'DailyQuizLeaderboardView',
    # social
    'FriendsListView', 'FriendRequestsView', 'PendingCountView',
    'SendFriendRequestView', 'RespondFriendRequestView',
    'CancelFriendRequestView', 'ManageFriendView', 'SearchUsersView',
    # challenges
    'CompletedSessionsView', 'ChallengeCreateView', 'ChallengeListView',
    'ChallengeQuestionsView', 'ChallengeSubmitView',
    # leaderboard / analytics
    'FriendLeaderboardView', 'UserAnalyticsView',
    'UserProfileView',
]
