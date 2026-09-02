from rest_framework import serializers
from .models import (
    UserProfile,
    Document,
    Flashcard,
    Question,
    SharedChallenge,
    TestSession,
    SessionResponse,
)


# ──────────────────────────────────────────────
#  Model Serializers
# ──────────────────────────────────────────────


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'elo_rating', 'total_questions_answered']
        read_only_fields = ['elo_rating', 'total_questions_answered']


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
