from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UploadedPDF(models.Model):
    """Represents an uploaded PDF document."""
    file = models.FileField(upload_to='uploads/pdfs/')
    raw_text = models.TextField(blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"Document #{self.id} - {self.file.name}"

    class Meta:
        ordering = ['-uploaded_at']


class UserProfile(models.Model):
    """Extends Django User with Elo rating and stats."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # 0-based Elo scale: every new learner starts at 0.
    elo_rating = models.FloatField(default=0.0)
    total_questions_answered = models.IntegerField(default=0)
    total_correct = models.IntegerField(default=0)
    streak = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Profile (Elo: {self.elo_rating})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class Question(models.Model):
    """A multiple-choice question generated from a document."""
    document = models.ForeignKey(
        UploadedPDF,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_text = models.TextField()
    options = models.JSONField(default=list)  # List of 4 option strings
    correct_index = models.IntegerField(default=0)  # 0-3
    explanation = models.TextField(blank=True, default='')
    # 0-based Elo-style difficulty rating (default = neutral / unknown).
    difficulty_rating = models.FloatField(default=0.0)
    difficulty_label = models.CharField(max_length=10, default='medium')  # easy/medium/hard
    times_served = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q#{self.id}: {self.question_text[:50]}..."

    class Meta:
        ordering = ['created_at']


class Flashcard(models.Model):
    """A flashcard generated from a document."""
    document = models.ForeignKey(
        UploadedPDF,
        on_delete=models.CASCADE,
        related_name='flashcards'
    )
    front = models.TextField()
    back = models.TextField()
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Card #{self.order}: {self.front[:50]}..."

    class Meta:
        ordering = ['order']


class Summary(models.Model):
    """A structured summary generated from a document."""
    document = models.OneToOneField(
        UploadedPDF,
        on_delete=models.CASCADE,
        related_name='summary'
    )
    executive_summary = models.TextField(blank=True)
    key_concepts = models.JSONField(default=list)
    terminology = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.document.file.name}"

    class Meta:
        ordering = ['-created_at']


class TestSession(models.Model):
    """A test session tracking Elo progression.

    Supports user-defined quiz length:

    - ``requested_questions`` is the N the user chose.
    - ``questions_generated_count`` is the 2N raw LLM pool size.
    - ``questions_answered_count`` increments with each submitted answer and
      is what ends the session (NOT the generated pool).

    Unused generated questions stay in the DB but are never served in this
    session and are NOT counted as 'questions_attempted' for ML features.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_sessions')
    document = models.ForeignKey(UploadedPDF, on_delete=models.CASCADE, related_name='test_sessions')
    start_elo = models.FloatField(default=0.0)  # 0-based Elo scale
    end_elo = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # ── User-defined quiz length ──
    requested_questions = models.IntegerField(
        null=True, blank=True,
        help_text='N the user requested to answer (None = legacy serve all generated).'
    )
    questions_generated_count = models.IntegerField(
        default=0,
        help_text='Size of the raw 2N LLM question pool for this session.'
    )
    questions_answered_count = models.IntegerField(
        default=0,
        help_text='How many questions this user has actually answered in this session.'
    )

    def __str__(self):
        return f"Session #{self.id} for {self.user.username}"

    class Meta:
        ordering = ['-created_at']


class SessionResponse(models.Model):
    """Records a single answer within a test session.

    The same question id must never appear twice in one session.
    """
    session = models.ForeignKey(
        TestSession,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_index = models.IntegerField()  # 0-3
    is_correct = models.BooleanField()
    time_taken_sec = models.FloatField(default=0.0)
    user_elo_before = models.FloatField(default=0.0)  # 0-based Elo scale
    user_elo_after = models.FloatField(default=0.0)
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session#{self.session.id} - Q#{self.question.id}"

    class Meta:
        ordering = ['answered_at']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'question'],
                name='uniq_session_question_once_pages',
            ),
        ]
