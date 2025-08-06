from django.contrib import admin
from .models.category import Category, UserCategoryAccess
from .models.quiz import Quiz, QuizAttempt, Question, UserAnswer, Topic
from django import forms
from ckeditor_uploader.widgets import CKEditorUploadingWidget


admin.site.register(Topic)

admin.site.register(Category)

admin.site.register(UserCategoryAccess)

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]


class QuestionAdminForm(forms.ModelForm):
    explanation = forms.CharField(widget=CKEditorUploadingWidget(config_name='default'))
  
    class Meta:
        model = Question
        fields = '__all__'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm

    class Media:
        css = {
            'all': [
                'https://unpkg.com/mathlive/dist/mathlive.core.css',
                'https://unpkg.com/mathlive/dist/mathlive.css',
            ]
        }
        js = [
            'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js',
        ]

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'status', 'started_at']
    list_filter = ['status', 'quiz__category', 'started_at']
    search_fields = ['user__username', 'user__email', 'quiz__title']
    readonly_fields = ['started_at']

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'score_earned', 'time_taken', 'answered_at']
    list_filter = ['answered_at']
    search_fields = ['attempt__user__username']
    readonly_fields = ['answered_at']