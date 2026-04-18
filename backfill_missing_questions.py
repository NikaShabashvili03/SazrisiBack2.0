#!/usr/bin/env python
"""
Scans every "მათემატიკა - XX" quiz and backfills any missing questions by
re-reading the corresponding solutions PDF from sol_output/.

For each quiz:
  1. Finds which question orders (1-37) are missing
  2. Opens sol_output/mixed_test_XX_solutions.pdf
  3. For each missing order N, reads page N, detects answer + score + topic
  4. Creates the Topic (get_or_create) and Question

Run from the SazrisiBack2.0/ directory:
    python backfill_missing_questions.py

Optional flags:
    --sols-dir PATH   Path to folder with solution PDFs (default: sol_output)
    --expected INT    Expected number of questions per quiz (default: 37)
    --dry-run         Print what would be created without writing to DB
    --quiz-id INT     Only backfill a specific quiz by ID
"""

import sys
import os
import re
import json
import argparse

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_solution_pages(pdf_path):
    """Return list of (page_index_1based, text) for every non-blank page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((i, text.strip()))
    return pages


def detect_answer(solution_text):
    pattern = r'(?:სწორი\s+)?პასუხი[:\s]*([აბგდ])\)'
    match = re.search(pattern, solution_text)
    if match:
        return GEO_ANSWER_MAP.get(match.group(1))
    return None


def detect_score(solution_text):
    match = re.search(r'(\d+)\s*ქულა', solution_text)
    return int(match.group(1)) if match else 1


def extract_topic_name(client, solution_text):
    prompt = TOPIC_PROMPT.format(solution_text=solution_text)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)["name"]


def quiz_num_str(quiz_title):
    """Extract zero-padded number from 'მათემატიკა - 01' → '01'."""
    m = re.search(r'-\s*(\d+)\s*$', quiz_title)
    return m.group(1).zfill(2) if m else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backfill missing Questions/Topics for მათემატიკა quizzes"
    )
    parser.add_argument("--sols-dir", default="sol_output",
                        help="Folder containing solution PDFs (default: sol_output)")
    parser.add_argument("--expected", type=int, default=37,
                        help="Expected questions per quiz (default: 37)")
    parser.add_argument("--quiz-id", type=int, default=None,
                        help="Only process a specific quiz by ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without writing to DB")
    args = parser.parse_args()

    if not os.path.isdir(args.sols_dir):
        print(f"Error: sols-dir not found: {args.sols_dir}")
        sys.exit(1)

    # ── Find quizzes to process ───────────────────────────────────────────────
    qs = Quiz.objects.filter(title__startswith="მათემატიკა - ")
    if args.quiz_id:
        qs = qs.filter(id=args.quiz_id)

    quizzes = list(qs.order_by("title"))
    if not quizzes:
        print("No matching quizzes found.")
        sys.exit(0)

    print(f"Found {len(quizzes)} quiz(zes) to check.\n")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    total_created  = 0
    total_skipped  = 0
    total_errors   = []

    for quiz in quizzes:
        num_str = quiz_num_str(quiz.title)
        if not num_str:
            print(f"[{quiz.title}] Could not parse number — skipping")
            continue

        sol_path = os.path.join(args.sols_dir, f"mixed_test_{num_str}_solutions.pdf")
        if not os.path.exists(sol_path):
            print(f"[{quiz.title}] Solutions PDF not found: {sol_path} — skipping")
            continue

        existing_orders = set(
            Question.objects.filter(quiz=quiz).values_list("order", flat=True)
        )
        missing_orders = sorted(
            set(range(1, args.expected + 1)) - existing_orders
        )

        print(f"[{quiz.title}]  id={quiz.id}  "
              f"existing={len(existing_orders)}  missing={len(missing_orders)}")

        if not missing_orders:
            print("  All questions present — nothing to do.\n")
            total_skipped += 1
            continue

        print(f"  Missing orders: {missing_orders}")
        print(f"  Reading: {sol_path}")

        s_pages = read_solution_pages(sol_path)
        print(f"  Solution pages found: {len(s_pages)}")

        questions_to_create = []
        errors = []

        for order in missing_orders:
            # page index is 0-based in our list; question order is 1-based
            page_idx = order - 1
            if page_idx >= len(s_pages):
                msg = f"page index {page_idx} out of range (only {len(s_pages)} pages)"
                print(f"  Q{order:02d} ERROR: {msg}")
                errors.append((order, msg))
                continue

            s_page_num, s_text = s_pages[page_idx]
            print(f"  Q{order:02d} (s_page={s_page_num})", end="  ")

            answer = detect_answer(s_text)
            if not answer:
                print("WARNING: could not detect answer — skipping")
                errors.append((order, "answer not detected"))
                continue

            score = detect_score(s_text)
            print(f"answer={answer}  score={score}  topic...", end=" ", flush=True)

            try:
                topic_name = extract_topic_name(client, s_text)
            except Exception as exc:
                print(f"ERROR: {exc}")
                errors.append((order, str(exc)))
                continue

            print(topic_name)

            if not args.dry_run:
                topic_obj, _ = Topic.objects.get_or_create(
                    name=topic_name,
                    defaults={"url": ""},
                )
                questions_to_create.append(
                    Question(
                        quiz=quiz,
                        topic=topic_obj,
                        answer=answer,
                        score=score,
                        order=order,
                    )
                )
            else:
                print(f"    [DRY RUN] Would create Q{order:02d}  answer={answer}  score={score}  topic={topic_name}")

        if questions_to_create:
            Question.objects.bulk_create(questions_to_create)
            print(f"  Created {len(questions_to_create)} question(s).")
            total_created += len(questions_to_create)

        if errors:
            total_errors.extend([(quiz.title, o, m) for o, m in errors])

        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("DONE")
    print(f"  Quizzes fully populated : {total_skipped}")
    print(f"  Questions created       : {total_created}")

    if total_errors:
        print(f"\nFailed ({len(total_errors)}):")
        for title, order, msg in total_errors:
            print(f"  [{title}] Q{order:02d}: {msg}")


if __name__ == "__main__":
    main()
