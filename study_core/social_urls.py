from django.urls import path

from . import social_views

app_name = 'study_core_social'

urlpatterns = [
    path('friends/', social_views.FriendsListView.as_view(), name='social-friends'),
    path('requests/', social_views.FriendRequestsView.as_view(), name='social-requests'),
    path('pending-count/', social_views.PendingCountView.as_view(), name='social-pending-count'),
    path('request/send/', social_views.SendFriendRequestView.as_view(), name='social-request-send'),
    path('request/<int:pk>/respond/', social_views.RespondFriendRequestView.as_view(), name='social-request-respond'),
    path('request/<int:pk>/cancel/', social_views.CancelFriendRequestView.as_view(), name='social-request-cancel'),
    path('friends/manage/', social_views.ManageFriendView.as_view(), name='social-friends-manage'),
    path('users/search/', social_views.SearchUsersView.as_view(), name='social-users-search'),
]
