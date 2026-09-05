import re

from django.contrib.auth.models import User

from rest_framework import serializers

from django.utils import timezone
from datetime import timedelta

from .models import (
    UserProfile,
    Document,
    Flashcard,
    Question,
    SharedChallenge,
    TestSession,
    SessionResponse,
    Friendship,
    QuizChallenge,
)


# ──────────────────────────────────────────────
#  Model Serializers
# ──────────────────────────────────────────────


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile payload returned to the authenticated user."""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar_emoji = serializers.CharField(read_only=True)
    skill_level = serializers.CharField(source='gk_skill_tier', read_only=True)
    total_quizzes_completed = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email', 'bio', 'avatar', 'avatar_emoji',
            'elo_rating', 'skill_level', 'gk_skill_tier',
            'total_questions_answered', 'total_quizzes_completed',
            'current_streak', 'longest_streak', 'last_quiz_completed_date',
            'created_at',
        ]
        read_only_fields = [
            'id', 'username', 'email', 'avatar_emoji', 'elo_rating',
            'skill_level', 'gk_skill_tier', 'total_questions_answered',
            'total_quizzes_completed', 'current_streak', 'longest_streak',
            'last_quiz_completed_date', 'created_at',
        ]


# ──────────────────────────────────────────────
#  Social / Public Profile Serializers
# ──────────────────────────────────────────────


class SocialProfileSerializer(serializers.ModelSerializer):
    """Public profile summary shown in friend lists, search, and duels."""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    avatar_emoji = serializers.CharField(read_only=True)
    online = serializers.SerializerMethodField()
    last_active = serializers.DateTimeField(
        source='user.last_login', read_only=True, default=None
    )

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'username', 'avatar', 'avatar_emoji',
            'gk_skill_tier', 'elo_rating', 'current_streak', 'longest_streak',
            'online', 'last_active',
        ]

    def get_online(self, obj):
        last = obj.user.last_login
        if last is None:
            return False
        return (timezone.now() - last) < timedelta(minutes=5)


class FriendshipSerializer(serializers.ModelSerializer):
    """A friendship row seen from the requesting user's perspective."""
    friend = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['id', 'status', 'created_at', 'friend', 'direction']

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def get_friend(self, obj):
        me = self._request_user()
        other = obj.receiver if obj.sender_id == me.pk else obj.sender
        try:
            profile = other.study_profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=other)
        return SocialProfileSerializer(profile, context=self.context).data

    def get_direction(self, obj):
        """'incoming' / 'outgoing' relative to the requesting user."""
        me = self._request_user()
        if obj.initiator_id == me.pk:
            return 'outgoing'
        return 'incoming'


# ──────────────────────────────────────────────
#  Challenge Serializers
# ──────────────────────────────────────────────


class QuizChallengeSerializer(serializers.ModelSerializer):
    """Duel row plus both participants' public summaries."""
    challenger = serializers.SerializerMethodField()
    challenged = serializers.SerializerMethodField()
    challenger_username = serializers.CharField(source='challenger.username', read_only=True)
    challenged_username = serializers.CharField(
        source='challenged_user.username', read_only=True
    )

    def _profile(self, user):
        try:
            profile = user.study_profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
        return SocialProfileSerializer(profile, context=self.context).data

    def get_challenger(self, obj):
        return self._profile(obj.challenger)

    def get_challenged(self, obj):
        return self._profile(obj.challenged_user)
    document_filename = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = QuizChallenge
        fields = [
            'id', 'role', 'status', 'is_expired',
            'challenger', 'challenged',
            'challenger_username', 'challenged_username',
            'document_filename', 'question_count',
            'challenger_score', 'challenged_score',
            'challenger_time_seconds', 'challenged_time_seconds',
            'winner', 'winner_username', 'created_at', 'expires_at',
            'completed_at',
        ]
        read_only_fields = fields

    question_count = serializers.SerializerMethodField()
    winner_username = serializers.SerializerMethodField()

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def get_role(self, obj):
        me = self._request_user()
        if me is None:
            return None
        if obj.challenger_id == me.pk:
            return 'outgoing'
        return 'incoming'

    def get_is_expired(self, obj):
        return (
            obj.status == obj.Status.PENDING
            and obj.expires_at <= timezone.now()
        )

    def get_question_count(self, obj):
        return obj.question_count

    def get_document_filename(self, obj):
        if obj.document_filename:
            return obj.document_filename
        if obj.document_id:
            return obj.document.filename
        return 'Study session'

    def get_winner_username(self, obj):
        return obj.winner.username if obj.winner_id else None


class ChallengeCreateSerializer(serializers.Serializer):
    # Session ids come from either stack: legacy pages (integer) or
    # study_core (UUID) — accept both as a plain string.
    session_id = serializers.CharField(max_length=64)
    challenged_user_id = serializers.IntegerField()


class ChallengeQuestionAnswerSerializer(serializers.Serializer):
    # Question ids mirror the originating stack (int for legacy, UUID for
    # study_core) — accept either as a string.
    question_id = serializers.CharField(max_length=64)
    selected_index = serializers.IntegerField(min_value=0, max_value=3)
    time_taken_sec = serializers.FloatField(min_value=0.0)


