from django.contrib import admin
from django import forms
from .models.imitation_quiz import (
    ImitationQuiz, 
    ImitationQuestion, 
    ImitationAttempt, 
    ImitationUserAnswer
)

# --- Inlines ---

from django.contrib import admin
from django import forms
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.db.models import Count, Avg, Max
from django.utils.html import format_html

from .models.imitation_quiz import (
    ImitationQuiz,
    ImitationQuestion,
    ImitationAttempt,
    ImitationUserAnswer,
    ImitationTopic
)

from .models.quiz_statistics import QuizStatistics

# -----------------------------
# Inlines
# -----------------------------

class ImitationQuestionInline(admin.StackedInline):
    model = ImitationQuestion
    extra = 1
    fields = ["order", "answer", "score"]


# -----------------------------
# Forms
# -----------------------------

class ImitationQuestionAdminForm(forms.ModelForm):
    class Meta:
        model = ImitationQuestion
        fields = "__all__"


# -----------------------------
# Default Quiz Admin
# -----------------------------

@admin.register(ImitationQuiz)
class ImitationQuizAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "time_limit", "user_count", "status", "created_at"]
    list_filter = ["category", "created_at", "start_datetime", "end_datetime"]
    search_fields = ["title", "location"]
    inlines = [ImitationQuestionInline]


@admin.register(ImitationQuestion)
class ImitationQuestionAdmin(admin.ModelAdmin):
    form = ImitationQuestionAdminForm
    list_display = ["quiz", "order", "answer", "score"]
    list_filter = ["quiz"]
    ordering = ["quiz", "order"]

    class Media:
        css = {
            "all": [
                "https://unpkg.com/mathlive/dist/mathlive.core.css",
                "https://unpkg.com/mathlive/dist/mathlive.css",
            ]
        }
        js = [
            "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
        ]


@admin.register(ImitationAttempt)
class ImitationAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "user",
        "imitation_quiz",
        "status",
        "score",
        "correct_answers",
        "total_questions",
        "percentage",
        "laptop_type",
        "started_at",
        "completed_at",
    ]
    list_filter = [
        "status",
        "laptop_type",
        "imitation_quiz__category",
        "started_at",
        "completed_at",
    ]
    search_fields = [
        "code",
        "user__firstname",
        "user__lastname",
        "user__phone",
        "user__email",
        "imitation_quiz__title",
    ]
    readonly_fields = [
        "code",
        "started_at",
        "completed_at",
        "time_taken",
    ]


@admin.register(ImitationUserAnswer)
class ImitationUserAnswerAdmin(admin.ModelAdmin):
    list_display = [
        "attempt",
        "question",
        "selected_answer",
        "is_correct",
        "score_earned",
        "answered_at",
    ]
    list_filter = ["is_correct", "answered_at"]
    search_fields = [
        "attempt__code",
        "attempt__user__firstname",
        "attempt__user__lastname",
        "attempt__user__phone",
        "attempt__user__email",
    ]
    readonly_fields = ["answered_at"]


# -----------------------------
# Quiz Statistics Admin
# -----------------------------

@admin.register(QuizStatistics)
class QuizStatisticsAdmin(admin.ModelAdmin):
    change_list_template = "admin/imitation_quiz/quiz_statistics_list.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            total_attempts_annotated=Count("attempts"),
            avg_score_annotated=Avg("attempts__score"),
            best_score_annotated=Max("attempts__score"),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:quiz_id>/users/",
                self.admin_site.admin_view(self.quiz_users_statistics_view),
                name="imitation_quiz_quizstatistics_users",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        quizzes = self.get_queryset(request).order_by("-created_at")

        extra_context = extra_context or {}
        extra_context["title"] = "Quiz Statistics"
        extra_context["quizzes"] = quizzes

        return super().changelist_view(request, extra_context=extra_context)

    def quiz_users_statistics_view(self, request, quiz_id):
        quiz = ImitationQuiz.objects.filter(id=quiz_id).first()

        attempts = (
            ImitationAttempt.objects
            .filter(imitation_quiz_id=quiz_id)
            .select_related("user", "imitation_quiz")
            .order_by("-score", "-percentage", "started_at")
        )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Users Statistics - {quiz.title if quiz else 'Quiz'}",
            "quiz": quiz,
            "attempts": attempts,
            "opts": self.model._meta,
            "has_view_permission": True,
        }

        return TemplateResponse(
            request,
            "admin/imitation_quiz/quiz_statistics_users.html",
            context,
        )
    

admin.site.register(ImitationTopic)