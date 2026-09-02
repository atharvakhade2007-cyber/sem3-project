import uuid
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """OneToOne extension of Django User with Elo rating and stats."""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='study_profile'
    )
    elo_rating = models.FloatField(default=1200.0)
    total_questions_answered = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} (Elo: {self.elo_rating:.0f})"

    class Meta:
        indexes = [
            models.Index(fields=['elo_rating']),
        ]


class Document(models.Model):
    """A user-uploaded PDF document with extracted content and generated data."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='study_documents'
    )
    file = models.FileField(upload_to='study_documents/pdfs/')
    filename = models.CharField(max_length=255)
    raw_text = models.TextField(blank=True, default='')
    summary_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.id})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]


class Flashcard(models.Model):
    """A flashcard generated from a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='flashcards'
    )
    front = models.TextField()
    back = models.TextField()

    def __str__(self):
        return f"Card: {self.front[:50]}..."

    class Meta:
        ordering = ['id']


class Question(models.Model):
    """A multiple-choice question generated from a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='questions'
    )
    question_text = models.TextField()
    options = models.JSONField(default=list)  # List of exactly 4 strings
    correct_index = models.IntegerField(default=0)  # 0-3
    explanation = models.TextField(blank=True, default='')
    difficulty_rating = models.FloatField(default=1200.0)
    times_served = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)

    def __str__(self):
        return f"Q: {self.question_text[:60]}..."

    class Meta:
        ordering = ['difficulty_rating']
        indexes = [
            models.Index(fields=['document', 'difficulty_rating']),
        ]


class SharedChallenge(models.Model):
    """A shareable link allowing friends to take an adaptive test on a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='challenges'
    )
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_challenges'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Challenge {self.id} by {self.creator.username}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['id', 'is_active']),
        ]


class TestSession(models.Model):
    """A test session tracking Elo progression for a user on a document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='study_sessions'
    )
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='test_sessions'
    )
    challenge = models.ForeignKey(
        SharedChallenge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions'
    )
    start_elo = models.FloatField(default=1200.0)
    end_elo = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Session {self.id} ({self.user.username})"

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['challenge', 'user']),
        ]


class SessionResponse(models.Model):
    """Records a single answer within a test session."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        TestSession, on_delete=models.CASCADE, related_name='responses'
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='session_responses'
    )
    selected_index = models.IntegerField()  # 0-3
    is_correct = models.BooleanField()
    time_taken_sec = models.FloatField(default=0.0)
    user_elo_after = models.FloatField(default=1200.0)
    question_elo_after = models.FloatField(default=1200.0)

    def __str__(self):
        return f"Response in Session {self.session.id}"

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['session', 'question']),
        ]


# ═══════════════════════════════════════════════
#  Daily GK Quiz Models
# ═══════════════════════════════════════════════


class DailyQuiz(models.Model):
    """A single daily quiz available for one calendar day."""
    date = models.DateField(unique=True)
    title = models.CharField(max_length=255, default='Daily GK & Current Affairs')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Daily Quiz — {self.date}"

    class Meta:
        ordering = ['-date']


class DailyQuestion(models.Model):
    """A multiple-choice question belonging to a daily quiz."""
    quiz = models.ForeignKey(
        DailyQuiz, on_delete=models.CASCADE, related_name='questions'
    )
    question_text = models.TextField()
    options = models.JSONField(default=list)  # List of exactly 4 strings
    correct_index = models.IntegerField(default=0)  # 0-3
    explanation = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:60]}..."

    class Meta:
        ordering = ['order']


class DailyQuizSession(models.Model):
    """Records a user's attempt at today's daily quiz."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='daily_quiz_sessions'
    )
    quiz = models.ForeignKey(
        DailyQuiz, on_delete=models.CASCADE, related_name='sessions'
    )
    score = models.IntegerField(default=0)  # 0-10
    total_time_sec = models.FloatField(default=0.0)
    answers = models.JSONField(default=list)  # [{question_id, selected_index, is_correct}, ...]
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.quiz.date} — {self.score}/10"

    class Meta:
        ordering = ['-score', 'total_time_sec']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'quiz'],
                name='unique_user_quiz_daily'
            ),
        ]
        indexes = [
            models.Index(fields=['quiz', '-score', 'total_time_sec']),
        ]
