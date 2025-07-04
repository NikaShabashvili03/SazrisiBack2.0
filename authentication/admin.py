from django.contrib import admin
from .models import User, Payment

admin.site.register(User)
admin.site.register(Payment)