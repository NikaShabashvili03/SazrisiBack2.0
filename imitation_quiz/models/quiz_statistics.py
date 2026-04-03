from .imitation_quiz import ImitationQuiz


class QuizStatistics(ImitationQuiz):
    class Meta:
        proxy = True
        verbose_name = "Quiz Statistics"
        verbose_name_plural = "Quiz Statistics"