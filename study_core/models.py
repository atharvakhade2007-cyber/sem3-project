import uuid
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """OneToOne extension of Django User with Elo rating and gamification stats."""

    class GKTier(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class Avatar(models.TextChoices):
        """Predefined avatar selector — stored as a key, rendered as an emoji."""
        OWL = 'owl', '🦉 Wise Owl'
        ROCKET = 'rocket', '🚀 Rocket'
        BRAIN = 'brain', '🧠 Brainiac'
        BOOKS = 'books', '📚 Bookworm'
        BOLT = 'bolt', '⚡ Speedster'
        TARGET = 'target', '🎯 Sharpshooter'
        WAVE = 'wave', '🌊 Deep Thinker'
        FIRE = 'fire', '🔥 Streak Master'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='study_profile'
    )
    bio = models.TextField(
        blank=True, default='', max_length=300,
        help_text='Short bio shown on your public profile (max 300 chars).'
    )
    avatar = models.CharField(
        max_length=20,
        choices=Avatar.choices,
        default=Avatar.OWL,
    )
    # 0-based Elo scale: every new learner starts at 0.
    elo_rating = models.FloatField(default=0.0)
    total_questions_answered = models.IntegerField(default=0)

    # ── Daily Quiz gamification ──
    gk_skill_tier = models.CharField(
        max_length=10,
        choices=GKTier.choices,
        default=GKTier.MEDIUM,
        help_text='Adaptive GK difficulty tier served to this user.'
    )
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_quiz_completed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} (Elo: {self.elo_rating:.0f}, Streak: {self.current_streak})"

    @property
    def avatar_emoji(self):
        """Render the stored avatar key as its emoji only."""
        return dict(self.Avatar.choices).get(self.avatar, '🦉').split(' ', 1)[0]

    @property
    def total_quizzes_completed(self):
        """Total completed quizzes (daily quiz attempts + adaptive test sessions)."""
        return (
            DailyQuizSession.objects.filter(user=self.user).count()
            + TestSession.objects.filter(user=self.user, is_completed=True).count()
        )

    class Meta:
        indexes = [
            models.Index(fields=['elo_rating']),
            models.Index(fields=['current_streak', 'longest_streak']),
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
    # 0-based Elo-style difficulty rating (default = neutral / unknown).
    difficulty_rating = models.FloatField(default=0.0)
    times_served = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)

    @property
    def difficulty_label(self) -> str:
        """Derived easy/medium/hard from the Elo difficulty rating.

        Kept as a property (not a DB column) so the serializers and review
        payloads that expose `difficulty_label` work without a migration.
        """
        from study_core.services.adaptive_engine import AdaptiveEloEngine
        return AdaptiveEloEngine.get_difficulty_label(self.difficulty_rating)

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
    start_elo = models.FloatField(default=0.0)  # 0-based Elo scale
    end_elo = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f"Session {self.id} ({self.user.username})"

    class Meta:
        ordering = ['-created_at', '-id']
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
    user_elo_after = models.FloatField(default=0.0)  # 0-based Elo scale
    question_elo_after = models.FloatField(default=0.0)

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
    """A multiple-choice question belonging to a daily quiz.

    Each daily quiz stores 20 questions:
    - 5 Current Affairs questions (category='current_affairs'), identical for
      every user — these are universally shared each day.
    - 15 GK questions (category='gk'), 5 per static difficulty tier
      (easy/medium/hard). The /today/ endpoint serves the 5 GK questions
      matching the user's optimal tier, chosen by the 1PL IRT engine from
      their persistent Elo rating and synced onto gk_skill_tier.
    """

    class Category(models.TextChoices):
        CURRENT_AFFAIRS = 'current_affairs', 'Current Affairs'
        GK = 'gk', 'General Knowledge'

    class DifficultyTier(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    quiz = models.ForeignKey(
        DailyQuiz, on_delete=models.CASCADE, related_name='questions'
    )
    question_text = models.TextField()
    options = models.JSONField(default=list)  # List of exactly 4 strings
    correct_index = models.IntegerField(default=0)  # 0-3
    explanation = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GK,
    )
    difficulty_tier = models.CharField(
        max_length=10,
        choices=DifficultyTier.choices,
        null=True,
        blank=True,
        help_text='Static difficulty for GK questions (None for Current Affairs).'
    )

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:60]}..."

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['quiz', 'category', 'difficulty_tier']),
        ]


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


