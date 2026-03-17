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
    phone = models.CharField(max_length=20, unique=True)
    phone_verified = models.DateTimeField(null=True, blank=True)
    
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'phone' 
    REQUIRED_FIELDS = ['firstname', 'lastname', 'email']

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
    PURPOSE_REGISTER = "register"
    PURPOSE_RESET = "reset"

    PURPOSE_CHOICES = (
        (PURPOSE_REGISTER, "Register"),
        (PURPOSE_RESET, "Reset Password"),
    )

    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)

    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        unique_together = ("phone", "purpose")

    def generate_code(self):
        self.code = str(random.randint(100000, 999999))
        self.is_used = False
        self.expires_at = now() + timedelta(minutes=10)
        self.save(update_fields=["code", "is_used", "expires_at", "updated_at"])

    def can_resend(self):
        if not self.updated_at:
            return True
        return now() >= self.updated_at + timedelta(seconds=60)

    def is_valid(self, code: str):
        return (
            not self.is_used
            and self.code == str(code)
            and self.expires_at is not None
            and self.expires_at >= now()
        )

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used", "updated_at"])

    def __str__(self):
        return f"{self.phone} - {self.purpose}"