import json
import re
import time as time_module
from typing import Any, Dict

from google import genai

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
MAX_RETRIES = 2


def _parse_gemini_json(text: str) -> Dict[str, Any]:
    if not text:
        raise json.JSONDecodeError("Empty response", "", 0)

    cleaned = text.strip()

    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _call_gemini(prompt: str, model: str, json_mode: bool = False):
    with genai.Client(api_key=settings.GEMINI_API_KEY) as client:
        kwargs: Dict[str, Any] = {
            "model": model,
            "contents": prompt,
        }
        if json_mode:
            kwargs["config"] = {"response_mime_type": "application/json"}
        return client.models.generate_content(**kwargs)


def _generate_gemini_response(prompt: str, json_mode: bool = False):
    return _call_gemini(prompt, MODEL, json_mode=json_mode)


def _generate_with_retry(prompt: str, json_mode: bool = False, max_retries: int = MAX_RETRIES):
    last_error = None
    models_to_try = [MODEL, *FALLBACK_MODELS]

    for model in models_to_try:
        for attempt_num in range(max_retries):
            try:
                response = _call_gemini(prompt, model, json_mode=json_mode)
                if getattr(response, "text", None):
                    return response, None
                last_error = "AI-მ ცარიელი პასუხი დააბრუნა."
            except Exception as err:
                last_error = f"{model}: {err}"
            if attempt_num < max_retries - 1:
                time_module.sleep(2 ** attempt_num)

    return None, last_error or "AI-მ ცარიელი პასუხი დააბრუნა."


class EvaluateEssayView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        essay = str(request.data.get("essay", "")).strip()
        topic_title = str(request.data.get("topic_title", "")).strip()
        topic_prompt = str(request.data.get("topic_prompt", "")).strip()

        if not essay:
            return Response(
                {"error": "Essay is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            response, err = _generate_with_retry(prompt, json_mode=True)
            if response is None:
                return Response(
                    {"error": err},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            result = _parse_gemini_json(response.text)
            return Response(result, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response(
                {"error": "AI პასუხის დამუშავება ვერ მოხერხდა. სცადეთ თავიდან."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class EvaluateQuizView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        score = request.data.get("score", 0)
        total_questions = request.data.get("total_questions", 0)
        correct_answers = request.data.get("correct_answers", 0)
        percentage = request.data.get("percentage", "0")
        time_taken = request.data.get("time_taken", 0)
        quiz_title = str(request.data.get("quiz_title", "ქვიზი")).strip()

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
            response, err = _generate_with_retry(prompt, json_mode=True)
            if response is None:
                return Response(
                    {"error": err},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            result = _parse_gemini_json(response.text)
            return Response(result, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response(
                {"error": "AI პასუხის დამუშავება ვერ მოხერხდა. სცადეთ თავიდან."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
