from quiz.models.category import Category
from quiz.models.quiz import Quiz, QuizAttempt, Answer, Question
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Max
from quiz.serializers.quiz import QuizAttemptSerializer, QuizSerializer, QuestionSerializer, QuestionWithCorrectSerializer, AnswerSerializer, AnswerWithCorrectSerializer, UserAnswerSerializer, UserAnswer

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
        
        if quiz.quiz_type == 'tournament' and not quiz.is_tournament_active:
            return Response(
                {'error': f'Tournament is only available from {quiz.tournament_start_time} to {quiz.tournament_end_time}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if quiz.quiz_type == 'progress':
            existing_attempt = QuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz,
                status__in=['started', 'in_progress']
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
    

class QuizQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id, question_id):
        attempt = get_object_or_404(
            QuizAttempt,
            id=attempt_id,
            user=request.user,
            status__in=['started', 'in_progress', 'completed']
        )

        if question_id is not None:
            try:
                question_id = int(question_id)
                current_question = attempt.get_question_by_id(question_id)
                if current_question is None:
                    return Response(
                        {'error': 'Invalid question ID'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {'details', 'Invalid question Id format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            current_question_id = attempt.get_current_question_id()
            if current_question_id is None:
                current_question_id = attempt.get_first_question_id()
                if current_question_id is None:
                    return Response(
                        {'error': 'No questions available'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            current_question = attempt.get_question_by_id(current_question_id)

        user_answer = UserAnswer.objects.filter(
            attempt=attempt,
            question=current_question,
            attempt__status__in=['started', 'in_progress', 'completed']
        ).distinct().exists()

        if user_answer:
            question_with_answers = QuestionWithCorrectSerializer(current_question, context={"attempt_id": attempt_id}).data
            return Response(question_with_answers)
        
        question_without_answers = QuestionSerializer(current_question).data
        return Response(question_without_answers)
        
# class QuizQuestion2View(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, attempt_id):
#         attempt = get_object_or_404(
#             QuizAttempt, 
#             id=attempt_id, 
#             user=request.user,
#             status__in=['started', 'in_progress']
#         )
        
#         question_id = request.query_params.get('question_id')

#         if question_id is not None:
#             try:
#                 question_id = int(question_id)
#                 current_question = attempt.get_question_by_id(question_id)
#                 if current_question is None:
#                     return Response(
#                         {'error': 'Invalid question ID'}, 
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#             except ValueError:
#                 return Response(
#                     {'error': 'Invalid question ID format'}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#         else:
#             current_question_id = attempt.get_current_question_id()
#             if current_question_id is None:
#                 current_question_id = attempt.get_first_question_id()
#                 if current_question_id is None:
#                     return Response(
#                         {'error': 'No questions available'}, 
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#             current_question = attempt.get_question_by_id(current_question_id)

#         serializer = QuestionSerializer(current_question)
        
#         question_number = attempt.get_question_number_by_id(current_question.id)
        
#         user_answer_data = None
#         try:
#             user_answer = UserAnswer.objects.get(
#                 attempt=attempt,
#                 question=current_question
#             )

#             selected_answers = user_answer.selected_answers.all()
#             selected_answers_data = [
#                 {
#                     'id': answer.id,
#                     'answer_text': answer.answer_text,
#                     'is_correct': answer.is_correct
#                 }
#                 for answer in selected_answers
#             ]
            
#             user_answer_data = {
#                 'has_answered': True,
#                 'selected_answers': selected_answers_data,
#                 'is_correct': user_answer.is_correct,
#                 'score_earned': user_answer.score_earned,
#                 'time_taken': user_answer.time_taken,
#                 'answered_at': user_answer.answered_at,
#                 'is_skipped': user_answer.is_skipped
#             }
#         except UserAnswer.DoesNotExist:
#             user_answer_data = {
#                 'has_answered': False,
#                 'selected_answers': [],
#                 'is_correct': None,
#                 'score_earned': 0,
#                 'time_taken': 0,
#                 'answered_at': None,
#                 'is_skipped': False
#             }
        
#         # Additional navigation info
#         next_question_id = attempt.get_next_question_id(current_question.id)
#         previous_question_id = attempt.get_previous_question_id(current_question.id)
        
#         # Get question status summary
#         question_status = attempt.get_question_status_summary()
        
#         return Response({
#             'question': serializer.data,
#             'question_number': question_number,
#             'total_questions': attempt.total_questions,
#             'time_limit': attempt.quiz.time_limit,
#             'user_answer': user_answer_data,
#             'current_question_id': current_question.id,
#             'next_question_id': next_question_id,
#             'previous_question_id': previous_question_id,
#             'is_first_question': previous_question_id is None,
#             'is_last_question': next_question_id is None,
#             'question_status': question_status
#         })
    
class QuizAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt, 
            id=attempt_id, 
            user=request.user,
            status__in=['started', 'in_progress']
        )

        selected_answer_ids = request.data.get('selected_answer_ids', [])
        time_taken = request.data.get('time_taken', 0)
        question_id = request.data.get('question_id')

        if question_id is None:
            question_id = attempt.get_current_question_id()
            if question_id is None:
                return Response(
                    {'error': 'No question ID provided and no current question available'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        question = attempt.get_question_by_id(question_id)
        
        if not selected_answer_ids:
            return Response(
                {'error': 'No answers selected'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_answer_ids = set(
            question.answers.values_list('id', flat=True)
        )

        selected_answer_ids_set = set(selected_answer_ids)

        if not selected_answer_ids_set.issubset(valid_answer_ids):
            return Response({
                'error': 'Selected answers do not belong to target question',
            }, status=status.HTTP_400_BAD_REQUEST)
        
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
            is_skipped=False
        )

        selected_answers = Answer.objects.filter(
                id__in=selected_answer_ids,
                question=question
        )
        user_answer.selected_answers.set(selected_answers)
        
        correct_answers = question.answers.filter(is_correct=True)
        selected_correct = selected_answers.filter(is_correct=True)
        
        if question.question_type == 'single':
            if (selected_correct.count() == 1 and 
                selected_answers.count() == 1):
                user_answer.is_correct = True
                user_answer.score_earned = question.score
                attempt.correct_answers += 1
                attempt.score += question.score
                
        elif question.question_type == 'multiple':
            if (set(selected_correct.values_list('id', flat=True)) == 
                    set(correct_answers.values_list('id', flat=True)) and
                    selected_answers.filter(is_correct=False).count() == 0):
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

        if attempt.is_quiz_completed():
            attempt.status = 'completed'
            attempt.completed_at = timezone.now()
            attempt.time_taken = attempt.completed_at - attempt.started_at
            attempt.calculate_results()
        else:
            attempt.status = 'in_progress'
        
        attempt.save()

        serialized_attempt = QuizAttemptSerializer(attempt).data

        next_question_id = attempt.get_next_question_id(question.id)

        return Response({
            "updated_question": question_with_correct_answers,
            "updated_attempt": serialized_attempt,
            "next_question": next_question_id
        })
    
# class QuizAnswer2View(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, attempt_id):
#         attempt = get_object_or_404(
#             QuizAttempt, 
#             id=attempt_id, 
#             user=request.user,
#             status__in=['started', 'in_progress']
#         )
        
        # selected_answer_ids = request.data.get('selected_answer_ids', [])
        # time_taken = request.data.get('time_taken', 0)
        # question_id = request.data.get('question_id')
        
        # if question_id is None:
        #     # If no question_id provided, use current question
        #     question_id = attempt.get_current_question_id()
        #     if question_id is None:
        #         return Response(
        #             {'error': 'No question ID provided and no current question available'}, 
        #             status=status.HTTP_400_BAD_REQUEST
        #         )
        
#         # Get the target question
#         target_question = attempt.get_question_by_id(question_id)
#         if target_question is None:
#             return Response(
#                 {'error': 'Invalid question ID'}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
        # if not selected_answer_ids:
        #     return Response(
        #         {'error': 'No answers selected'}, 
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        
#         # Validate that selected answers belong to the target question
        # valid_answer_ids = set(
        #     target_question.answers.values_list('id', flat=True)
        # )
#         selected_answer_ids_set = set(selected_answer_ids)
        
        # if not selected_answer_ids_set.issubset(valid_answer_ids):
        #     # Find which question these answers actually belong to
        #     correct_question = None
        #     for question in attempt.quiz.questions.all():
        #         question_answer_ids = set(question.answers.values_list('id', flat=True))
        #         if selected_answer_ids_set.issubset(question_answer_ids):
        #             correct_question = question
        #             break
            
            # return Response({
            #     'error': 'Selected answers do not belong to target question',
            #     'target_question_id': question_id,
            #     'correct_question_id': correct_question.id if correct_question else None,
            #     'message': f'These answers belong to question {correct_question.id}' if correct_question else 'Invalid answer IDs provided'
            # }, status=status.HTTP_400_BAD_REQUEST)
        
#         # Check if user has already answered this question
        # existing_answer = UserAnswer.objects.filter(
        #     attempt=attempt,
        #     question=target_question
        # ).first()
        
#         with transaction.atomic():
#             if existing_answer:
#                 # Update existing answer
#                 user_answer = existing_answer
#                 # Reset previous scoring only if it was correct and not skipped
#                 if user_answer.is_correct and not user_answer.is_skipped:
#                     attempt.correct_answers -= 1
#                     attempt.score -= user_answer.score_earned
                
#                 # Clear previous selected answers
#                 user_answer.selected_answers.clear()
#                 user_answer.time_taken = time_taken
#                 user_answer.is_correct = False
#                 user_answer.score_earned = 0
#                 user_answer.is_skipped = False  # Reset skip status when answering
#             else:
#                 # Create new answer
                # user_answer = UserAnswer.objects.create(
                #     attempt=attempt,
                #     question=target_question,
                #     time_taken=time_taken,
                #     is_skipped=False
                # )
            
        #     selected_answers = Answer.objects.filter(
        #         id__in=selected_answer_ids,
        #         question=target_question
        #     )
        #     user_answer.selected_answers.set(selected_answers)
            
        #     correct_answers = target_question.answers.filter(is_correct=True)
        #     selected_correct = selected_answers.filter(is_correct=True)
            
        #     # Check if answer is correct based on question type
        #     if target_question.question_type == 'single':
        #         # For single choice: exactly one correct answer selected
        #         if (selected_correct.count() == 1 and 
        #             selected_answers.count() == 1):
        #             user_answer.is_correct = True
        #             user_answer.score_earned = target_question.score
        #             attempt.correct_answers += 1
        #             attempt.score += target_question.score
                    
        #     elif target_question.question_type == 'multiple':
        #         # For multiple choice: all correct answers selected, no incorrect ones
        #         if (set(selected_correct.values_list('id', flat=True)) == 
        #               set(correct_answers.values_list('id', flat=True)) and
        #               selected_answers.filter(is_correct=False).count() == 0):
        #             user_answer.is_correct = True
        #             user_answer.score_earned = target_question.score
        #             attempt.correct_answers += 1
        #             attempt.score += target_question.score
                    
        #     elif target_question.question_type == 'true_false':
        #         # For true/false: exactly one correct answer selected
        #         if (selected_correct.count() == 1 and 
        #             selected_answers.count() == 1):
        #             user_answer.is_correct = True
        #             user_answer.score_earned = target_question.score
        #             attempt.correct_answers += 1
        #             attempt.score += target_question.score
            
        #     user_answer.save()
            
        #     # Update attempt totals
            # total_questions = attempt.quiz.questions.count()
            # attempt.total_questions = total_questions
            
            # # Check if quiz should be completed (all questions have been interacted with)
            # if attempt.is_quiz_completed():
            #     attempt.status = 'completed'
            #     attempt.completed_at = timezone.now()
            #     attempt.time_taken = attempt.completed_at - attempt.started_at
            #     attempt.calculate_results()
            # else:
            #     attempt.status = 'in_progress'
            
            # attempt.save()
        
        # # Return response with correct answers for review
        # correct_answer_serializer = QuestionWithCorrectSerializer(target_question)
        
#         # Get navigation info after answering
#         current_question_id = attempt.get_current_question_id()
#         next_question_id = attempt.get_next_question_id(target_question.id)
        
#         response_data = {
#             'user_answer': {
#                 'is_correct': user_answer.is_correct,
#                 'score_earned': user_answer.score_earned,
#                 'selected_answers': list(selected_answers.values_list('id', flat=True)),
#                 'is_skipped': user_answer.is_skipped
#             },
#             'correct_answers': correct_answer_serializer.data,
#             'quiz_completed': attempt.status == 'completed',
#             'current_question_id': current_question_id,
#             'next_question_id': next_question_id,
#             'answered_question_id': target_question.id,
#             'was_updated': existing_answer is not None
#         }
        
#         return Response(response_data)


# class QuizSkipView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, attempt_id):
#         attempt = get_object_or_404(
#             QuizAttempt, 
#             id=attempt_id, 
#             user=request.user,
#             status__in=['started', 'in_progress']
#         )
        
#         question_id = request.data.get('question_id')
#         time_taken = request.data.get('time_taken', 0)
        
#         if question_id is None:
#             # If no question_id provided, use current question
#             question_id = attempt.get_current_question_id()
#             if question_id is None:
#                 return Response(
#                     {'error': 'No question ID provided and no current question available'}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         # Get the target question
#         target_question = attempt.get_question_by_id(question_id)
#         if target_question is None:
#             return Response(
#                 {'error': 'Invalid question ID'}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Check if user has already answered/skipped this question
#         existing_answer = UserAnswer.objects.filter(
#             attempt=attempt,
#             question=target_question
#         ).first()
        
#         with transaction.atomic():
#             if existing_answer:
#                 # Update existing answer to skipped
#                 user_answer = existing_answer
#                 # Reset previous scoring if it was correct
#                 if user_answer.is_correct and not user_answer.is_skipped:
#                     attempt.correct_answers -= 1
#                     attempt.score -= user_answer.score_earned
                
#                 # Clear selected answers and mark as skipped
#                 user_answer.selected_answers.clear()
#                 user_answer.is_skipped = True
#                 user_answer.is_correct = False
#                 user_answer.score_earned = 0
#                 user_answer.time_taken = time_taken
#             else:
#                 # Create new skipped answer
#                 user_answer = UserAnswer.objects.create(
#                     attempt=attempt,
#                     question=target_question,
#                     time_taken=time_taken,
#                     is_skipped=True,
#                     is_correct=False,
#                     score_earned=0
#                 )
            
#             user_answer.save()
            
#             # Update attempt status
#             if attempt.is_quiz_completed():
#                 attempt.status = 'completed'
#                 attempt.completed_at = timezone.now()
#                 attempt.time_taken = attempt.completed_at - attempt.started_at
#                 attempt.calculate_results()
#             else:
#                 attempt.status = 'in_progress'
            
#             attempt.save()
        
#         # Get navigation info after skipping
#         current_question_id = attempt.get_current_question_id()
#         next_question_id = attempt.get_next_question_id(target_question.id)
        
#         response_data = {
#             'skipped_question_id': target_question.id,
#             'quiz_completed': attempt.status == 'completed',
#             'current_question_id': current_question_id,
#             'next_question_id': next_question_id,
#             'was_updated': existing_answer is not None
#         }
        
#         return Response(response_data)


class QuizNavigationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt, 
            id=attempt_id, 
            user=request.user,
            status__in=['started', 'in_progress', 'completed']
        )
        
        current_question_id = attempt.get_current_question_id()
        answered_question_ids = attempt.get_answered_question_ids()
        
        # Get all questions with their status
        questions_info = []
        for question in attempt.quiz.questions.order_by('order'):
            is_answered = question.id in answered_question_ids
            
            questions_info.append({
                'id': question.id,
                'order': question.order,
                'is_answered': is_answered,
                'status': 'answered' if is_answered else 'unanswered'
            })
        
        return Response(questions_info)


class QuizResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        attempt = get_object_or_404(
            QuizAttempt, 
            id=attempt_id, 
            user=request.user
        )
        
        serializer = QuizAttemptSerializer(attempt)
        
        response_data = serializer.data
        
        user_answers = attempt.user_answers.select_related('question').prefetch_related('selected_answers')
        answers_data = []
        
        for user_answer in user_answers:
            question_serializer = QuestionWithCorrectSerializer(user_answer.question)
            answers_data.append({
                'question': question_serializer.data,
                'user_answer': {
                    'selected_answers': list(user_answer.selected_answers.values_list('id', flat=True)),
                    'is_correct': user_answer.is_correct,
                    'score_earned': user_answer.score_earned,
                    'time_taken': user_answer.time_taken,
                    'is_skipped': user_answer.is_skipped
                }
            })
            
        response_data['detailed_answers'] = answers_data
        
        return Response(response_data)


class UserQuizHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        attempts = QuizAttempt.objects.filter(
            user=request.user
        ).select_related('quiz', 'quiz__category').order_by('-started_at')
        
        quiz_type = request.query_params.get('type')
        if quiz_type:
            attempts = attempts.filter(quiz__quiz_type=quiz_type)
        
        attempt_status = request.query_params.get('status')
        if attempt_status:
            attempts = attempts.filter(status=attempt_status)
        
        serializer = QuizAttemptSerializer(attempts, many=True)
        return Response(serializer.data)


class QuizStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_attempts = QuizAttempt.objects.filter(user=request.user, status='completed')
        
        total_attempts = user_attempts.count()
        if total_attempts == 0:
            return Response({
                'total_attempts': 0,
                'average_score': 0,
                'best_score': 0,
                'total_time_spent': 0,
                'quizzes_passed': 0,
                'by_quiz_type': {},
                'by_difficulty': {}
            })
        
        stats = {
            'total_attempts': total_attempts,
            'average_score': user_attempts.aggregate(avg_score=Avg('percentage'))['avg_score'] or 0,
            'best_score': user_attempts.aggregate(Max('percentage'))['percentage__max'] or 0,
            'quizzes_passed': user_attempts.filter(percentage__gte=70).count(),
            'by_quiz_type': {},
            'by_difficulty': {}
        }
        
        for quiz_type, _ in Quiz.QUIZ_TYPES:
            type_attempts = user_attempts.filter(quiz__quiz_type=quiz_type)
            if type_attempts.exists():
                stats['by_quiz_type'][quiz_type] = {
                    'attempts': type_attempts.count(),
                    'average_score': type_attempts.aggregate(Avg('percentage'))['percentage__avg'] or 0,
                    'best_score': type_attempts.aggregate(Max('percentage'))['percentage__max'] or 0
                }
        
        for difficulty, _ in Quiz.DIFFICULTY_LEVELS:
            diff_attempts = user_attempts.filter(quiz__difficulty=difficulty)
            if diff_attempts.exists():
                stats['by_difficulty'][difficulty] = {
                    'attempts': diff_attempts.count(),
                    'average_score': diff_attempts.aggregate(Avg('percentage'))['percentage__avg'] or 0,
                    'best_score': diff_attempts.aggregate(Max('percentage'))['percentage__max'] or 0
                }
        
        return Response(stats)