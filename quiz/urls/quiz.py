from django.urls import path
from ..views import quiz

urlpatterns = [
    path('category/<int:categoryId>/quizzes/', quiz.QuizListView.as_view(), name='quiz-list'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/', quiz.QuizDetailView.as_view(), name='quiz-detail'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/start/', quiz.QuizStartView.as_view(), name='quiz-start'),

    path('attempts/<int:attempt_id>/questions', quiz.QuizQuestionsView.as_view(), name='quiz-question'),
    path('attempts/<int:attempt_id>/answer', quiz.QuizAnswerView.as_view(), name='quiz-answer'),

    path('statistics', quiz.Statistic.as_view(), name='statistics')
]