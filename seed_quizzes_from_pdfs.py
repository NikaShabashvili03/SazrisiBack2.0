#!/usr/bin/env python
"""
Creates Quiz objects from paired test/solution PDFs in test_output/ and sol_output/,
uploads the PDF files to each quiz, then seeds Topics and Questions for each one.

For every matched pair (e.g. mixed_test_01.pdf / mixed_test_01_solutions.pdf) it:
  - Creates a Quiz with:
      title       : მათემატიკა - 01
      description : მათემატიკის ეროვნული გამოცდის იმიტაცია (37 ერთქულიანი დავალება)
      is_paid     : True
      price       : 3.00
      time_limit  : 90 minutes
      file        : the test PDF
      explanation : the solutions PDF
  - Reads each question/solution page pair
  - Detects answer (ა/ბ/გ/დ), score (ქულა), and topic (via Gemini)
  - Creates Topic (get_or_create) and Question records

Run from the SazrisiBack2.0/ directory:
    python seed_quizzes_from_pdfs.py --category-id 1

Optional flags:
    --tests-dir   PATH   Path to folder with test PDFs      (default: test_output)
    --sols-dir    PATH   Path to folder with solution PDFs  (default: sol_output)
    --time-limit  INT    Minutes per quiz                   (default: 90)
    --dry-run            Print extracted data without writing to DB
"""

import sys
import os
import re
import json
import argparse
import glob
from decimal import Decimal

# ── Django setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()
# ─────────────────────────────────────────────────────────────────────────────

from django.conf import settings
from django.core.files import File
from google import genai
import pdfplumber

from quiz.models.quiz import Quiz, Question, Topic
from quiz.models.category import Category

MODEL = "gemini-2.5-flash"

