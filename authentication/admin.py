from django.contrib import admin
from .models import User, Payment, Avatar, Preferences, VerificationCode

class AvatarInline(admin.StackedInline):
    model = Avatar
    can_delete = False

class PreferencesInline(admin.StackedInline):
    model = Preferences
    can_delete = False

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = [AvatarInline, PreferencesInline]
    list_display = ('firstname', 'lastname', 'email', 'phone', 'phone_verified', 'last_login')

admin.site.register(Payment)
admin.site.register(VerificationCode)