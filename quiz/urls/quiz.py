from django.urls import path
from ..views import quiz

urlpatterns = [
    path('category/<int:categoryId>/quizzes/', quiz.QuizListView.as_view(), name='quiz-list'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/', quiz.QuizDetailView.as_view(), name='quiz-detail'),
    path('category/<int:categoryId>/quizzes/<int:quiz_id>/start/', quiz.QuizStartView.as_view(), name='quiz-start'),

    path('attempts/<int:attempt_id>/questions', quiz.QuizQuestionsView.as_view(), name='quiz-question'),
    path('attempts/<int:attempt_id>/answer', quiz.QuizAnswerView.as_view(), name='quiz-answer'),
    path('attempts/<int:attempt_id>/result', quiz.QuizResultView.as_view(), name='view-attempt'),
    path('attempts/<int:attempt_id>/ai-summary/', quiz.AttemptAISummaryView.as_view(), name='quiz-ai-summary'),

    path('ai-summaries/', quiz.QuizAISummaryHistoryView.as_view(), name='quiz-ai-summary-history'),

    path('statistics', quiz.Statistic.as_view(), name='statistics'),

    path("attempts/<int:attempt_id>/notes/", quiz.BlackNoteListCreateView.as_view(), name="blacknote-list-create"),
    path("notes/<int:note_id>/", quiz.BlackNoteDeleteView.as_view(), name="blacknote-delete"),

    path('leaderboard', quiz.LeaderboardView.as_view(), name='leaderboard'),

    path('topics/<int:topic_id>/', quiz.QuizTopicDetailView.as_view(), name='quiz-topic-detail'),
    path('topics/<int:topic_id>/ai-insights/', quiz.QuizTopicAIInsightsView.as_view(), name='quiz-topic-ai-insights'),
]