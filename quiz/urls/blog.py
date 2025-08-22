from django.urls import path
from ..views import blog

urlpatterns = [
    path('list/', blog.BlogListAPIView.as_view(), name='blog-list'),
    path('details/<int:id>/', blog.BlogDetailAPIView.as_view(), name='blog-detail'),
]