from django.contrib import admin
from django.db.models import Count, Sum, Avg, Max, Q

from .models import User, Payment, Avatar, Preferences, VerificationCode, UserStatistics


class AvatarInline(admin.StackedInline):
    model = Avatar
    extra = 0
    can_delete = False

class PreferencesInline(admin.StackedInline):
    model = Preferences
    extra = 0
    can_delete = False


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = [AvatarInline, PreferencesInline]
    list_display = (
        "id",
        "firstname",
        "lastname",
        "email",
        "phone",
        "phone_verified",
        "last_login",
        "created_at",
    )
    search_fields = ("firstname", "lastname", "email", "phone")
    list_filter = ("phone_verified", "created_at")
    readonly_fields = ("last_login", "created_at")


@admin.register(UserStatistics)
class UserStatisticsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "phone",
        "email",
        "attempts_count",
        "completed_attempts",
        "total_score",
        "best_score",
        "avg_percentage",
        "last_attempt_at",
    )

    search_fields = (
        "firstname",
        "lastname",
        "phone",
        "email",
    )

    list_filter = (
        "phone_verified",
        "created_at",
    )

    readonly_fields = (
        "firstname",
        "lastname",
        "phone",
        "email",
        "phone_verified",
        "created_at",
        "last_login",
    )

    fieldsets = (
        ("User", {
            "fields": (
                "firstname",
                "lastname",
                "phone",
                "email",
                "phone_verified",
            )
        }),
        ("Dates", {
            "fields": (
                "created_at",
                "last_login",
            )
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            attempts_count_annotated=Count("imitation_attempts", distinct=True),
            completed_attempts_annotated=Count(
                "imitation_attempts",
                filter=Q(imitation_attempts__status="completed"),
                distinct=True,
            ),
            total_score_annotated=Sum("imitation_attempts__score"),
            best_score_annotated=Max("imitation_attempts__score"),
            avg_percentage_annotated=Avg("imitation_attempts__percentage"),
            last_attempt_at_annotated=Max("imitation_attempts__started_at"),
        )

    @admin.display(description="Full Name")
    def full_name(self, obj):
        return f"{obj.firstname} {obj.lastname}"

    @admin.display(description="Attempts", ordering="attempts_count_annotated")
    def attempts_count(self, obj):
        return obj.attempts_count_annotated or 0

    @admin.display(description="Completed", ordering="completed_attempts_annotated")
    def completed_attempts(self, obj):
        return obj.completed_attempts_annotated or 0

    @admin.display(description="Total Score", ordering="total_score_annotated")
    def total_score(self, obj):
        return obj.total_score_annotated or 0

    @admin.display(description="Best Score", ordering="best_score_annotated")
    def best_score(self, obj):
        return obj.best_score_annotated or 0

    @admin.display(description="Average %", ordering="avg_percentage_annotated")
    def avg_percentage(self, obj):
        if obj.avg_percentage_annotated is None:
            return "0.00%"
        return f"{obj.avg_percentage_annotated:.2f}%"

    @admin.display(description="Last Attempt", ordering="last_attempt_at_annotated")
    def last_attempt_at(self, obj):
        return obj.last_attempt_at_annotated


admin.site.register(Payment)
admin.site.register(VerificationCode)