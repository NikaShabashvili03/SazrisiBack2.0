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

from django.db.models import Count, Avg, Sum, F, Q, Max, Min, Case, When, IntegerField, FloatField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Extract
from collections import defaultdict
import math
from datetime import timedelta, datetime
from quiz.models.quiz import UserAnswer, Quiz, Question, Topic


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

class Statistic(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        def percentage(correct, total):
            return round((correct / total) * 100, 2) if total > 0 else 0

        # === Category Stats ===
        category_stats = Quiz.objects.filter(attempts__user=user).values(
            'category__title'
        ).annotate(
            total_answers=Count(
                'questions__useranswer',
                filter=Q(questions__useranswer__attempt__user=user)
            ),
            total_errors=Count(
                'questions__useranswer',
                filter=Q(
                    questions__useranswer__is_correct=False,
                    questions__useranswer__attempt__user=user
                )
            ),
            avg_time=Avg(
                'questions__useranswer__time_taken',
                filter=Q(questions__useranswer__attempt__user=user)
            ),
        ).annotate(
            error_percentage=ExpressionWrapper(
                100 * F('total_errors') / F('total_answers'),
                output_field=FloatField()
            )
        ).filter(total_answers__gt=0).order_by('-total_errors')

        categories_chart = {
            "labels": [c['category__title'] for c in category_stats],
            "datasets": {
                "total_errors": [c['total_errors'] for c in category_stats],
                "error_percentages": [round(c['error_percentage'], 2) for c in category_stats],
                "average_time_seconds": [round(c['avg_time'] or 0, 2) for c in category_stats],
            }
        }

        # === Topic Stats ===
        topic_stats = Topic.objects.annotate(
            total_answers=Count(
                'questions__useranswer',
                filter=Q(questions__useranswer__attempt__user=user)
            ),
            total_errors=Count(
                'questions__useranswer',
                filter=Q(
                    questions__useranswer__is_correct=False,
                    questions__useranswer__attempt__user=user
                )
            ),
            avg_time=Avg(
                'questions__useranswer__time_taken',
                filter=Q(questions__useranswer__attempt__user=user)
            )
        ).annotate(
            error_percentage=ExpressionWrapper(
                100 * F('total_errors') / F('total_answers'),
                output_field=FloatField()
            )
        ).filter(total_answers__gt=0).order_by('-total_errors')

        topics_chart = {
            "labels": [t.name for t in topic_stats],
            "datasets": {
                "total_errors": [t.total_errors for t in topic_stats],
                "error_percentages": [round(t.error_percentage, 2) for t in topic_stats],
                "average_time_seconds": [round(t.avg_time or 0, 2) for t in topic_stats],
            }
        }

        # === Answer Distribution (for Pie/Bar chart) ===
        distribution = {
            label: UserAnswer.objects.filter(
                attempt__user=user, selected_answer=label.lower()
            ).count()
            for label in ['A', 'B', 'G', 'D']
        }

        answer_distribution_chart = {
            "labels": list(distribution.keys()),
            "datasets": {
                "counts": list(distribution.values())
            }
        }

        # === Topic Accuracy (Correct vs Incorrect)
        topic_accuracy_stats = Topic.objects.annotate(
            correct=Count(
                'questions__useranswer',
                filter=Q(questions__useranswer__is_correct=True, questions__useranswer__attempt__user=user)
            ),
            incorrect=Count(
                'questions__useranswer',
                filter=Q(questions__useranswer__is_correct=False, questions__useranswer__attempt__user=user)
            )
        ).filter(Q(correct__gt=0) | Q(incorrect__gt=0)).order_by('-incorrect')

        topic_accuracy_chart = {
            "labels": [],
            "datasets": {
                "correct": [],
                "incorrect": [],
                "accuracy_percentage": []
            }
        }

        for t in topic_accuracy_stats:
            total = t.correct + t.incorrect
            topic_accuracy_chart["labels"].append(t.name)
            topic_accuracy_chart["datasets"]["correct"].append(t.correct)
            topic_accuracy_chart["datasets"]["incorrect"].append(t.incorrect)
            topic_accuracy_chart["datasets"]["accuracy_percentage"].append(percentage(t.correct, total))

        # === Overall Stats ===
        total_answers = UserAnswer.objects.filter(attempt__user=user).count()
        total_errors = UserAnswer.objects.filter(attempt__user=user, is_correct=False).count()
        average_time = UserAnswer.objects.filter(attempt__user=user).aggregate(
            avg_time=Avg('time_taken')
        )['avg_time'] or 0

        overall_stats = {
            "total_answers": total_answers,
            "total_errors": total_errors,
            "accuracy": percentage(total_answers - total_errors, total_answers),
            "average_time_seconds": round(average_time, 2)
        }

        return Response({
            "overall": overall_stats,
            "categories": categories_chart,
            "topics": topics_chart,
            "answer_distribution": answer_distribution_chart,
            "topic_accuracy": topic_accuracy_chart
        })