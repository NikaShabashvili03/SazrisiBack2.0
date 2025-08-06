from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import doc_view


urlpatterns = [
    path('docs/', doc_view, name='doc'),
    path('admin/', admin.site.urls),
    path('api/v1/', include("authentication.urls")),
    path('api/v2/', include("quiz.urls")),
    path('ckeditor/', include('ckeditor_uploader.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)