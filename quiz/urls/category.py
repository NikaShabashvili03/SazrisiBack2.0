from django.urls import path
from ..views import category

urlpatterns = [
    path('categories/', category.CategoryListView.as_view(), name='category-list'),
    path('categories/<int:id>/', category.CategoryDetailView.as_view(), name='category-detail'),
]