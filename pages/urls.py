from django.urls import path
from . import views

urlpatterns = [
    # REST API — Document Management
    path('documents/upload/', views.api_upload_document, name='api_upload_document'),
    path('documents/<int:doc_id>/summary/', views.api_generate_summary, name='api_generate_summary'),
    path('documents/<int:doc_id>/flashcards/', views.api_generate_flashcards, name='api_generate_flashcards'),

    # REST API — Adaptive Test
    path('test/generate-bank/', views.api_generate_question_bank, name='api_generate_question_bank'),
    path('test/start/', views.api_test_start, name='api_test_start'),
    path('test/submit-answer/', views.api_test_submit_answer, name='api_test_submit_answer'),
    path('test/complete/', views.api_test_complete, name='api_test_complete'),
]
