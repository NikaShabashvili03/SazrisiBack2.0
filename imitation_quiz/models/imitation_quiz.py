import random
import os
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from authentication.models.user import User
from ckeditor_uploader.fields import RichTextUploadingField
from core.utils import image_upload, validate_image

# --- ფაილების ატვირთვის დამხმარე ფუნქციები ---

def unique_file_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename_base = os.path.splitext(filename)[0]
    unique_id = uuid.uuid4().hex 
    return f"imitation_files/{filename_base}_{unique_id}.{ext}"

def unique_exp_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename_base = os.path.splitext(filename)[0]
    unique_id = uuid.uuid4().hex 
    return f"imitation_explanation/{filename_base}_{unique_id}.{ext}"

def validate_pdf(file):
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError('მხოლოდ PDF ფაილებია ნებადართული.')

class ImitationQuiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        'quiz.Category',
        on_delete=models.CASCADE,
        related_name='imitation_quizzes'
    )
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    time_limit = models.IntegerField(default=30)

    file = models.FileField(
        upload_to=unique_file_upload_path,
        validators=[validate_pdf],
        blank=False,
        null=False
    )

    explanation = models.FileField(
        upload_to=unique_exp_upload_path,
        validators=[validate_pdf],
        blank=False,
        null=False
    )

    location = models.CharField(max_length=255, blank=False, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    start_datetime = models.DateTimeField(
        verbose_name="Start Date and Time",
        default=timezone.now,
        help_text="The quiz will become accessible from this time."
    )
    end_datetime = models.DateTimeField(
        verbose_name="End Date and Time",
        default=timezone.now,
        help_text="The quiz will close after this time."
    )

    max_space = models.IntegerField(null=False, blank=False)

    available_laptops = models.IntegerField(null=False, blank=False)

    @property
    def registered_laptops(self):
        return self.attempts.filter(laptop_type='company').count()

    @property
    def is_laptop_available(self):
        return self.registered_laptops < self.available_laptops
    
    @property
    def user_count(self):
        return self.attempts.count()
    
    @property
    def is_valid_space(self):
        return self.user_count < self.max_space

    @property
    def is_active(self):
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime
    
    @property
    def status(self):
        now = timezone.now()
        if now < self.start_datetime:
            return "Scheduled"
        elif now > self.end_datetime:
            return "Expired"
        return "Active"
    
    class Meta:
        ordering = ['-created_at']
    
    def has_access(self, user):
        if not self.is_paid:
            return True
        if not user or not user.is_authenticated:
            return False
        return UserImitationQuizAccess.objects.filter(
            user=user, imitation_quiz=self, is_active=True, expires_at__gt=timezone.now()
        ).exists()

    def get_total_questions(self):
        return self.questions.all().count()

    def get_total_score(self):
        return self.questions.aggregate(total=models.Sum('score'))['total'] or 0

    def __str__(self):
        return f"{self.title} - {self.category.title}"


class ImitationAttempt(models.Model):
    STATUS_CHOICES = [
        ('geted_attempt', 'Geted Attempt'), 
        ('started', 'Started'),       
        ('in_progress', 'In Progress'),    
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]

    LAPTOP_TYPE = [
        ('my', 'my'),
        ('company', 'company')
    ]
    
    laptop_type = models.CharField(
        max_length=10, 
        choices=LAPTOP_TYPE, 
        default='my'
    )

    code = models.CharField(max_length=6, unique=True, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='imitation_attempts')
    imitation_quiz = models.ForeignKey(ImitationQuiz, on_delete=models.CASCADE, related_name='attempts')
    
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
        return f"{self.user} - {self.code} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_unique_code()
        
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
            
        super().save(*args, **kwargs)

    def generate_unique_code(self):
        while True:
            new_code = f"{random.randint(100000, 999999)}"
            if not ImitationAttempt.objects.filter(code=new_code).exists():
                return new_code

    def get_remaining_time_from_answers(self):
        total_time_taken = self.user_answers.aggregate(
            total=models.Sum('time_taken')
        )['total'] or 0

        quiz_time_limit_seconds = self.imitation_quiz.time_limit * 60 
        remaining_time = quiz_time_limit_seconds - total_time_taken
        return max(0, remaining_time)

    def calculate_results(self):
        if self.total_questions > 0:
            self.percentage = (self.correct_answers / self.total_questions) * 100
        else:
            self.percentage = 0
        self.save()
    
    def get_questions(self):
        return self.imitation_quiz.questions.all()
        
    def is_quiz_completed(self):
        total_questions = self.imitation_quiz.questions.count()
        interacted_questions = self.user_answers.count()
        return interacted_questions >= total_questions


class ImitationTopic(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class ImitationQuestion(models.Model):
    ANSWER_CHOICES = [
        ('a', 'A'),
        ('b', 'B'),
        ('g', 'G'),
        ('d', 'D'),
    ]

    quiz = models.ForeignKey(ImitationQuiz, on_delete=models.CASCADE, related_name='questions')
   
    answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    topic = models.ForeignKey(ImitationTopic, on_delete=models.CASCADE, related_name="questions", null=True, blank=True)
    score = models.IntegerField(default=1)
    order = models.IntegerField(default=1, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['quiz', 'order']

    def save(self, *args, **kwargs):
        # ავტომატური ინკრემენტი 'order' ველისთვის, თუ ის არ არის მითითებული
        if not self.pk and self.order == 1:
            last_order = ImitationQuestion.objects.filter(quiz=self.quiz).aggregate(
                max_order=models.Max('order')
            )['max_order']
            self.order = (last_order or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"

    
class ImitationUserAnswer(models.Model):
    ANSWER_CHOICES = [
        ('a', 'A'),
        ('b', 'B'),
        ('g', 'G'),
        ('d', 'D'),
    ]

    attempt = models.ForeignKey(ImitationAttempt, on_delete=models.CASCADE, related_name='user_answers')
    question = models.ForeignKey(ImitationQuestion, on_delete=models.CASCADE)
    
    # აქ მომხმარებელი ირჩევს კონკრეტულ ასოს
    selected_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    
    is_correct = models.BooleanField(default=False)
    score_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)
    time_taken = models.IntegerField(default=0, help_text="Time taken to answer in seconds")

    class Meta:
        unique_together = ['attempt', 'question']
        ordering = ['answered_at']

    def save(self, *args, **kwargs):
        # ავტომატური შემოწმება სისწორეზე შენახვისას
        if self.selected_answer == self.question.answer:
            self.is_correct = True
            self.score_earned = self.question.score
        else:
            self.is_correct = False
            self.score_earned = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.attempt.user} - {self.attempt.code} ({'✓' if self.is_correct else '✗'})"


class ImitationAISummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_summaries')
    attempt = models.ForeignKey(
        'ImitationAttempt', on_delete=models.CASCADE,
        related_name='ai_summaries', null=True, blank=True
    )
    quiz_title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.quiz_title} ({self.created_at.date()})"


class UserImitationQuizAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='imitation_quiz_access')
    imitation_quiz = models.ForeignKey(ImitationQuiz, on_delete=models.CASCADE, related_name='user_access')
    access_granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-access_granted_at']

    def __str__(self):
        return f"{self.user} has access to {self.imitation_quiz.title} until {self.expires_at}"

    @property
    def is_access_active(self):
        return self.is_active and timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)