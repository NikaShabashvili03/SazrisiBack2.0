from quiz.models.quiz import Quiz, QuizAttempt, Question, Answer, UserAnswer
from rest_framework import serializers


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'order']


class AnswerWithCorrectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'answer_text', 'is_correct', 'order']

class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'question_type', 'score', 'order', 'answers']


class QuestionWithCorrectSerializer(serializers.ModelSerializer):
    answers = AnswerWithCorrectSerializer(many=True, read_only=True)
    user_answer = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'question_type', 'explanation', 'score', 'order', 'answers', 'user_answer']

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
    category_title = serializers.CharField(source='category.title', read_only=True)
    is_tournament_active = serializers.ReadOnlyField()
    total_questions = serializers.SerializerMethodField()
    total_score = serializers.SerializerMethodField()
    attempt = serializers.SerializerMethodField() 

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'category', 'category_title', 'quiz_type',
            'difficulty', 'tournament_start_time', 'tournament_end_time',
            'time_limit', 'total_questions', 'total_score', 'is_tournament_active',
            'created_at', 'attempt'
        ]

    def get_total_questions(self, obj):
        return obj.get_total_questions()

    def get_total_score(self, obj):
        return obj.get_total_score()

    def get_attempt(self, obj):
        request = self.context.get('request')

        attempt = (
            obj.attempts
            .filter(user=request.user)
            .order_by('-started_at')
            .first()
        )

        if attempt:
            return QuizAttemptSerializer(attempt).data
        return None

class QuizAttemptSerializer(serializers.ModelSerializer):
    first_question_id = serializers.SerializerMethodField()
    last_question_id = serializers.SerializerMethodField()
    current_question_id = serializers.SerializerMethodField()
    remaining_time = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'status', 'score', 'total_questions', 'correct_answers',
                 'percentage', 'started_at', 'completed_at', 'time_taken',
                 'last_question_id', 'first_question_id', 'current_question_id', 'remaining_time'
                 ]
    
    def get_remaining_time(self, obj):
        return obj.get_remaining_time_from_answers()

    def get_current_question_id(self, obj):
        return obj.get_current_question_id()
    
    def get_first_question_id(self, obj):
        return obj.get_first_question_id()
    
    def get_last_question_id(self, obj):
        return obj.get_last_question_id()
        
class UserAnswerSerializer(serializers.ModelSerializer):
    selected_answers = AnswerWithCorrectSerializer(many=True, read_only=True)

    class Meta:
        model = UserAnswer
        fields = ['id', 'selected_answers', 'is_correct', 
                 'answered_at', 'time_taken']