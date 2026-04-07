from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.imitation_quiz import (
    ImitationAISummary,
    ImitationAttempt,
    ImitationQuestion,
    ImitationQuiz,
    ImitationTopic,
    ImitationUserAnswer,
)
from ..serializers.imitation_quiz import (
    CompletedImitationQuizSerializer,
    ImitationAISummarySerializer,
    ImitationAttemptSerializer,
    ImitationQuestionSerializer,
    ImitationQuestionWithAnswerSerializer,
    ImitationQuizResultSerializer,
    ImitationQuizSerializer,
    ImitationTopicSerializer,
)


class ImitationQuizListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, category_id):
        quizzes = ImitationQuiz.objects.filter(category_id=category_id)
        serializer = ImitationQuizSerializer(quizzes, many=True, context={'request': request})
        return Response(serializer.data)


class CompletedImitationQuizList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        attempts = (
            ImitationAttempt.objects
            .filter(user=request.user, status="completed")
            .select_related("imitation_quiz")
        )

        quizzes = [a.imitation_quiz for a in attempts]

        return Response(
            CompletedImitationQuizSerializer(
                quizzes,
                many=True,
                context={"request": request}
            ).data
        )


class ImitationAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(ImitationQuiz, id=quiz_id)
        now = timezone.now()

        if not quiz.has_access(user=request.user):
            return Response(
                {"error": "ამ გამოცდაზე წვდომისათვის საჭიროა გადახდა", "requires_payment": True},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        laptop_type = request.data.get('laptop_type')

        if laptop_type not in ['my', 'company']:
            return Response(
                {"error": "არასწორი მოწყობილობის ტიპი. გამოიყენეთ 'my' ან 'company'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if now > quiz.start_datetime:
            return Response(
                {"error": "დასრულებულია"},
                status=status.HTTP_403_FORBIDDEN
            )

        has_attempt = ImitationAttempt.objects.filter(
            user=request.user,
            imitation_quiz=quiz
        ).exists()

        if not has_attempt:
            if laptop_type == 'company' and not quiz.is_laptop_available:
                return Response(
                    {"error": "კომპიუტერები აღარ არის ხელმისაწვდომი"},
                    status=status.HTTP_403_FORBIDDEN
                )

        if not has_attempt and not quiz.is_valid_space:
            return Response(
                {"error": "აღარ არის ადგილი ამ ქვიზში"},
                status=status.HTTP_403_FORBIDDEN
            )

        attempt, created = ImitationAttempt.objects.get_or_create(
            user=request.user,
            imitation_quiz=quiz,
            defaults={
                'laptop_type': laptop_type,
                'status': 'geted_attempt',
                'total_questions': quiz.get_total_questions(),
            }
        )

        if not created and attempt.laptop_type != laptop_type:
            attempt.laptop_type = laptop_type
            attempt.save(update_fields=['laptop_type'])

        return Response({
            "code": attempt.code,
            "status": attempt.status,
            "quiz_title": quiz.title
        }, status=status.HTTP_200_OK)


class ImitationStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if attempt.status == 'geted_attempt':
            attempt.status = 'started'
            attempt.started_at = timezone.now()
            attempt.save(update_fields=['status', 'started_at'])

        return Response(ImitationAttemptSerializer(attempt).data)


class ImitationQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if attempt.status == 'geted_attempt':
            return Response({"error": "ტესტი ჯერ არ არის გააქტიურებული"}, status=status.HTTP_403_FORBIDDEN)

        questions = (
            attempt.imitation_quiz.questions
            .prefetch_related('topics')
            .all()
            .order_by('order')
        )
        answered_ids = set(attempt.user_answers.values_list('question_id', flat=True))

        serialized_data = []
        for question in questions:
            if question.id in answered_ids:
                serialized = ImitationQuestionWithAnswerSerializer(
                    question,
                    context={"attempt_id": attempt.id}
                ).data
            else:
                serialized = ImitationQuestionSerializer(question).data
            serialized_data.append(serialized)

        return Response(serialized_data)


class ImitationAnswerView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if not attempt.imitation_quiz.is_active:
            return Response(
                {
                    "details": "ქვიზი არ არის აქტიური",
                    "start_date": attempt.imitation_quiz.start_datetime,
                    "end_date": attempt.imitation_quiz.end_datetime
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if attempt.status == 'geted_attempt':
            return Response({"error": "ტესტი ჯერ არ არის გააქტიურებული"}, status=status.HTTP_403_FORBIDDEN)

        if attempt.status == 'completed':
            return Response({"error": "ტესტი უკვე დასრულებულია"}, status=status.HTTP_400_BAD_REQUEST)

        question_id = request.data.get('question_id')
        selected_answer = request.data.get('selected_answer')
        time_taken = request.data.get('time_taken', 0)

        if question_id is None:
            return Response(
                {'error': 'No question ID provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not selected_answer:
            return Response(
                {'error': 'selected_answer is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        selected_answer = str(selected_answer).lower()
        valid_choices = [choice[0] for choice in ImitationQuestion.ANSWER_CHOICES]

        if selected_answer not in valid_choices:
            return Response(
                {'error': f'არასწორი არჩევანი. დასაშვებია მხოლოდ: {", ".join(valid_choices).upper()}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        question = get_object_or_404(
            ImitationQuestion,
            id=question_id,
            quiz=attempt.imitation_quiz
        )

        user_answer, created = ImitationUserAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_answer': selected_answer,
                'time_taken': time_taken
            }
        )

        if attempt.status == 'started':
            attempt.status = 'in_progress'
            attempt.save(update_fields=['status'])

        stats = attempt.user_answers.aggregate(
            total_correct=models.Count('id', filter=models.Q(is_correct=True)),
            total_earned=models.Sum('score_earned')
        )

        attempt.correct_answers = stats['total_correct'] or 0
        attempt.score = stats['total_earned'] or 0
        attempt.save(update_fields=['correct_answers', 'score'])
        attempt.calculate_results()

        return Response({
            "status": attempt.status,
            "is_correct": user_answer.is_correct,
            "selected": user_answer.selected_answer
        })


class CompleteAttemptView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code)

        if attempt.status in ['in_progress', 'started']:
            attempt.status = "completed"
            attempt.save(update_fields=['status'])
            return Response({"details": "ქვიზი წარმატებით დასრულდა"})

        return Response(
            {"details": f"Attempt cannot be completed. Current status: {attempt.status}"},
            status=400
        )


class ImitationResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, code):
        attempt = get_object_or_404(ImitationAttempt, code=code, user=request.user)

        if attempt.status != 'completed':
            return Response({"error": "ტესტი ჯერ არ არის დასრულებული"}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() < attempt.imitation_quiz.end_datetime:
            return Response(
                {"error": "doesnot active"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ImitationQuizResultSerializer(attempt, context={'request': request})
        return Response(serializer.data)


class TopicDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(ImitationTopic, id=topic_id)

        has_attempt = ImitationAttempt.objects.filter(
            user=request.user,
            status='completed',
            imitation_quiz__questions__topics=topic,
        ).exists()

        if not has_attempt:
            return Response(
                {"error": "ამ თემაზე წვდომა არ გაქვს"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(ImitationTopicSerializer(topic).data)


class TopicAIInsightsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, topic_id):
        from ai_feedback.views import _generate_gemini_response
        import json
        import time

        topic = get_object_or_404(ImitationTopic, id=topic_id)

        has_attempt = ImitationAttempt.objects.filter(
            user=request.user,
            status='completed',
            imitation_quiz__questions__topics=topic,
        ).exists()

        if not has_attempt:
            return Response(
                {"error": "ამ თემაზე წვდომა არ გაქვს"},
                status=status.HTTP_403_FORBIDDEN,
            )

        prompt = f"""შენ ხარ მათემატიკის პედაგოგი და სახელმწიფო გამოცდების ექსპერტი.
მოამზადე სრული სასწავლო მასალა შემდეგი თემის შესახებ:

თემა: {topic.name}
მოკლე აღწერა: {topic.description}

დააბრუნე პასუხი მხოლოდ JSON ფორმატში, ქართულ ენაზე:
{{
  "overall_info": "თემის ზოგადი მიმოხილვა (3-4 წინადადება) — რა არის, სად გამოიყენება, რატომ მნიშვნელოვანია",
  "detailed_info": "დეტალური ახსნა ფორმულებით, კანონებით, შინაარსობრივი განმარტებით (5-8 წინადადება)",
  "examples": [
    {{"task": "მაგალითი 1 — ამოცანის პირობა", "solution": "ამოხსნა ნაბიჯ-ნაბიჯ"}},
    {{"task": "მაგალითი 2 — ამოცანის პირობა", "solution": "ამოხსნა ნაბიჯ-ნაბიჯ"}},
    {{"task": "მაგალითი 3 — ამოცანის პირობა", "solution": "ამოხსნა ნაბიჯ-ნაბიჯ"}}
  ],
  "useful_links": [
    {{"title": "რესურსის სახელი", "url": "https://..."}},
    {{"title": "რესურსის სახელი", "url": "https://..."}}
  ]
}}

useful_links-ში მოიყვანე ძირითადად ქართულენოვანი ან ქართული საგამოცდო სისტემისთვის შესაფერისი რესურსები.
პასუხი მხოლოდ JSON, სხვა ტექსტი არ დაამატო."""

        try:
            max_retries = 3
            response = None
            last_error = None

            for attempt_num in range(max_retries):
                try:
                    response = _generate_gemini_response(prompt)
                    if getattr(response, "text", None):
                        break
                    last_error = "AI-მ ცარიელი პასუხი დააბრუნა."
                except Exception as retry_err:
                    last_error = str(retry_err)

                if attempt_num < max_retries - 1:
                    time.sleep(2 ** attempt_num)

            if not response or not getattr(response, "text", None):
                return Response({"error": last_error or "AI-მ ცარიელი პასუხი დააბრუნა."}, status=500)

            text = response.text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].strip()
                    if text.lower().startswith("json"):
                        text = text[4:].strip()

            result = json.loads(text)
            return Response(result, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response({"error": "AI პასუხის დამუშავება ვერ მოხერხდა."}, status=500)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class AttemptAISummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        from ai_feedback.views import _generate_gemini_response
        import time

        attempt = get_object_or_404(ImitationAttempt, code=code, user=request.user)

        if attempt.status != 'completed':
            return Response({"error": "ტესტი დასრულებული არ არის"}, status=400)

        all_questions = (
            attempt.imitation_quiz.questions
            .prefetch_related('topics')
            .all()
        )
        user_answers = {ua.question_id: ua for ua in attempt.user_answers.all()}

        failed_topics = []
        all_topics = []

        for q in all_questions:
            question_topics = list(q.topics.all())

            for topic in question_topics:
                all_topics.append(topic.name)

            ua = user_answers.get(q.id)
            if ua and not ua.is_correct:
                for topic in question_topics:
                    failed_topics.append(topic.name)

        all_topics_unique = list(dict.fromkeys(all_topics))
        failed_topics_unique = list(dict.fromkeys(failed_topics))

        all_topics_str = ", ".join(all_topics_unique) if all_topics_unique else "უცნობი"
        failed_str = ", ".join(failed_topics_unique) if failed_topics_unique else "არცერთი"
        time_taken = str(attempt.time_taken) if attempt.time_taken else "უცნობი"

        prompt = f"""შენ ხარ მათემატიკის პედაგოგი და სახელმწიფო გამოცდების ექსპერტი.
მოამზადე სრული, პერსონალიზებული სასწავლო გეგმა მოსწავლისთვის, ვინც ახლახან დაასრულა იმიტირებული გამოცდა.

გამოცდის შედეგები:
- სახელი: {attempt.imitation_quiz.title}
- ქულა: {attempt.score}
- სულ კითხვები: {attempt.total_questions}
- სწორი პასუხები: {attempt.correct_answers}/{attempt.total_questions}
- პროცენტი: {attempt.percentage}%
- დახარჯული დრო: {time_taken}
- გამოცდაზე წარმოდგენილი თემები: {all_topics_str}
- შეცდომები შემდეგ თემებში: {failed_str}

მოამზადე გრძელი, სტრუქტურირებული ანალიზი შემდეგი სექციებით:

1. **ზოგადი შეფასება**
2. **სუსტი მხარეები**
3. **სასწავლო გეგმა**
4. **პრიორიტეტები**
5. **პრაქტიკული რჩევები**
6. **შემდეგი ნაბიჯები**

პასუხი დაწერე ქართულად, დეტალურად, მამოტივირებელ ტონში. გამოიყენე markdown ფორმატირება. პასუხი უნდა იყოს მინიმუმ 400 სიტყვა."""

        try:
            max_retries = 3
            response = None
            last_error = None

            for attempt_num in range(max_retries):
                try:
                    response = _generate_gemini_response(prompt)
                    if getattr(response, "text", None):
                        break
                    last_error = "AI-მ ცარიელი პასუხი დააბრუნა."
                except Exception as retry_err:
                    last_error = str(retry_err)

                if attempt_num < max_retries - 1:
                    time.sleep(2 ** attempt_num)

            if not response or not getattr(response, "text", None):
                return Response({"error": last_error or "AI-მ ცარიელი პასუხი დააბრუნა."}, status=500)

            content = response.text.strip()

            summary = ImitationAISummary.objects.create(
                user=request.user,
                attempt=attempt,
                quiz_title=attempt.imitation_quiz.title,
                content=content,
            )

            return Response(
                ImitationAISummarySerializer(summary).data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class AISummaryHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        summaries = ImitationAISummary.objects.filter(user=request.user)
        return Response(ImitationAISummarySerializer(summaries, many=True).data)