from django.urls import path
from .views import EvaluateEssayView, EvaluateQuizView

urlpatterns = [
    path('evaluate-essay/', EvaluateEssayView.as_view(), name='evaluate-essay'),
    path('evaluate-quiz/', EvaluateQuizView.as_view(), name='evaluate-quiz'),
]
