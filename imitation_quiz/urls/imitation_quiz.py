from django.urls import path
from ..views import imitation_quiz

urlpatterns = [
    path('category/<int:category_id>/quizzes/', imitation_quiz.ImitationQuizListView.as_view(), name='quiz-list'),

    path('quizzes/<int:quiz_id>/access/', 
         imitation_quiz.ImitationAccessView.as_view(), name='imitation-get-code'),

    path('attempts/<code>/start/', 
         imitation_quiz.ImitationStartView.as_view(), name='imitation-start'),
     
    path('attempts/<code>/complete/', 
         imitation_quiz.CompleteAttemptView.as_view(), name='imitation-complete'),

    path('attempts/<code>/questions/', 
         imitation_quiz.ImitationQuestionsView.as_view(), name='imitation-questions'),
    
    path('attempts/<code>/answer/', 
         imitation_quiz.ImitationAnswerView.as_view(), name='imitation-answer'),
    
    path('attempts/<code>/result/', 
         imitation_quiz.ImitationResultView.as_view(), name='imitation-result'),
]