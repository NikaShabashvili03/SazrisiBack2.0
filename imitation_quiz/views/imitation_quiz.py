from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import models

from ..models.imitation_quiz import (
    ImitationQuiz, 
    ImitationAttempt, 
    ImitationQuestion, 
    ImitationUserAnswer
)
from ..serializers.imitation_quiz import (
    ImitationQuizSerializer, 
    ImitationAttemptSerializer, 
    ImitationQuestionSerializer, 
    ImitationQuizResultSerializer, 
    ImitationQuestionWithAnswerSerializer
)

class ImitationQuizListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, category_id):
        quizzes = ImitationQuiz.objects.filter(category_id=category_id)
        serializer = ImitationQuizSerializer(quizzes, many=True, context={'request': request})
        return Response(serializer.data)

class ImitationAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(ImitationQuiz, id=quiz_id)
        now = timezone.now()
        
        if now > quiz.start_datetime:
            return Response(
                {"error": "დასრულებულია"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        attempt, created = ImitationAttempt.objects.get_or_create(
            user=request.user,
            imitation_quiz=quiz,
            defaults={
                'status': 'geted_attempt',
                'total_questions': quiz.get_total_questions()
            }
        )

        return Response({
            "code": attempt.code,
            "status": attempt.status,
            "quiz_title": quiz.title
        }, status=status.HTTP_200_OK)

class ImitationStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                }, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if attempt.status == 'geted_attempt':
            attempt.status = 'started'
            attempt.started_at = timezone.now()
            attempt.save()
            
        return Response(ImitationAttemptSerializer(attempt).data)
    
class ImitationQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)
        
        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                }, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if attempt.status == 'geted_attempt':
            return Response({"error": "ტესტი ჯერ არ არის გააქტიურებული"}, status=status.HTTP_403_FORBIDDEN)

        questions = attempt.imitation_quiz.questions.all().order_by('order')
        answered_ids = attempt.user_answers.values_list('question_id', flat=True)

        serialized_data = []
        for question in questions:
            if question.id in answered_ids:
                serialized = ImitationQuestionWithAnswerSerializer(
                    question, context={"attempt_id": attempt.id}
                ).data
            else:
                serialized = ImitationQuestionSerializer(question).data
            serialized_data.append(serialized)

        return Response(serialized_data)

class ImitationAnswerView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                }, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        if attempt.status == 'geted_attempt':
            return Response({"error": "ტესტი ჯერ არ არის გააქტიურებული"}, status=status.HTTP_403_FORBIDDEN)
        
        if attempt.status == 'completed':
            return Response({"error": "ტესტი უკვე დასრულებულია"}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get('question_id')
        selected_answer = request.data.get('selected_answer', None) 
        time_taken = request.data.get('time_taken', 0)

        valid_choices = [choice[0] for choice in ImitationQuestion.ANSWER_CHOICES]
        if selected_answer.lower() not in valid_choices:
            return Response(
                {'error': f'არასწორი არჩევანი. დასაშვებია მხოლოდ: {", ".join(valid_choices).upper()}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if question_id is None:
            return Response(
                    {'error': 'No question ID provided and no current question available'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        question = get_object_or_404(ImitationQuestion, id=question_id, quiz=attempt.imitation_quiz)

        user_answer, created = ImitationUserAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_answer': selected_answer,
                'time_taken': time_taken
            }
        )

        if attempt.status == 'started':
            attempt.status = 'in_progress'
            attempt.save()
        
        if attempt.is_quiz_completed():
            attempt.status = 'completed'
            attempt.completed_at = timezone.now()
            
            stats = attempt.user_answers.aggregate(
                total_correct=models.Count('id', filter=models.Q(is_correct=True)),
                total_earned=models.Sum('score_earned')
            )
            
            attempt.correct_answers = stats['total_correct'] or 0
            attempt.score = stats['total_earned'] or 0
            
            attempt.save()
            if hasattr(attempt, 'calculate_results'):
                attempt.calculate_results()
        
        return Response({
            "status": attempt.status, 
            "is_correct": user_answer.is_correct,
            "selected": user_answer.selected_answer
        })
    
class ImitationResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code, user=request.user)
        
        if attempt.status != 'completed':
            return Response({"error": "ტესტი ჯერ არ არის დასრულებული"}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() < attempt.imitation_quiz.end_datetime:
            return Response(
                {"error": "doesnot active"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ImitationQuizResultSerializer(attempt, context={'request': request})
        return Response(serializer.data)