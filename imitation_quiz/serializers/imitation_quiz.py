from rest_framework import serializers

from imitation_quiz.models.imitation_quiz import (
    ImitationQuiz,
    ImitationAttempt,
    ImitationQuestion,
    ImitationUserAnswer,
    ImitationTopic,
    ImitationAISummary,
)
from authentication.serializers.user import UserProfileSerializer


class ImitationTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImitationTopic
        fields = ['id', 'name', 'description', 'url']


class ImitationAISummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImitationAISummary
        fields = ['id', 'quiz_title', 'content', 'created_at']


class ImitationQuestionSerializer(serializers.ModelSerializer):
    topics = ImitationTopicSerializer(many=True, read_only=True)

    class Meta:
        model = ImitationQuestion
        fields = ['id', 'score', 'order', 'topics']


class ImitationUserAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImitationUserAnswer
        fields = [
            'id',
            'selected_answer',
            'is_correct',
            'score_earned',
            'answered_at',
            'time_taken',
        ]


class ImitationQuestionWithAnswerSerializer(serializers.ModelSerializer):
    user_answer = serializers.SerializerMethodField()
    topics = ImitationTopicSerializer(many=True, read_only=True)

    class Meta:
        model = ImitationQuestion
        fields = ['id', 'score', 'order', 'user_answer', 'topics']

    def get_user_answer(self, obj):
        attempt_id = self.context.get("attempt_id")
        if not attempt_id:
            return None

        try:
            user_answer = ImitationUserAnswer.objects.get(
                attempt__id=attempt_id,
                question=obj
            )
            return ImitationUserAnswerSerializer(user_answer).data
        except ImitationUserAnswer.DoesNotExist:
            return None


class ImitationAttemptSerializer(serializers.ModelSerializer):
    remaining_time = serializers.SerializerMethodField()
    quiz_file = serializers.SerializerMethodField()
    user = UserProfileSerializer()

    class Meta:
        model = ImitationAttempt
        fields = [
            'id',
            'code',
            'status',
            'score',
            'total_questions',
            'correct_answers',
            'percentage',
            'started_at',
            'completed_at',
            'time_taken',
            'remaining_time',
            'quiz_file',
            'user',
            'laptop_type',
        ]

    def get_remaining_time(self, obj):
        return obj.get_remaining_time_from_answers()

    def get_quiz_file(self, obj):
        if obj.imitation_quiz.file:
            request = self.context.get('request')
            file_url = obj.imitation_quiz.file.url
            if request:
                return request.build_absolute_uri(file_url)
            return file_url
        return None


class ImitationQuizSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()
    total_score = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    has_access = serializers.SerializerMethodField()

    class Meta:
        model = ImitationQuiz
        fields = [
            'id',
            'title',
            'description',
            'category',
            'time_limit',
            'location',
            'total_questions',
            'total_score',
            'created_at',
            'attempt',
            'file',
            'start_datetime',
            'end_datetime',
            'is_active',
            'max_space',
            'user_count',
            'is_valid_space',
            'available_laptops',
            'registered_laptops',
            'is_laptop_available',
            'is_paid',
            'price',
            'has_access',
        ]

    def get_total_questions(self, obj):
        return obj.get_total_questions()

    def get_total_score(self, obj):
        return obj.get_total_score()

    def get_has_access(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.has_access(user=request.user)
        return False

    def get_attempt(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            attempt = obj.attempts.filter(user=request.user).order_by('-started_at').first()
            if attempt:
                return ImitationAttemptSerializer(attempt, context={'request': request}).data
        return None


class CompletedImitationQuizSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()
    total_score = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    has_access = serializers.SerializerMethodField()

    class Meta:
        model = ImitationQuiz
        fields = [
            'id',
            'title',
            'description',
            'category',
            'time_limit',
            'location',
            'total_questions',
            'total_score',
            'created_at',
            'attempt',
            'file',
            'start_datetime',
            'end_datetime',
            'is_active',
            'max_space',
            'user_count',
            'is_valid_space',
            'available_laptops',
            'registered_laptops',
            'is_laptop_available',
            'is_paid',
            'price',
            'has_access',
        ]

    def get_total_questions(self, obj):
        return obj.get_total_questions()

    def get_total_score(self, obj):
        return obj.get_total_score()

    def get_has_access(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.has_access(user=request.user)
        return False

    def get_attempt(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            attempt = obj.attempts.filter(user=request.user).order_by('-started_at').first()
            if attempt:
                return ImitationAttemptSerializer(attempt, context={'request': request}).data
        return None


class ImitationQuizResultSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    quiz_file = serializers.SerializerMethodField()
    quiz_explanation = serializers.SerializerMethodField()

    class Meta:
        model = ImitationAttempt
        fields = [
            'id',
            'code',
            'status',
            'score',
            'total_questions',
            'correct_answers',
            'percentage',
            'started_at',
            'completed_at',
            'time_taken',
            'questions',
            'quiz_file',
            'quiz_explanation',
        ]

    def get_questions(self, obj):
        questions = obj.imitation_quiz.questions.prefetch_related('topics').all()
        return ImitationQuestionWithAnswerSerializer(
            questions,
            many=True,
            context={'attempt_id': obj.id}
        ).data

    def get_quiz_file(self, obj):
        request = self.context.get('request')
        if obj.imitation_quiz.file:
            url = obj.imitation_quiz.file.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_quiz_explanation(self, obj):
        request = self.context.get('request')
        if obj.imitation_quiz.explanation:
            url = obj.imitation_quiz.explanation.url
            return request.build_absolute_uri(url) if request else url
        return None