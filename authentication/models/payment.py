from . import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
from quiz.models.category import Category, UserCategoryAccess

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='GEL')
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} - {self.user} - {self.amount} {self.currency}"

    def mark_completed(self):
        self.save()
        
        if self.category and self.category.is_paid:
            access, created = UserCategoryAccess.objects.get_or_create(
                user=self.user,
                category=self.category,
                defaults={
                    'expires_at': timezone.now() + timedelta(days=30),
                    'is_active': True
                }
            )
            
            
            if not created and (access.expires_at <= timezone.now() or not access.is_active):
                access.expires_at = timezone.now() + timedelta(days=30)
                access.is_active = True
                access.save()
        
            duplicates = UserCategoryAccess.objects.filter(
                user=self.user,
                category=self.category
            ).exclude(id=access.id)
            
            if duplicates.exists():
                duplicates.delete()