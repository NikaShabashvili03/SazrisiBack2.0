import json
from google import genai

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

MODEL = "gemini-2.0-flash"


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _parse_gemini_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        parts = text.split('```')
        text = parts[1] if len(parts) > 1 else text
        if text.startswith('json'):
            text = text[4:]
    return json.loads(text.strip())


class EvaluateEssayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        essay        = request.data.get('essay', '').strip()
        topic_title  = request.data.get('topic_title', '')
        topic_prompt = request.data.get('topic_prompt', '')

        if not essay:
            return Response({'error': 'Essay is required'}, status=status.HTTP_400_BAD_REQUEST)

        prompt = f"""შენ ხარ ქართული ენის და ლიტერატურის გამოცდების ექსპერტი შემფასებელი.
შეაფასე მოსწავლის ნარკვევი სახელმწიფო გამოცდის კრიტერიუმებით.

თემა: {topic_title}
დავალება: {topic_prompt}

ნარკვევი:
{essay}

გთხოვ შეაფასო ნარკვევი და დააბრუნო პასუხი მხოლოდ JSON ფორმატში შემდეგი სტრუქტურით:
{{
  "score": "X/100",
  "overall_feedback": "ზოგადი შეფასება ქართულად (2-3 წინადადება)",
  "strengths": ["ძლიერი მხარე 1", "ძლიერი მხარე 2", "ძლიერი მხარე 3"],
  "improvements": ["გასაუმჯობესებელი 1", "გასაუმჯობესებელი 2", "გასაუმჯობესებელი 3"],
  "language_quality": "ენობრივი ხარისხის შეფასება (1 წინადადება)",
  "structure": "სტრუქტურის შეფასება (1 წინადადება)",
  "advice": "პრაქტიკული რჩევები სამომავლოდ (2-3 წინადადება)"
}}

შეფასების კრიტერიუმები:
- შინაარსი და არგუმენტაცია (40 ქულა)
- ენობრივი სისწორე და სტილი (30 ქულა)
- სტრუქტურა და ლოგიკა (20 ქულა)
- კრეატიულობა და ორიგინალობა (10 ქულა)

პასუხი მხოლოდ JSON, სხვა ტექსტი არ დაამატო."""

        try:
            response = _get_client().models.generate_content(model=MODEL, contents=prompt)
            result   = _parse_gemini_json(response.text)
            return Response(result)
        except json.JSONDecodeError:
            return Response(
                {'error': 'AI პასუხის დამუშავება ვერ მოხერხდა. სცადეთ თავიდან.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EvaluateQuizView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        score           = request.data.get('score', 0)
        total_questions = request.data.get('total_questions', 0)
        correct_answers = request.data.get('correct_answers', 0)
        percentage      = request.data.get('percentage', '0')
        time_taken      = request.data.get('time_taken', 0)
        quiz_title      = request.data.get('quiz_title', 'ქვიზი')

        prompt = f"""შენ ხარ სასწავლო კონსულტანტი და მოსწავლეთა მხარდამჭერი.
გააანალიზე მოსწავლის ქვიზის შედეგი და მიეცი პრაქტიკული, მამოტივირებელი რჩევები.

ქვიზი: {quiz_title}
შეგროვებული ქულა: {score}
სულ კითხვები: {total_questions}
სწორი პასუხები: {correct_answers}/{total_questions}
პროცენტი: {percentage}%
დახარჯული დრო: {time_taken} წამი

გთხოვ დააბრუნო პასუხი მხოლოდ JSON ფორმატში:
{{
  "performance_summary": "შესრულების მოკლე შეჯამება (2 წინადადება)",
  "strengths": ["ძლიერი მხარე 1", "ძლიერი მხარე 2"],
  "areas_to_improve": ["გასაუმჯობესებელი სფერო 1", "გასაუმჯობესებელი სფერო 2"],
  "study_recommendations": ["სასწავლო რჩევა 1", "სასწავლო რჩევა 2", "სასწავლო რჩევა 3"],
  "motivational_message": "მამოტივირებელი შეტყობინება მოსწავლეს (1-2 წინადადება)",
  "next_steps": "კონკრეტული შემდეგი ნაბიჯები (2 წინადადება)"
}}

პასუხი მხოლოდ JSON, სხვა ტექსტი არ დაამატო."""

        try:
            response = _get_client().models.generate_content(model=MODEL, contents=prompt)
            result   = _parse_gemini_json(response.text)
            return Response(result)
        except json.JSONDecodeError:
            return Response(
                {'error': 'AI პასუხის დამუშავება ვერ მოხერხდა. სცადეთ თავიდან.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
