#!/usr/bin/env python
"""
Reads a quiz PDF (questions) and its solutions PDF, then for each question:
  1. Detects the correct answer (ა/ბ/გ/დ → a/b/g/d) from the solution text
  2. Extracts the score from the question text (e.g. "2 ქულა")
  3. Uses Gemini to identify the math topic from the solution text
  4. Creates a Topic (get_or_create) and a Question linked to the given Quiz

Run from the SazrisiBack2.0/ directory:
    python add_questions_from_pdf.py \\
        --questions path/to/test.pdf \\
        --solutions path/to/solutions.pdf \\
        --quiz-id 1

Optional flags:
    --dry-run   Print extracted data without writing to DB
"""

import sys
import os
import argparse
import json
import re

# ── Django setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()
# ─────────────────────────────────────────────────────────────────────────────

from django.conf import settings
from google import genai
import pdfplumber

from quiz.models.quiz import Quiz, Question, Topic

MODEL = "gemini-2.5-flash"

# Georgian answer letters to internal single-char codes
GEO_ANSWER_MAP = {
    'ა': 'a',
    'ბ': 'b',
    'გ': 'g',
    'დ': 'd',
}

TOPIC_PROMPT = """\
შემდეგი არის ქართული სამათემატიკო ტესტის ამოხსნა.
გამოიტანე მოკლე მათემატიკური თემის სახელი ქართულად.
მაგალითები: "წილადები", "მოდული", "პითაგორას თეორემა", "ალბათობა", "ლოგარითმები"

ამოხსნა:
{solution_text}

უპასუხე მხოლოდ JSON-ით, სხვა ტექსტის გარეშე:
{{"name": "..."}}"""


# ── PDF helpers ───────────────────────────────────────────────────────────────

def read_pdf_pages(pdf_path):
    """Return list of (page_index_1based, text) for every non-blank page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((i, text.strip()))
    return pages


def filter_question_pages(pages):
    """Keep only pages that contain a question block (ამოცანა keyword)."""
    return [(n, t) for n, t in pages if 'ამოცანა' in t]


# ── Data extraction ───────────────────────────────────────────────────────────

def detect_answer(solution_text):
    """
    Parse the correct-answer line from a solution page.
    Handles patterns like:
      "პასუხი: ბ) ..."
      "სწორი პასუხი: ა) ..."
    Returns one of 'a','b','g','d' or None.
    """
    pattern = r'(?:სწორი\s+)?პასუხი[:\s]*([აბგდ])\)'
    match = re.search(pattern, solution_text)
    if match:
        return GEO_ANSWER_MAP.get(match.group(1))
    return None


def detect_score(question_text):
    """
    Parse the point value from a question page, e.g. '2 ქულა' → 2.
    Defaults to 1 if nothing is found.
    """
    match = re.search(r'(\d+)\s*ქულა', question_text)
    return int(match.group(1)) if match else 1


def extract_topic_name(client, solution_text):
    """Call Gemini to get a short Georgian math topic name."""
    prompt = TOPIC_PROMPT.format(solution_text=solution_text)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)["name"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Seed Questions + Topics from quiz PDFs into a Quiz"
    )
    parser.add_argument("--questions", required=True, help="Path to the questions PDF")
    parser.add_argument("--solutions", required=True, help="Path to the solutions PDF")
    parser.add_argument("--quiz-id", required=True, type=int, help="ID of the Quiz to attach questions to")
    parser.add_argument("--dry-run", action="store_true", help="Print data without writing to DB")
    args = parser.parse_args()

    # ── Validate inputs ───────────────────────────────────────────────────────
    for path in (args.questions, args.solutions):
        if not os.path.exists(path):
            print(f"Error: file not found: {path}")
            sys.exit(1)

    try:
        quiz = Quiz.objects.get(id=args.quiz_id)
    except Quiz.DoesNotExist:
        print(f"Error: Quiz with id={args.quiz_id} does not exist")
        sys.exit(1)

    print(f"Quiz  : {quiz}")
    print(f"Dry   : {args.dry_run}\n")

    # ── Read PDFs ─────────────────────────────────────────────────────────────
    print(f"Reading questions PDF : {args.questions}")
    q_pages = filter_question_pages(read_pdf_pages(args.questions))
    print(f"  → {len(q_pages)} question pages\n")

    print(f"Reading solutions PDF : {args.solutions}")
    s_pages = read_pdf_pages(args.solutions)
    print(f"  → {len(s_pages)} solution pages\n")

    count = min(len(q_pages), len(s_pages))
    if len(q_pages) != len(s_pages):
        print(f"Warning: page counts differ ({len(q_pages)} vs {len(s_pages)}). Processing {count} pairs.\n")

    # ── Process pairs ─────────────────────────────────────────────────────────
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    collected = []   # list of dicts: {order, answer, score, topic_name}
    errors = []

    for i in range(count):
        q_page_num, q_text = q_pages[i]
        s_page_num, s_text = s_pages[i]
        order = i + 1

        print(f"Q{order:02d}  (q_page={q_page_num}, s_page={s_page_num})", end="  ")

        answer = detect_answer(s_text)
        if not answer:
            print("⚠  Could not detect answer — skipping")
            errors.append((order, "answer not detected"))
            continue

        score = detect_score(q_text)

        print(f"answer={answer}  score={score}  topic...", end=" ", flush=True)

        try:
            topic_name = extract_topic_name(client, s_text)
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors.append((order, str(exc)))
            continue

        print(topic_name)
        collected.append({
            "order": order,
            "answer": answer,
            "score": score,
            "topic_name": topic_name,
        })

    print(f"\nExtracted {len(collected)} questions  ({len(errors)} errors)\n")

    if args.dry_run:
        print("=== DRY RUN — nothing written ===")
        for item in collected:
            print(f"  Q{item['order']:02d}  answer={item['answer']}  score={item['score']}  topic={item['topic_name']}")
        if errors:
            _print_errors(errors)
        return

    # ── Write to DB ───────────────────────────────────────────────────────────
    new_topics = 0
    new_questions = 0
    skipped = 0

    questions_to_create = []

    for item in collected:
        topic_obj, t_created = Topic.objects.get_or_create(
            name=item["topic_name"],
            defaults={"url": ""},
        )
        if t_created:
            new_topics += 1

        # Skip if a question with this order already exists for this quiz
        if Question.objects.filter(quiz=quiz, order=item["order"]).exists():
            print(f"  Q{item['order']:02d} already exists — skipped")
            skipped += 1
            continue

        questions_to_create.append(
            Question(
                quiz=quiz,
                topic=topic_obj,
                answer=item["answer"],
                score=item["score"],
                order=item["order"],
            )
        )

    # bulk_create bypasses the model's save() auto-order logic so our explicit
    # order values (including order=1) are preserved as-is.
    if questions_to_create:
        Question.objects.bulk_create(questions_to_create)
        new_questions = len(questions_to_create)

    print(f"\nDone.")
    print(f"  Topics   created : {new_topics}")
    print(f"  Questions created: {new_questions}")
    print(f"  Questions skipped: {skipped}")

    if errors:
        _print_errors(errors)


def _print_errors(errors):
    print(f"\nFailed questions ({len(errors)}):")
    for order, msg in errors:
        print(f"  Q{order:02d}: {msg}")


if __name__ == "__main__":
    main()
