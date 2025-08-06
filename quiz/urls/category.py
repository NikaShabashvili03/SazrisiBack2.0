from django.urls import path
from ..views import category

urlpatterns = [
    path('list/', category.CategoryListView.as_view(), name='category-list'),
    path('details/<int:id>/', category.CategoryDetailView.as_view(), name='category-detail'),
]