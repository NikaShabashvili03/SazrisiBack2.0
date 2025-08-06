from quiz.models.category import Category
from quiz.models.quiz import Quiz, QuizAttempt, Question
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Max
from quiz.serializers.quiz import QuizAttemptSerializer, QuizSerializer, QuestionSerializer, QuestionWithCorrectSerializer, UserAnswer

class QuizListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, categoryId): 
        category = get_object_or_404(Category, id=categoryId)

        if not category.has_access(user=request.user):
            print("Not Access")
            return Response(
                    {'error': 'You do not have access to this category'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        quizzes = Quiz.objects.filter(
            category=category,
        )
        
        quiz_type = request.query_params.get('type')
        if quiz_type:
            quizzes = quizzes.filter(quiz_type=quiz_type)

        serializer = QuizSerializer(quizzes, many=True, context={'request': request})
        return Response(serializer.data)


class QuizDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id, categoryId):
        category = get_object_or_404(Category, id=categoryId)

        if not category.has_access(user=request.user):
            return Response(
                    {'error': 'You do not have access to this category'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        quiz = get_object_or_404(Quiz, id=quiz_id, category=category)
        
        serializer = QuizSerializer(quiz, context={'request': request})
        return Response(serializer.data)


class QuizStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id, categoryId):
        category = get_object_or_404(Category, id=categoryId)

        if not category.has_access(user=request.user):
            return Response(
                    {'error': 'You do not have access to this category'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        quiz = get_object_or_404(Quiz, id=quiz_id, category=category)
        
        existing_attempt = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz,
            status__in=['started', 'in_progress', 'completed']
        ).first()
            
        if existing_attempt:
            serializer = QuizAttemptSerializer(existing_attempt)
            return Response(serializer.data)
        
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            total_questions=quiz.get_total_questions(),
            status='started'
        )
        
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class QuizQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt,
            id=attempt_id,
            user=request.user,
            status__in=['started', 'in_progress', 'completed']
        )

        questions = attempt.get_questions()

        user_answers = UserAnswer.objects.filter(
            attempt=attempt,
            attempt__status__in=['started', 'in_progress', 'completed']
        ).values_list('question_id', flat=True)

        serialized_data = []
        for question in questions:
            if question.id in user_answers:
                serialized = QuestionWithCorrectSerializer(
                    question, context={"attempt_id": attempt_id}
                ).data
            else:
                serialized = QuestionSerializer(question).data
            serialized_data.append(serialized)

        return Response(serialized_data)
        
class QuizAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt, 
            id=attempt_id, 
            user=request.user,
            status__in=['started', 'in_progress']
        )

        selected_answer = request.data.get('selected_answer', None)
        time_taken = request.data.get('time_taken', 0)
        question_id = request.data.get('question_id')

        if question_id is None:
            return Response(
                    {'error': 'No question ID provided and no current question available'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        question = attempt.get_question_by_id(question_id)
        
        if question is None:
            return Response(
                {'error': 'Question Doesnot exists'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if selected_answer is None:
            return Response(
                {'error': 'No answers selected'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        existing_answer = UserAnswer.objects.filter(
            attempt=attempt,
            question=question
        ).first()

        if existing_answer:
            return Response({
                'error': 'You have been answered to this question',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_answer = UserAnswer.objects.create(
            attempt=attempt,
            question=question,
            time_taken=time_taken,
            selected_answer=selected_answer
        )

        selected_correct = selected_answer == question.answer

        if selected_correct:
            user_answer.is_correct = True
            user_answer.score_earned = question.score
            attempt.correct_answers += 1
            attempt.score += question.score
                
        user_answer.save()
        
        total_questions = attempt.quiz.questions.count()
        attempt.total_questions = total_questions
        
        if attempt.is_quiz_completed():
            attempt.status = 'completed'
            attempt.completed_at = timezone.now()
            attempt.time_taken = attempt.completed_at - attempt.started_at
            attempt.calculate_results()
        else:
            attempt.status = 'in_progress'
        
        attempt.save()
    
        question_with_correct_answers = QuestionWithCorrectSerializer(question, context={"attempt_id": attempt_id}).data
        
        total_questions = attempt.quiz.questions.count()
        attempt.total_questions = total_questions
        serialized_attempt = QuizAttemptSerializer(attempt).data

        return Response({
            "updated_question": question_with_correct_answers,
            "updated_attempt": serialized_attempt,
        })