QUIZ_TITLE_TEMPLATE  = "მათემატიკა - {num}"
QUIZ_DESCRIPTION     = "მათემატიკის ეროვნული გამოცდის იმიტაცია (37 ერთქულიანი დავალება)"
QUIZ_PRICE           = Decimal("3.00")

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
    Handles: "პასუხი: ბ) ..."  /  "სწორი პასუხი: ა) ..."
    Returns one of 'a','b','g','d' or None.
    """
    pattern = r'(?:სწორი\s+)?პასუხი[:\s]*([აბგდ])\)'
    match = re.search(pattern, solution_text)
    if match:
        return GEO_ANSWER_MAP.get(match.group(1))
    return None


def detect_score(question_text):
    """Parse the point value, e.g. '2 ქულა' → 2. Defaults to 1."""
    match = re.search(r'(\d+)\s*ქულა', question_text)
    return int(match.group(1)) if match else 1


def extract_topic_name(client, solution_text):
    """Call Gemini to get a short Georgian math topic name."""
    prompt = TOPIC_PROMPT.format(solution_text=solution_text)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)["name"]


# ── Quiz creation ─────────────────────────────────────────────────────────────

def create_quiz(title, category, test_pdf_path, sol_pdf_path, time_limit, dry_run):
    """
    Create and persist a Quiz with both PDF files attached.
    Returns the Quiz instance (unsaved in dry-run mode).
    """
    quiz = Quiz(
        title=title,
        description=QUIZ_DESCRIPTION,
        category=category,
        is_paid=True,
        price=QUIZ_PRICE,
        time_limit=time_limit,
    )

    if dry_run:
        print(f"  [DRY RUN] Would create Quiz: {title!r}")
        return quiz

    with open(test_pdf_path, 'rb') as f_test:
        quiz.file.save(os.path.basename(test_pdf_path), File(f_test), save=False)

    with open(sol_pdf_path, 'rb') as f_sol:
        quiz.explanation.save(os.path.basename(sol_pdf_path), File(f_sol), save=False)

    quiz.save()
    print(f"  Created Quiz id={quiz.id} : {quiz.title!r}")
    return quiz


# ── Question seeding ──────────────────────────────────────────────────────────

def seed_questions(quiz, test_pdf_path, sol_pdf_path, client, dry_run):
    """
    Read a test/solution PDF pair, extract questions, and write them to DB.
    Returns (new_questions, new_topics, errors).
    """
    print(f"  Reading test PDF      : {test_pdf_path}")
    q_pages = filter_question_pages(read_pdf_pages(test_pdf_path))
    print(f"    → {len(q_pages)} question pages")

    print(f"  Reading solutions PDF : {sol_pdf_path}")
    s_pages = read_pdf_pages(sol_pdf_path)
    print(f"    → {len(s_pages)} solution pages")

    count = min(len(q_pages), len(s_pages))
    if len(q_pages) != len(s_pages):
        print(f"  Warning: page counts differ ({len(q_pages)} vs {len(s_pages)}). Processing {count} pairs.")

    collected = []
    errors = []

    for i in range(count):
        q_page_num, q_text = q_pages[i]
        s_page_num, s_text = s_pages[i]
        order = i + 1

        print(f"    Q{order:02d} (q_page={q_page_num}, s_page={s_page_num})", end="  ")

        answer = detect_answer(s_text)
        if not answer:
            print("WARNING: could not detect answer — skipping")
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

    print(f"  Extracted {len(collected)} questions  ({len(errors)} errors)")

    if dry_run:
        print("  [DRY RUN] Would create questions:")
        for item in collected:
            print(f"    Q{item['order']:02d}  answer={item['answer']}  score={item['score']}  topic={item['topic_name']}")
        return 0, 0, errors

    # Write to DB
    new_topics = 0
    questions_to_create = []
    skipped = 0

    for item in collected:
        topic_obj, t_created = Topic.objects.get_or_create(
            name=item["topic_name"],
            defaults={"url": ""},
        )
        if t_created:
            new_topics += 1

        if Question.objects.filter(quiz=quiz, order=item["order"]).exists():
            print(f"    Q{item['order']:02d} already exists — skipped")
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
    print(f"  Topics created: {new_topics}  Questions created: {new_questions}  Skipped: {skipped}")
    return new_questions, new_topics, errors


# ── File discovery ────────────────────────────────────────────────────────────

def discover_pairs(tests_dir, sols_dir):
    """
    Find matching test/solution PDF pairs.
    Expects test files named  mixed_test_XX.pdf
    and solution files named  mixed_test_XX_solutions.pdf
    Returns list of (num_str, test_path, sol_path) sorted by num_str.
    """
    pattern = os.path.join(tests_dir, "mixed_test_*.pdf")
    # Exclude manifest JSONs; only .pdf files
    test_files = sorted(
        p for p in glob.glob(pattern)
        if not p.endswith("_solutions.pdf")
    )

    pairs = []
    for test_path in test_files:
        basename = os.path.basename(test_path)
        # Extract the numeric part, e.g. "01" from "mixed_test_01.pdf"
        m = re.match(r'mixed_test_(\d+)\.pdf$', basename)
        if not m:
            continue
        num_str = m.group(1)
        sol_path = os.path.join(sols_dir, f"mixed_test_{num_str}_solutions.pdf")
        if not os.path.exists(sol_path):
            print(f"  Warning: no matching solution file for {basename} — skipping")
            continue
        pairs.append((num_str, test_path, sol_path))

    return pairs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create Quizzes and seed Questions/Topics from paired test/solution PDFs"
    )
    parser.add_argument("--category-id", required=True, type=int,
                        help="ID of the Category to attach quizzes to")
    parser.add_argument("--tests-dir", default="test_output",
                        help="Folder containing test PDFs (default: test_output)")
    parser.add_argument("--sols-dir", default="sol_output",
                        help="Folder containing solution PDFs (default: sol_output)")
    parser.add_argument("--time-limit", type=int, default=90,
                        help="Quiz time limit in minutes (default: 90)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print extracted data without writing to DB")
    args = parser.parse_args()

    # ── Validate inputs ───────────────────────────────────────────────────────
    for d in (args.tests_dir, args.sols_dir):
        if not os.path.isdir(d):
            print(f"Error: directory not found: {d}")
            sys.exit(1)

    try:
        category = Category.objects.get(id=args.category_id)
    except Category.DoesNotExist:
        print(f"Error: Category with id={args.category_id} does not exist")
        print("Existing categories:")
        for cat in Category.objects.all():
            print(f"  id={cat.id}  {cat}")
        sys.exit(1)

    print(f"Category : {category}")
    print(f"Dry run  : {args.dry_run}\n")

    # ── Discover PDF pairs ────────────────────────────────────────────────────
    pairs = discover_pairs(args.tests_dir, args.sols_dir)
    if not pairs:
        print("No matching PDF pairs found. Check --tests-dir and --sols-dir.")
        sys.exit(1)

    print(f"Found {len(pairs)} PDF pair(s):\n")
    for num_str, test_path, sol_path in pairs:
        print(f"  [{num_str}]  {os.path.basename(test_path)}  +  {os.path.basename(sol_path)}")
    print()

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    total_quizzes   = 0
    total_questions = 0
    total_errors    = []

    # ── Process each pair ─────────────────────────────────────────────────────
    for num_str, test_path, sol_path in pairs:
        title = QUIZ_TITLE_TEMPLATE.format(num=num_str)
        print(f"{'='*60}")
        print(f"Processing: {title}")
        print(f"{'='*60}")

        # Skip if a quiz with this title already exists
        if Quiz.objects.filter(title=title).exists():
            print(f"  Quiz {title!r} already exists — skipping\n")
            continue

        quiz = create_quiz(
            title=title,
            category=category,
            test_pdf_path=test_path,
            sol_pdf_path=sol_path,
            time_limit=args.time_limit,
            dry_run=args.dry_run,
        )
        total_quizzes += 1

        new_q, new_t, errors = seed_questions(
            quiz=quiz,
            test_pdf_path=test_path,
            sol_pdf_path=sol_path,
            client=client,
            dry_run=args.dry_run,
        )
        total_questions += new_q
        if errors:
            total_errors.extend([(title, order, msg) for order, msg in errors])

        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"DONE")
    print(f"  Quizzes   processed : {total_quizzes}")
    print(f"  Questions created   : {total_questions}")

    if total_errors:
        print(f"\nFailed questions ({len(total_errors)}):")
        for quiz_title, order, msg in total_errors:
            print(f"  [{quiz_title}] Q{order:02d}: {msg}")


if __name__ == "__main__":
    main()
