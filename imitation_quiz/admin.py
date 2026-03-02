from django.contrib import admin
from django import forms
from .models.imitation_quiz import (
    ImitationQuiz, 
    ImitationQuestion, 
    ImitationAttempt, 
    ImitationUserAnswer
)

# --- Inlines ---

class ImitationQuestionInline(admin.StackedInline):
    model = ImitationQuestion
    extra = 1
    fields = ['order', 'answer', 'score']

# --- Forms ---

class ImitationQuestionAdminForm(forms.ModelForm):
    class Meta:
        model = ImitationQuestion
        fields = '__all__'

# --- Admin Classes ---

@admin.register(ImitationQuiz)
class ImitationQuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'time_limit', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title']
    inlines = [ImitationQuestionInline]

@admin.register(ImitationQuestion)
class ImitationQuestionAdmin(admin.ModelAdmin):
    form = ImitationQuestionAdminForm
    list_display = ['quiz', 'order', 'answer', 'score']
    list_filter = ['quiz']
    ordering = ['quiz', 'order']

    # მათემატიკური ფორმულების მხარდაჭერა (MathLive/MathJax)
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

@admin.register(ImitationAttempt)
class ImitationAttemptAdmin(admin.ModelAdmin):
    # აქ დავამატე 'code' ველი, რადგან იმიტაციაში ეს მთავარია
    list_display = ['code', 'user', 'imitation_quiz', 'status', 'score', 'started_at']
    list_filter = ['status', 'imitation_quiz__category', 'started_at']
    search_fields = ['code', 'user__username', 'user__email', 'imitation_quiz__title']
    readonly_fields = ['code', 'started_at', 'completed_at']

@admin.register(ImitationUserAnswer)
class ImitationUserAnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'selected_answer', 'is_correct', 'score_earned', 'answered_at']
    list_filter = ['is_correct', 'answered_at']
    search_fields = ['attempt__code', 'attempt__user__username']
    readonly_fields = ['answered_at']