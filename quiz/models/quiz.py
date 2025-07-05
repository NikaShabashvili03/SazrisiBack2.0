from django.db import models
from django.utils import timezone
from datetime import timedelta
from ..models.category import Category
from authentication.models.user import User
from ckeditor_uploader.fields import RichTextUploadingField

class Quiz(models.Model):
    QUIZ_TYPES = [
        ('tournament', 'Tournament'),
        ('progress', 'Progress'),
        ('training', 'Training'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='quizzes')
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPES, default='training')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS, default='medium')
    
    tournament_start_time = models.TimeField(null=True, blank=True, help_text="Tournament start time (e.g., 17:00)")
    tournament_end_time = models.TimeField(null=True, blank=True, help_text="Tournament end time (e.g., 22:00)")
    
    time_limit = models.IntegerField(default=30, help_text="Time limit per quiz in seconds")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def get_total_questions(self):
        return self.questions.all().count()
    
    def get_total_score(self):
        return self.questions.aggregate(total=models.Sum('score'))['total'] or 0
    
    @property
    def is_tournament_active(self):
        if self.quiz_type != 'tournament':
            return False
        
        if not self.tournament_start_time or not self.tournament_end_time:
            return False
        
        current_time = timezone.now().time()
        
        if self.tournament_start_time <= self.tournament_end_time:
            return self.tournament_start_time <= current_time <= self.tournament_end_time
        else:
            return current_time >= self.tournament_start_time or current_time <= self.tournament_end_time
    
    def __str__(self):
        return f"{self.title} ({self.get_quiz_type_display()}) - {self.category.title}"


class QuizAttempt(models.Model):
    STATUS_CHOICES = [
        ('started', 'Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='started')
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0) 
    correct_answers = models.IntegerField(default=0)
    skipped_answers = models.IntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken = models.DurationField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user} - {self.quiz.title} ({self.get_status_display()})"

    def get_remaining_time_from_answers(self):
        total_time_taken = self.user_answers.aggregate(
            total=models.Sum('time_taken')
        )['total']

        quiz_time_limit_seconds = self.quiz.time_limit * 60 

        if total_time_taken is None:
            return quiz_time_limit_seconds

        remaining_time = quiz_time_limit_seconds - total_time_taken
        return max(0, remaining_time)

    def calculate_results(self):
        if self.total_questions > 0:
            self.percentage = (self.correct_answers / self.total_questions) * 100
        else:
            self.percentage = 0
        self.save()
    
    def get_answered_question_ids(self):
        return list(self.user_answers.filter(is_skipped=False).values_list('question_id', flat=True))
    
    def get_skipped_question_ids(self):
        return list(self.user_answers.filter(is_skipped=True).values_list('question_id', flat=True))
    
    def get_current_question_id(self):
        interacted_question_ids = list(self.user_answers.values_list('question_id', flat=True))
        
        next_question = self.quiz.questions.exclude(
            id__in=interacted_question_ids
        ).order_by('order').first()
        
        return next_question.id if next_question else None
    
    def get_question_by_id(self, question_id):
        try:
            return self.quiz.questions.get(id=question_id)
        except Question.DoesNotExist:
            return None
    
    # casashleli
    def get_next_question_id(self, current_question_id):
        try:
            current_question = self.quiz.questions.get(id=current_question_id)
            next_question = self.quiz.questions.filter(
                order__gt=current_question.order
            ).order_by('order').first()
            return next_question.id if next_question else None
        except Question.DoesNotExist:
            return None
    
    def get_previous_question_id(self, current_question_id):
        try:
            current_question = self.quiz.questions.get(id=current_question_id)
            previous_question = self.quiz.questions.filter(
                order__lt=current_question.order
            ).order_by('-order').first()
            return previous_question.id if previous_question else None
        except Question.DoesNotExist:
            return None

    def get_first_question_id(self):
        first_question = self.quiz.questions.order_by('order').first()
        return first_question.id if first_question else None
    
    def get_last_question_id(self):
        last_question = self.quiz.questions.order_by('-order').first()
        return last_question.id if last_question else None
    
    def is_question_answered(self, question_id):
        return self.user_answers.filter(question_id=question_id).exists()
    
    def get_question_number_by_id(self, question_id):
        try:
            question = self.quiz.questions.get(id=question_id)
            return question.order
        except Question.DoesNotExist:
            return None
    
    def is_quiz_completed(self):
        total_questions = self.quiz.questions.count()
        interacted_questions = self.user_answers.count()
        return interacted_questions >= total_questions
    
    def get_question_status_summary(self):
        answered_ids = set(self.get_answered_question_ids())
        skipped_ids = set(self.get_skipped_question_ids())
        
        questions_status = []
        for question in self.quiz.questions.order_by('order'):
            if question.id in answered_ids:
                status = 'answered'
            elif question.id in skipped_ids:
                status = 'skipped'
            else:
                status = 'unanswered'
            
            questions_status.append({
                'question_id': question.id,
                'order': question.order,
                'status': status
            })
        
        return {
            'questions': questions_status,
            'answered_count': len(answered_ids),
            'skipped_count': len(skipped_ids),
            'unanswered_count': self.quiz.questions.count() - len(answered_ids) - len(skipped_ids),
            'total_count': self.quiz.questions.count()
        }


class Question(models.Model):
    QUESTION_TYPES = [
        ('single', 'Single Choice'),
        ('multiple', 'Multiple Choice'),
        ('true_false', 'True/False'),
    ]
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = RichTextUploadingField('Question Text', config_name='question_editor')
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single')
    explanation = RichTextUploadingField('Explanation', config_name='explanation')
    score = models.IntegerField(default=1)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['quiz', 'order']
    
    def save(self, *args, **kwargs):
        if self._state.adding and self.order == 0:
            last_order = Question.objects.filter(quiz=self.quiz).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            self.order = last_order + 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}: {self.question_text[:50]}"


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = RichTextUploadingField('Answer Text', config_name='answer_editor')
    
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['question', 'order']
    
    def save(self, *args, **kwargs):
        if self._state.adding and self.order == 0:
            last_order = Answer.objects.filter(question=self.question).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            self.order = last_order + 1
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.question.quiz.title} - {self.answer_text[:30]} ({'✓' if self.is_correct else '✗'})"


class UserAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answers = models.ManyToManyField(Answer, blank=True)
    is_correct = models.BooleanField(default=False)
    is_skipped = models.BooleanField(default=False)
    score_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    time_taken = models.IntegerField(default=0, help_text="Time taken to answer in seconds")
    
    class Meta:
        unique_together = ['attempt', 'question']
        ordering = ['answered_at']
    
    def __str__(self):
        return f"{self.attempt.user} - {self.question.question_text[:30]} ({'✓' if self.is_correct else '✗'})"