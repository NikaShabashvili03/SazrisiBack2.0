from . import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
from quiz.models.category import Category, UserCategoryAccess


class Payment(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED    = 'failed'
    STATUS_CHOICES   = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED,    'Failed'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    # Legacy category-level FK (kept for backward compatibility)
    category         = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name='payments', null=True, blank=True)
    # Quiz-level FKs
    quiz             = models.ForeignKey('quiz.Quiz', on_delete=models.SET_NULL, related_name='payments', null=True, blank=True)
    imitation_quiz   = models.ForeignKey('imitation_quiz.ImitationQuiz', on_delete=models.SET_NULL, related_name='payments', null=True, blank=True)
    amount           = models.DecimalField(max_digits=10, decimal_places=2)
    currency         = models.CharField(max_length=10, default='GEL')
    transaction_id   = models.CharField(max_length=100, blank=True, null=True, unique=True)
    description      = models.TextField(blank=True, null=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    bog_order_id     = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} - {self.user} - {self.amount} {self.currency} [{self.status}]"

    def _grant_quiz_access(self):
        from quiz.models.category import UserQuizAccess
        access, created = UserQuizAccess.objects.get_or_create(
            user=self.user,
            quiz=self.quiz,
            defaults={'expires_at': timezone.now() + timedelta(days=30), 'is_active': True},
        )
        if not created and (access.expires_at <= timezone.now() or not access.is_active):
            access.expires_at = timezone.now() + timedelta(days=30)
            access.is_active  = True
            access.save()
        UserQuizAccess.objects.filter(user=self.user, quiz=self.quiz).exclude(id=access.id).delete()

    def _grant_imitation_quiz_access(self):
        from imitation_quiz.models.imitation_quiz import UserImitationQuizAccess
        access, created = UserImitationQuizAccess.objects.get_or_create(
            user=self.user,
            imitation_quiz=self.imitation_quiz,
            defaults={'expires_at': timezone.now() + timedelta(days=30), 'is_active': True},
        )
        if not created and (access.expires_at <= timezone.now() or not access.is_active):
            access.expires_at = timezone.now() + timedelta(days=30)
            access.is_active  = True
            access.save()
        UserImitationQuizAccess.objects.filter(
            user=self.user, imitation_quiz=self.imitation_quiz
        ).exclude(id=access.id).delete()

    def _grant_category_access(self):
        access, created = UserCategoryAccess.objects.get_or_create(
            user=self.user,
            category=self.category,
            defaults={'expires_at': timezone.now() + timedelta(days=30), 'is_active': True},
        )
        if not created and (access.expires_at <= timezone.now() or not access.is_active):
            access.expires_at = timezone.now() + timedelta(days=30)
            access.is_active  = True
            access.save()
        UserCategoryAccess.objects.filter(
            user=self.user, category=self.category
        ).exclude(id=access.id).delete()

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.save()

        if self.quiz:
            self._grant_quiz_access()
        elif self.imitation_quiz:
            self._grant_imitation_quiz_access()
        elif self.category and self.category.is_paid:
            self._grant_category_access()

    def mark_failed(self):
        self.status = self.STATUS_FAILED
        self.save()
