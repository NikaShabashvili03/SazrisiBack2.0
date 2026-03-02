from django.urls import path, include

urlpatterns = [
    path('quiz/', include("imitation_quiz.urls.imitation_quiz"))
]