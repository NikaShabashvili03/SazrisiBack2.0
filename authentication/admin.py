from django.contrib import admin
from .models import User, Payment, Avatar, Preferences

class AvatarInline(admin.StackedInline):
    model = Avatar
    can_delete = False

class PreferencesInline(admin.StackedInline):
    model = Preferences
    can_delete = False

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = [AvatarInline, PreferencesInline]
    list_display = ('firstname', 'lastname', 'email', 'email_verified', 'last_login')

admin.site.register(Payment)