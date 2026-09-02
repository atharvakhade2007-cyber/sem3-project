from django.contrib import admin
from .models import (
    UploadedPDF, Question, UserProfile, Flashcard, Summary,
    TestSession, SessionResponse,
)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ('question_text', 'options', 'correct_index', 'difficulty_label', 'difficulty_rating')
    readonly_fields = ('created_at',)


@admin.register(UploadedPDF)
class UploadedPDFAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'uploaded_at', 'processed', 'question_count')
    list_filter = ('processed', 'uploaded_at')
    search_fields = ('file',)
    inlines = [QuestionInline]

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Generated Questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'question_text_short', 'correct_index', 'difficulty_label', 'difficulty_rating', 'times_served', 'times_correct', 'created_at')
    list_filter = ('difficulty_label', 'created_at', 'document')
    search_fields = ('question_text',)
    readonly_fields = ('times_served', 'times_correct', 'created_at')

    def question_text_short(self, obj):
        return obj.question_text[:75] + "..." if len(obj.question_text) > 75 else obj.question_text
    question_text_short.short_description = 'Question Text'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'elo_rating', 'total_questions_answered', 'total_correct', 'streak')
    search_fields = ('user__username', 'user__email')


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'order', 'front_short')
    list_filter = ('document',)
    search_fields = ('front', 'back')

    def front_short(self, obj):
        return obj.front[:60] + "..." if len(obj.front) > 60 else obj.front
    front_short.short_description = 'Front'


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'created_at')


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'document', 'start_elo', 'end_elo', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'created_at')


@admin.register(SessionResponse)
class SessionResponseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'session', 'question', 'selected_index', 'is_correct',
        'time_taken_sec', 'user_elo_before', 'user_elo_after', 'answered_at'
    )
    list_filter = ('is_correct', 'answered_at')
    readonly_fields = ('answered_at',)
