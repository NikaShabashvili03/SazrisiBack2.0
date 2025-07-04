from rest_framework import serializers
from ..models.category import Category, UserCategoryAccess
from django.utils import timezone

class CategorySerializer(serializers.ModelSerializer):
    has_access = serializers.SerializerMethodField()
    access_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'title', 'price', 'is_paid', 'description', 'has_access', 'access_expires_at']

    def get_has_access(self, obj):
        if not obj.is_paid:
            return True
        
        user = self.context.get('request').user
        return obj.has_access(user)

    def get_access_expires_at(self, obj):
        user = self.context.get('request').user
        if not user or user.is_anonymous or not obj.is_paid:
            return None
            
        try:
            access = UserCategoryAccess.objects.get(
                user=user,
                category=obj,
                expires_at__gt=timezone.now(),
                is_active=True
            )
            return access.expires_at
        except UserCategoryAccess.DoesNotExist:
            return None
        

class UserCategoryAccessSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    is_access_active = serializers.ReadOnlyField()

    class Meta:
        model = UserCategoryAccess
        fields = ['id', 'category', 'access_granted_at', 'expires_at', 'is_access_active']