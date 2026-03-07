from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from core.utils import image_upload, validate_image
from django.core.exceptions import ValidationError
import random
from datetime import timedelta
from django.utils.timezone import now

def upload_image(instance, filename):
    return image_upload(instance, filename, 'avatars/')


class User(AbstractBaseUser):
    firstname = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    email_verified = models.DateTimeField(null=True, blank=True)

    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname']

    def save(self, *args, **kwargs):
        self.firstname = self.firstname.capitalize()
        self.lastname = self.lastname.capitalize()
        if self.pk is None: 
            self.set_password(self.password) 
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firstname} {self.lastname} - {self.email}"

class Avatar(models.Model):
    url = models.ImageField(upload_to=upload_image, null=True, blank=True)
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="avatar")

    def save(self, *args, **kwargs):
        if self.url:
            try:
                self.url = validate_image(image_field=self.url, max_size_kb=1200, compress_quality=75, path='avatars/')
            except (FileNotFoundError, ValueError, ValidationError):
                self.url = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.firstname} {self.user.lastname} | {self.url}"

class Preferences(models.Model):
    theme_color = models.CharField(max_length=255)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")

    def __str__(self):
        return f"{self.user.firstname} {self.user.lastname} | {self.theme_color}"
    
class VerificationCode(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="verification_code")
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(auto_now=True)
    attempts_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return now() < self.created_at + timedelta(minutes=15)

    def can_resend(self):
        return now() > self.last_sent_at + timedelta(seconds=60)

    def reset_if_new_day(self):
        if self.last_attempt_at and self.last_attempt_at.date() < now().date():
            self.attempts_count = 0
            self.save()

    def generate_code(self):
        self.code = str(random.randint(100000, 999999))
        self.created_at = now()
        self.last_sent_at = now()
        self.save()