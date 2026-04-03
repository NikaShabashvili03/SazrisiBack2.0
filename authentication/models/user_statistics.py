from django.db import models
from .user import User


class UserStatistics(User):
    class Meta:
        proxy = True
        verbose_name = "User Statistics"
        verbose_name_plural = "User Statistics"