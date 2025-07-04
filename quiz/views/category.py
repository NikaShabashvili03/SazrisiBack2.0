from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
import uuid
from rest_framework.views import APIView

from authentication.models.payment import Payment

from ..models.category import Category, UserCategoryAccess
from ..serializers.category import (
    CategorySerializer,
)

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class CategoryDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        category = get_object_or_404(Category, id=id)

        serializer = CategorySerializer(category, context={'request': request}).data
        return Response(serializer)