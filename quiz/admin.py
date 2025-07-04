from django.contrib import admin
from .models.category import Category, UserCategoryAccess
from .models.quiz import Quiz, QuizAttempt, Question, Answer, UserAnswer
from django import forms
from ckeditor_uploader.widgets import CKEditorUploadingWidget


admin.site.register(Category)

admin.site.register(UserCategoryAccess)



class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    inlines = [AnswerInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'quiz_type', 'difficulty', 
                   'is_tournament_active', 'created_at']
    list_filter = ['quiz_type', 'difficulty', 'category', 'created_at']
    search_fields = ['title', 'description', 'category__title']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [QuestionInline]


class QuestionAdminForm(forms.ModelForm):
    question_text = forms.CharField(widget=CKEditorUploadingWidget(config_name='default'))
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
    inlines = [AnswerInline]

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['question', 'answer_text', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__quiz__category']
    search_fields = ['answer_text', 'question__question_text']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'status', 'started_at']
    list_filter = ['status', 'quiz__quiz_type', 'quiz__category', 'started_at']
    search_fields = ['user__username', 'user__email', 'quiz__title']
    readonly_fields = ['started_at']


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'score_earned', 'time_taken', 'answered_at']
    list_filter = ['answered_at']
    search_fields = ['attempt__user__username', 'question__question_text']
    readonly_fields = ['answered_at']