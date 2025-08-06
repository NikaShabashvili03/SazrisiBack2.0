from quiz.models.quiz import Quiz, QuizAttempt, Question, UserAnswer, Topic
from rest_framework import serializers

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['name', 'url']

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'score', 'order']


class QuestionWithCorrectSerializer(serializers.ModelSerializer):
    user_answer = serializers.SerializerMethodField()
    topic = TopicSerializer()

    class Meta:
        model = Question
        fields = ['id', 'explanation', 'score', 'order', 'answer', 'user_answer', 'topic']

    def get_user_answer(self, obj):
        attempt_id = self.context.get("attempt_id")

        if not attempt_id:
            return None

        try:
            user_answer = UserAnswer.objects.get(attempt__id=attempt_id, question=obj)
            return UserAnswerSerializer(user_answer).data
        except UserAnswer.DoesNotExist:
            return None
    

class QuizSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()
    total_score = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField()
    
    file = serializers.FileField(required=False, allow_null=True) 

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'category',
            'time_limit', 'total_questions', 'total_score',
            'created_at', 'attempt', 'file'
        ]

    def get_total_questions(self, obj):
        return obj.get_total_questions()

    def get_total_score(self, obj):
        return obj.get_total_score()

    def get_attempt(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            attempt = obj.attempts.filter(user=request.user).order_by('-started_at').first()
            if attempt:
                return QuizAttemptSerializer(attempt).data
        return None

class QuizAttemptSerializer(serializers.ModelSerializer):
    remaining_time = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'status', 'score', 'total_questions', 'correct_answers',
                 'percentage', 'started_at', 'completed_at', 'time_taken',
                 'remaining_time'
                 ]
    
    def get_remaining_time(self, obj):
        return obj.get_remaining_time_from_answers()
        
class UserAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnswer
        fields = ['id', 'selected_answer', 'is_correct', 
                 'answered_at', 'time_taken']