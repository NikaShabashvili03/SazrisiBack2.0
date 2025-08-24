from quiz.models.quiz import Quiz, QuizAttempt, Question, UserAnswer, Topic, BlackNote
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

class QuizResultSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    quiz_file = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_file', 'status', 'score', 'total_questions', 'correct_answers',
            'percentage', 'started_at', 'completed_at', 'time_taken',
            'questions'
        ]


    def get_quiz_file(self, obj):
            if obj.quiz.file:
                request = self.context.get('request')
                file_url = obj.quiz.file.url
                if request is not None:
                    return request.build_absolute_uri(file_url)
                return file_url
            return None
    
    def get_questions(self, obj):
        questions = obj.quiz.questions.all()
        return QuestionWithCorrectSerializer(
            questions, many=True, context={'attempt_id': obj.id}
        ).data

    
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
    quiz_file = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'status', 'score', 'total_questions', 'correct_answers',
                 'percentage', 'started_at', 'completed_at', 'time_taken',
                 'remaining_time', 'quiz_file'
                 ]
    
    def get_remaining_time(self, obj):
        return obj.get_remaining_time_from_answers()

    def get_quiz_file(self, obj):
            if obj.quiz.file:
                request = self.context.get('request')
                file_url = obj.quiz.file.url
                if request is not None:
                    return request.build_absolute_uri(file_url)
                return file_url
            return None
    
class UserAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnswer
        fields = ['id', 'selected_answer', 'is_correct', 
                 'answered_at', 'time_taken']
        
class BlackNoteSerializer(serializers.ModelSerializer):
    note = serializers.SerializerMethodField()

    class Meta:
        model = BlackNote
        fields = ["id", "attempt", "note", "created_at"]

    def get_note(self, obj):
        if obj.note and hasattr(obj.note, "url"):
            return obj.note.url
        return None
    

class BlackNoteCreateSerializer(serializers.Serializer):
    note = serializers.ImageField(required=True)