class DailyQuizAnswer(models.Model):
    """A single locked, graded answer in today's daily quiz run.

    Recorded the moment the user answers a question (via the per-question
    check endpoint) so instant feedback can be shown without making the final
    score gameable: once a question is answered it is immutable — the user
    cannot retry after seeing the correct answer. The submission is then
    graded exclusively from these rows.

    Unanswered questions (skipped / timeout) simply have no row.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='daily_quiz_answers'
    )
    quiz = models.ForeignKey(
        DailyQuiz, on_delete=models.CASCADE, related_name='recorded_answers'
    )
    question = models.ForeignKey(
        DailyQuestion, on_delete=models.CASCADE, related_name='recorded_answers'
    )
    selected_index = models.IntegerField()  # 0-3, locked forever
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.user.username} — {self.quiz.date} "
            f"Q{self.question.order}: {'✓' if self.is_correct else '✗'}"
        )

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'quiz', 'question'],
                name='uniq_user_quiz_question_answer',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'quiz']),
        ]


# ═══════════════════════════════════════════════
#  Social Graph & Direct Challenges
# ═══════════════════════════════════════════════


class Friendship(models.Model):
    """One row per unordered pair of users — friendship is stored symmetrically.

    State machine: pending → accepted | declined, plus blocked.

    Canonicalisation: ``sender`` is always the user with the LOWER pk and
    ``receiver`` the HIGHER pk (enforced by a DB CheckConstraint + swap in
    save()). This makes the UNIQUE(sender, receiver) constraint meaningful and
    makes it impossible to store A→B and B→A as two distinct rows. The
    direction of a pending request lives in ``initiator``.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        BLOCKED = 'blocked', 'Blocked'

    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='friendship_as_sender'
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='friendship_as_receiver'
    )
    initiator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='friendship_initiated',
        help_text='User who sent the request (or who performed the block).'
    )
    blocker = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='friendship_blocks',
        help_text='Set when status=blocked — the user who issued the block.'
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Canonicalise the unordered pair so (sender, receiver) is unique.
        if self.sender_id > self.receiver_id:
            self.sender_id, self.receiver_id = self.receiver_id, self.sender_id
        super().save(*args, **kwargs)

    def counterpart(self, user):
        """Return the other user of the pair (falls back to sender if unknown)."""
        if self.sender_id == user.pk:
            return self.receiver
        return self.sender

    # ── Class helpers ──────────────────────────────────────

    @classmethod
    def friend_ids(cls, user):
        """Pks of every confirmed friend of ``user`` (symmetrical, one row)."""
        ids = set(cls.objects.filter(
            models.Q(sender=user) | models.Q(receiver=user),
            status=cls.Status.ACCEPTED,
        ).values_list('sender_id', 'receiver_id'))
        result = set()
        for s, r in ids:
            result.add(r if s == user.pk else s)
        return result

    @classmethod
    def are_friends(cls, a, b):
        if a.pk == b.pk:
            return False
        return cls.objects.filter(
            models.Q(sender=a, receiver=b) | models.Q(sender=b, receiver=a),
            status=cls.Status.ACCEPTED,
        ).exists()

    @classmethod
    def relationship_between(cls, a, b):
        """Return the Friendship row spanning a/b (any status) or None."""
        if a.pk == b.pk:
            return None
        return cls.objects.filter(
            models.Q(sender=a, receiver=b) | models.Q(sender=b, receiver=a),
        ).first()

    @classmethod
    def is_blocked(cls, a, b):
        row = cls.relationship_between(a, b)
        return row is not None and row.status == cls.Status.BLOCKED

    def __str__(self):
        return f"{self.sender.username} ↔ {self.receiver.username}: {self.status}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sender', 'receiver'],
                name='uniq_friendship_pair',
            ),
            models.CheckConstraint(
                check=models.Q(sender_id__lt=models.F('receiver_id')),
                name='friendship_canonical_order',
            ),
        ]
        indexes = [
            models.Index(fields=['sender', 'status']),
            models.Index(fields=['receiver', 'status']),
        ]


class QuizChallenge(models.Model):
    """An asynchronous 1v1 duel over an identical fixed question set.

    The challenger completes an adaptive PDF test session first; the answered
    question ids are snapshotted into ``question_ids`` so the challenged user
    later answers the exact same questions. Scoring is correctness count, with
    total time as the tiebreaker.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'

    session = models.ForeignKey(
        TestSession, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quiz_challenges',
        help_text="Challenger's completed adaptive session (the quiz instance)."
    )
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quiz_challenges',
    )
    challenger = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='duels_sent'
    )
    challenged_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='duels_received'
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    question_ids = models.JSONField(
        default=list, blank=True,
        help_text='Ordered snapshot of question ids the challenged user must answer.'
    )
    question_data = models.JSONField(
        default=list, blank=True,
        help_text=('Self-contained ordered snapshot of the duel questions '
                   '[{id, question_text, options, correct_index}] — grading is '
                   'independent of the originating document stack.')
    )
    document_filename = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Denormalised source document name shown in duel lists.'
    )
    challenger_score = models.IntegerField(default=0)
    challenged_score = models.IntegerField(null=True, blank=True)
    challenger_time_seconds = models.FloatField(default=0.0)
    challenged_time_seconds = models.FloatField(null=True, blank=True)
    winner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='duels_won',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return (
            f"{self.challenger.username} ⚔ {self.challenged_user.username}: "
            f"{self.status}"
        )

    @property
    def question_count(self):
        return len(self.question_data or self.question_ids or [])

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'challenged_user'],
                condition=models.Q(status='pending'),
                name='uniq_pending_challenge_pair',
            ),
        ]
        indexes = [
            models.Index(fields=['challenged_user', 'status']),
            models.Index(fields=['challenger', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
