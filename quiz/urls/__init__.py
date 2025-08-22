from django.urls import path, include

urlpatterns = [
    path('category/', include("quiz.urls.category")),
    path('quiz/', include("quiz.urls.quiz")),
    path('blog/', include("quiz.urls.blog"))
]