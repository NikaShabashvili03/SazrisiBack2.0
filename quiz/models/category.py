from django.db import models
from django.utils import timezone
from datetime import timedelta
from authentication.models.user import User


class Category(models.Model):
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['title']

    def has_access(self, user):
        if not user:
            return False

        return UserCategoryAccess.objects.filter(
            user=user,
            category=self,
            is_active=True,
            expires_at__gt=timezone.now()
        ).exists()


    def __str__(self):
        return f"{self.title} | {self.price} GEL ({'Paid' if self.is_paid else 'Free'})"
    

class UserCategoryAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='category_access')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='user_access')
    access_granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-access_granted_at']

    def __str__(self):
        return f"{self.user} has access to {self.category.title} until {self.expires_at}"

    @property
    def is_access_active(self):
        return self.is_active and timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)