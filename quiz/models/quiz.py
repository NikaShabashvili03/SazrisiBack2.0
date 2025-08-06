from django.db import models
from authentication.models.user import User
from ckeditor_uploader.fields import RichTextUploadingField
import uuid
import os
from django.core.exceptions import ValidationError

def unique_file_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename_base = os.path.splitext(filename)[0]
    unique_id = uuid.uuid4().hex 
    return f"quiz_files/{filename_base}_{unique_id}.{ext}"


def validate_pdf(file):
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError('Only PDF files are allowed.')
        
class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='quizzes')

    time_limit = models.IntegerField(default=30)

    file = models.FileField(
        upload_to=unique_file_upload_path,
        validators=[validate_pdf],
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def get_total_questions(self):
        return self.questions.all().count()

    def get_total_score(self):
        return self.questions.aggregate(total=models.Sum('score'))['total'] or 0

    def __str__(self):
        return f"{self.title} - {self.category.title}"


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
    
    def get_questions(self):
        try:
            return self.quiz.questions.all()
        except Question.DoesNotExist:
            return None
        
    def get_question_by_id(self, question_id):
        try:
            return self.quiz.questions.get(id=question_id)
        except Question.DoesNotExist:
            return None

    def is_quiz_completed(self):
        total_questions = self.quiz.questions.count()
        interacted_questions = self.user_answers.count()
        return interacted_questions >= total_questions

class Topic(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()

    def __str__(self):
        return self.name

class Question(models.Model):
    ANSWER_CHOICES = [
        ('a', 'A'),
        ('b', 'B'),
        ('g', 'G'),
        ('d', 'D'),
    ]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="questions")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    explanation = RichTextUploadingField('Explanation', config_name='explanation')
    answer = models.CharField(max_length=1, choices=ANSWER_CHOICES, default=None)
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
        return f"{self.quiz.title} - Q{self.order}"

class UserAnswer(models.Model):
    ANSWER_CHOICES = [
        ('a', 'A'),
        ('b', 'B'),
        ('g', 'G'),
        ('d', 'D'),
    ]

    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES, default=None)
    is_correct = models.BooleanField(default=False)
    score_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    time_taken = models.IntegerField(default=0, help_text="Time taken to answer in seconds")
    
    class Meta:
        unique_together = ['attempt', 'question']
        ordering = ['answered_at']
    
    def __str__(self):
        return f"{self.attempt.user} - ({'✓' if self.is_correct else '✗'})"