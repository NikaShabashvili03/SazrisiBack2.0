from . import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
          verbose_name = _("Session")
          verbose_name_plural = _("Sessions")

    def clean(self):
          if not self.user:
               raise ValidationError(_("Either a user must be set."))
          
    def is_valid(self):
         return f"{self.session_token}"
    
    def __str__(self):
         return f"{self.created_at} / {self.expires_at}"