#!/usr/bin/env python
"""
Reads a PDF of math test solutions and uses Gemini to extract topic name +
description from each page, then seeds the ImitationTopic table.

Run from the SazrisiBack2.0/ directory:
    python add_topics_from_pdf.py --pdf path/to/solutions.pdf

Optional flags:
    --dry-run   Print extracted topics without writing to DB
"""

import sys
import os
import argparse
import json

# ── Django setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()
# ─────────────────────────────────────────────────────────────────────────────

from django.conf import settings
from google import genai
import pdfplumber

from imitation_quiz.models.imitation_quiz import ImitationTopic

MODEL = "gemini-2.5-flash"

PROMPT_TEMPLATE = """შემდეგი არის ქართული სამათემატიკო ტესტის ამოხსნის გვერდი.
გამოიტანე:
1. მოკლე მათემატიკური თემის სახელი ქართულად (მაგ.: "პითაგორას თეორემა")
2. მოკლე აღწერა - გამოყენებული კონცეფცია ერთ წინადადებაში ქართულად

ამოხსნა:
{solution_text}

უპასუხე მხოლოდ JSON-ით, სხვა ტექსტის გარეშე:
{{"name": "...", "description": "..."}}"""


def extract_pages(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
    return pages


def extract_topic(client, solution_text):
    prompt = PROMPT_TEMPLATE.format(solution_text=solution_text)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description="Seed ImitationTopic from a PDF of solutions")
    parser.add_argument("--pdf", required=True, help="Path to the solutions PDF")
    parser.add_argument("--dry-run", action="store_true", help="Print topics without writing to DB")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}")
        sys.exit(1)

    print(f"Reading PDF: {args.pdf}")
    pages = extract_pages(args.pdf)
    print(f"Found {len(pages)} pages with text\n")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    created_count = 0
    existed_count = 0
    errors = []

    for i, page_text in enumerate(pages, 1):
        print(f"  Page {i}/{len(pages)} — extracting topic...", end=" ", flush=True)
        try:
            topic = extract_topic(client, page_text)
        except (json.JSONDecodeError, Exception) as e:
            print(f"ERROR: {e}")
            errors.append((i, str(e)))
            continue

        print(f"{topic['name']}")

        if args.dry_run:
            print(f"    desc: {topic['description']}")
            continue

        obj, created = ImitationTopic.objects.get_or_create(
            name=topic["name"],
            defaults={
                "url": "",
                "description": topic["description"],
            },
        )
        if created:
            created_count += 1
        else:
            existed_count += 1

    print()
    if args.dry_run:
        print(f"Dry run complete. {len(pages) - len(errors)} topics extracted, {len(errors)} errors.")
    else:
        print(f"Done. Created: {created_count}, Already existed: {existed_count}, Errors: {len(errors)}")

    if errors:
        print("\nFailed pages:")
        for page_num, err in errors:
            print(f"  Page {page_num}: {err}")


if __name__ == "__main__":
    main()
