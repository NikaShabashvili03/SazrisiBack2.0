from django.db import models
from django.utils import timezone
from datetime import timedelta
from ckeditor_uploader.fields import RichTextUploadingField

class Blog(models.Model):
    title = models.CharField(max_length=255)
    description = RichTextUploadingField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Blogs"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} | {self.description}"