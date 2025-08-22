from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from ..models import Blog
from ..serializers.blog import BlogListSerializer, BlogDetailSerializer
from rest_framework.permissions import IsAuthenticated


class BlogListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        blogs = Blog.objects.all()

        search = request.query_params.get("search")
        if search:
            blogs = blogs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(created_at__icontains=search)
            )

        sort = request.query_params.get("sort", "-created_at")
        blogs = blogs.order_by(sort)

        serializer = BlogListSerializer(blogs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BlogDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, id):
        try:
            blog = Blog.objects.get(id=id)
        except Blog.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = BlogDetailSerializer(blog)
        return Response(serializer.data, status=status.HTTP_200_OK)