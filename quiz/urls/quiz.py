from django.urls import path
from ..views import quiz

urlpatterns = [
    path('category/<int:categoryId>/quizzes/', quiz.QuizListView.as_view(), name='quiz-list'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/', quiz.QuizDetailView.as_view(), name='quiz-detail'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/start/', quiz.QuizStartView.as_view(), name='quiz-start'),

    path('attempts/<int:attempt_id>/question/<int:question_id>', quiz.QuizQuestionView.as_view(), name='quiz-question'),
    path('attempts/<int:attempt_id>/answer/', quiz.QuizAnswerView.as_view(), name='quiz-answer'),
    path('attempts/<int:attempt_id>/results/', quiz.QuizResultsView.as_view(), name='quiz-results'),
    
    # path('attempts/<int:attempt_id>/skip/', quiz.QuizSkipView.as_view(), name='quiz-skip'),

    path('attempts/<int:attempt_id>/navigation/', quiz.QuizNavigationView.as_view(), name='quiz-navigation'),
    
    path('my-attempts/', quiz.UserQuizHistoryView.as_view(), name='user-quiz-history'),
    path('my-stats/', quiz.QuizStatsView.as_view(), name='user-quiz-stats'),
]