from django.db import models
from django.utils import timezone
from datetime import timedelta


class Blog(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Blogs"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} | {self.description}"