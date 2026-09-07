from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v2/", include("study_core.urls")),
    path("api/auth/", include("study_core.auth_urls")),
    path("api/user/", include("study_core.user_urls")),
    path("api/social/", include("study_core.social_urls")),
    path("api/challenges/", include("study_core.challenge_urls")),
    path("api/leaderboard/", include("study_core.leaderboard_urls")),
]

# Serve React frontend for all non-API, non-admin routes
# This catch-all must be last
urlpatterns += [
    re_path(r'^(?!api/|admin/).*$', TemplateView.as_view(template_name='index.html'), name='react-app'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static('/static/react_build/', document_root='study_core/static/react_build/')
