from rest_framework import serializers
from ..models import Blog


class BlogListSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = ['id', 'title', 'description', 'created_at']

    def get_description(self, obj):
        if len(obj.description) > 100:
            return obj.description[:100] + "..."
        return obj.description


class BlogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'title', 'description', 'created_at', 'updated_at']