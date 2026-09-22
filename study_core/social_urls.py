from django.urls import path

from .views import social

app_name = 'study_core_social'

urlpatterns = [
    path('friends/', social.FriendsListView.as_view(), name='social-friends'),
    path('requests/', social.FriendRequestsView.as_view(), name='social-requests'),
    path('pending-count/', social.PendingCountView.as_view(), name='social-pending-count'),
    path('request/send/', social.SendFriendRequestView.as_view(), name='social-request-send'),
    path('request/<int:pk>/respond/', social.RespondFriendRequestView.as_view(), name='social-request-respond'),
    path('request/<int:pk>/cancel/', social.CancelFriendRequestView.as_view(), name='social-request-cancel'),
    path('friends/manage/', social.ManageFriendView.as_view(), name='social-friends-manage'),
    path('users/search/', social.SearchUsersView.as_view(), name='social-users-search'),
]