class ChallengeSubmitSerializer(serializers.Serializer):
    answers = ChallengeQuestionAnswerSerializer(many=True)


# ──────────────────────────────────────────────
#  Auth Serializers (signup / login / reset / password)
# ──────────────────────────────────────────────


def validate_password_strength(value):
    """Require ≥8 chars with letters, digits, and at least one symbol."""
    errors = []
    if len(value) < 8:
        errors.append('Password must be at least 8 characters long.')
    if not re.search(r'[A-Za-z]', value):
        errors.append('Password must contain at least one letter.')
    if not re.search(r'\d', value):
        errors.append('Password must contain at least one number.')
    if not re.search(r'[^A-Za-z0-9]', value):
        errors.append('Password must contain at least one symbol (e.g. !@#$).')
    if errors:
        raise serializers.ValidationError(errors)
    return value


class SignupSerializer(serializers.Serializer):
    """Registration: validates username/email/password, provisions UserProfile."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'An account with this email already exists.'
            )
        return value

    def validate_password(self, value):
        return validate_password_strength(value)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'].lower(),
            password=validated_data['password'],
        )
        # UserProfile is auto-provisioned by the post_save signal in
        # study_core/signals.py — no explicit create needed here.
        return user


class LoginSerializer(serializers.Serializer):
    """Login payload — username OR email accepted."""
    username_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        return validate_password_strength(value)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        return validate_password_strength(value)

    def validate(self, attrs):
        if attrs.get('new_password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.',
            })
        return attrs


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """PATCH /profile/update — username, email, bio, avatar."""
    username = serializers.CharField(source='user.username', max_length=150, required=False)
    email = serializers.EmailField(source='user.email', required=False)

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'bio', 'avatar']
        extra_kwargs = {
            'bio': {'max_length': 300, 'required': False, 'allow_blank': True},
            'avatar': {'required': False},
        }

    def validate_username(self, value):
        user = self.instance.user
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        user = self.instance.user
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                'An account with this email already exists.'
            )
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        if user_data:
            instance.user.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'filename', 'created_at']
        read_only_fields = ['id', 'created_at']


class DocumentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id', 'filename', 'raw_text', 'summary_data',
            'created_at',
        ]
        read_only_fields = ['id', 'raw_text', 'summary_data', 'created_at']


class FlashcardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flashcard
        fields = ['id', 'front', 'back']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'options', 'correct_index',
            'explanation', 'difficulty_rating', 'difficulty_label',
        ]


class QuestionBriefSerializer(serializers.ModelSerializer):
    """Lightweight question serializer for during-test display (no answer)."""
    class Meta:
        model = Question
        fields = ['id', 'question_text', 'options', 'difficulty_label', 'difficulty_rating']


class SharedChallengeSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    document_filename = serializers.CharField(source='document.filename', read_only=True)

    class Meta:
        model = SharedChallenge
        fields = ['id', 'document', 'document_filename', 'creator', 'creator_username', 'is_active', 'created_at']
        read_only_fields = ['id', 'creator', 'is_active', 'created_at']


class TestSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSession
        fields = ['id', 'user', 'document', 'challenge', 'start_elo', 'end_elo', 'is_completed']
        read_only_fields = ['id', 'user', 'start_elo', 'end_elo', 'is_completed']


class SessionResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionResponse
        fields = [
            'id', 'session', 'question', 'selected_index',
            'is_correct', 'time_taken_sec', 'user_elo_after',
            'question_elo_after',
        ]


# ──────────────────────────────────────────────
#  API Request / Response Serializers
# ──────────────────────────────────────────────


class UploadDocumentSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are supported.")
        return value


class StartTestSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()


class SubmitAnswerSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    question_id = serializers.UUIDField()
    selected_index = serializers.IntegerField(min_value=0, max_value=3)
    time_taken_sec = serializers.FloatField(min_value=0.0)


class CompleteTestSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()


class ShareDocumentSerializer(serializers.Serializer):
    """Empty serializer — share endpoint just needs the document UUID in the URL."""
    pass


class ChallengeStartSerializer(serializers.Serializer):
    """Empty serializer — challenge start uses UUID in URL."""
    pass


# ──────────────────────────────────────────────
#  Nested Response Serializers
# ──────────────────────────────────────────────


class SummaryResponseSerializer(serializers.Serializer):
    executive_summary = serializers.CharField()
    key_concepts = serializers.ListField(child=serializers.CharField())
    terminology = serializers.ListField(child=serializers.DictField())


class LeaderboardEntrySerializer(serializers.Serializer):
    username = serializers.CharField()
    start_elo = serializers.FloatField()
    end_elo = serializers.FloatField()
    elo_gained = serializers.FloatField()
    accuracy = serializers.FloatField()
    questions_answered = serializers.IntegerField()


class SendFriendRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class RespondFriendRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'decline', 'block'])


class ManageFriendSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['remove', 'block'])
