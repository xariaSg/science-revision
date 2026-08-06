"""Build the Booklet B question inventory: which questions exist, their sub-parts,
the marks each carries, and which page each is printed on.

This is deliberately *not* segmentation. The app shows the original Booklet B page
and offers one answer box per sub-part, so all that is needed is the inventory that
drives those boxes. No crops, no question text, no figure extraction -- the page
itself carries the diagrams, tables and graphs intact, which is also the better
pedagogy (CLAUDE.md section 2.1).

Booklet B is single-column and indentation encodes role, as on the answer pages:

    32  Diagram 1 shows two types of plants...      <- question number, left margin
        (a) As the population of plant F...   [1]   <- sub-part one indent in
                                              [2]   <- marks right-aligned

The strong constraint here that answer segmentation lacked: question numbers run
consecutively. Requiring each to be the previous one plus one rejects the false
positives a bare-digit pattern otherwise picks up ("56", "12", "11" all appear in
body text at the left margin).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pytesseract
from PIL import Image

from segment_answers import (MARGIN_BOTTOM, MARGIN_TOP, expected_question_range,
                             group_lines, page_words)

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"

# Question numbers sit in the left margin, sub-part labels one indent in. Both are
# well inside this fraction of the page width; body text starts beyond it.
MARKER_ZONE = 0.25
# How many leading tokens may precede a sub-part label ("34 = (a) Name the...").
MARKER_LOOKAHEAD = 3

# The trailing separator is optional: the full papers OCR the number bare ("37"),
# while the Booklet B extracts render it with a stop ("37."). Requiring bare digits
# silently dropped every question in the extracts. The consecutive-number rule below
# is what keeps this loose pattern from matching body text.
QUESTION_RE = re.compile(r"^(\d{1,2})\s*[.,]?$")
SUBPART_RE = re.compile(r"^\(?\s*(i{1,3}|iv|v|[a-h])\s*\)$", re.I)
ROMAN_PARTS = {"i", "ii", "iii", "iv", "v"}
MARKS_RE = re.compile(r"\[\s*(\d)\s*]")
# A mark allocation the main pass could not read. Tesseract mangles these small
# right-margin tokens badly -- 2024 Q29(a)'s "[2]" comes back as "{?]" -- so a token
# that merely looks bracket-shaped is worth a second, narrower look.
# The interior must not be a letter, or this also matches sub-part labels like "(a)".
MARK_CANDIDATE_RE = re.compile(r"^[\[{(<|][^a-z]{0,3}[]})>|]$", re.I)
# Fraction of page width beyond which a token is in the right margin where marks sit.
RIGHT_MARGIN = 0.80
MARK_PAD = 14
MIN_MARKS, MAX_MARKS = 1, 3
# Booklet B states its own total on its first page: "(44 marks)".
TOTAL_MARKS_RE = re.compile(r"\((\d{2})\s+marks\)", re.I)

# Scenario anchors: the labelled entities a question is *about* ("plant E", "tube A").
# The marking gate keys on them (CLAUDE.md section 3.3), and speech-to-text needs them
# too -- unseeded, Whisper renders "plant E" as "Planty" and the anchor is gone.
ANCHOR_RE = re.compile(
    r"\b(plant|animal|bird|fish|insect|tube|beaker|container|substance|block|"
    r"set-?up|zone|bulb|magnet|cylinder|jar|box|ball|spring|liquid|material|"
    r"object|sample|card|strip|wire|circuit|solution|mixture|seed|leaf|organism)"
    r"\s+([A-Z])\b")


def scenario_anchors(text: str) -> list[str]:
    seen: dict[str, str] = {}
    for noun, letter in ANCHOR_RE.findall(re.sub(r"\s+", " ", text)):
        anchor = f"{noun.lower()} {letter}"
        seen.setdefault(anchor.lower(), anchor)
    return sorted(seen.values())


def reread_mark(img, word) -> int | None:
    """Re-OCR a single mark token with a digit whitelist.

    Read in isolation and told to expect only "[0-9]", tesseract gets these right
    where it fails on them as part of a full page.
    """
    box = (max(0, word.left - MARK_PAD), max(0, word.top - MARK_PAD),
           min(img.width, word.right + MARK_PAD),
           min(img.height, word.bottom + MARK_PAD))
    text = pytesseract.image_to_string(
        img.crop(box),
        config="--psm 7 -c tessedit_char_whitelist=[]0123456789")
    match = re.search(r"(\d)", text)
    if not match:
        return None
    value = int(match.group(1))
    # Booklet B allocations are 1-3 marks (CLAUDE.md section 3.4). Anything else is
    # the whitelist inventing a digit where the glyph was unreadable -- it returned
    # "7" for 2024 Q29(a), whose real allocation is 2.
    return value if MIN_MARKS <= value <= MAX_MARKS else None


def stated_total_marks(work: Path, bounds: dict) -> int | None:
    booklet_b = bounds["booklet_b"]
    for page in range(booklet_b["start"], min(booklet_b["start"] + 3,
                                              booklet_b["end"] + 1)):
        cached = work / "ocr" / f"page-{page:03d}.txt"
        if not cached.exists():
            continue
        match = TOTAL_MARKS_RE.search(re.sub(r"\s+", " ", cached.read_text()))
        if match:
            return int(match.group(1))
    return None


def choose_question_run(candidates: list[tuple[int, int, int]],
                        expected: tuple[int, int] | None) -> dict[tuple[int, int], int]:
    """Pick the real question numbers from all left-margin number candidates.

    Taking the first candidate and then demanding +1 each time is too fragile: the
    Booklet B cover carries numbered instructions ("1. Please check that your
    name..."), and on 2022 -- whose extract has no "For questions N to M" line to
    anchor on -- that swallowed the sequence and left one question out of twelve.

    Real questions form a long consecutive run; noise (page numbers, axis labels,
    "50 times") does not. So take the longest run, preferring one that starts where
    Booklet B says it should when that is known.
    """
    def longest_from(start_value: int | None) -> list[tuple[int, int, int]]:
        best: list[tuple[int, int, int]] = []
        for i, candidate in enumerate(candidates):
            if start_value is not None and candidate[2] != start_value:
                continue
            run = [candidate]
            for later in candidates[i + 1:]:
                if later[2] == run[-1][2] + 1:
                    run.append(later)
            if len(run) > len(best):
                best = run
        return best

    run = longest_from(expected[0]) if expected else []
    if len(run) < 2:
        # No usable run from the stated start; fall back to the longest anywhere.
        unconstrained = longest_from(None)
        if len(unconstrained) > len(run):
            run = unconstrained
    return {(page, line): number for page, line, number in run}


REVIEW_MARKS = REPO / "review" / "marks.json"


def verified_marks(year: int) -> dict[str, int]:
    """Human-verified mark allocations for a paper, keyed "29a" / "30b(i)".

    Some allocations are simply not readable: 2024 Q29(a) is printed as a damaged
    glyph in the scan, so no OCR pass recovers it. A person reads it off the paper
    once and it is recorded here, in the repo, because work/ is regenerated.
    """
    if not REVIEW_MARKS.exists():
        return {}
    data = json.loads(REVIEW_MARKS.read_text())
    return {k: v for k, v in data.get(str(year), {}).items() if isinstance(v, int)}


def index_paper(work: Path) -> dict:
    bounds = json.loads((work / "boundaries.json").read_text())
    booklet_b = bounds["booklet_b"]
    expected = expected_question_range(work, bounds)
    verified = verified_marks(bounds["year"])

    questions: dict[int, dict] = {}
    warnings: list[str] = []
    current_q: int | None = None
    current_part: str | None = None
    current_sub: str | None = None

    # Pass 1: read every page once, and collect left-margin number candidates.
    pages: dict[int, tuple[list[list], int]] = {}
    candidates: list[tuple[int, int, int]] = []
    for page in range(booklet_b["start"], booklet_b["end"] + 1):
        words, width, height = page_words(work, page)
        words = [w for w in words
                 if MARGIN_TOP * height <= w.cy <= MARGIN_BOTTOM * height]
        if not words:
            continue
        lines = group_lines(words)
        pages[page] = (lines, width)
        for index, line in enumerate(lines):
            head = line[0]
            if head.left > width * MARKER_ZONE:
                continue
            match = QUESTION_RE.match(head.text)
            if match:
                candidates.append((page, index, int(match.group(1))))

    accepted = choose_question_run(candidates, expected)

    repairs: list[str] = []
    for page, (lines, width) in pages.items():
        marker_limit = width * MARKER_ZONE
        page_image = None

        for index, line in enumerate(lines):
            text = " ".join(w.text for w in line)
            consumed = 0

            head = line[0]
            number = accepted.get((page, index))
            if number is not None:
                current_q = number
                current_part = current_sub = None
                questions[number] = {"question": number, "pages": [page],
                                     "parts": []}
                consumed = 1

            if current_q is None:
                continue
            entry = questions[current_q]
            if page not in entry["pages"]:
                entry["pages"].append(page)

            for token in line[consumed:consumed + MARKER_LOOKAHEAD]:
                if token.left > marker_limit:
                    break
                match = SUBPART_RE.match(token.text)
                if not match:
                    continue
                label = match.group(1).lower()
                if label in ROMAN_PARTS:
                    current_sub = label
                else:
                    current_part = label
                    current_sub = None
                part = (f"{current_part}({current_sub})" if current_sub and current_part
                        else current_sub or current_part)
                if not any(p["part"] == part for p in entry["parts"]):
                    entry["parts"].append({"part": part, "marks": None,
                                           "page": page, "marks_source": None})
                break

            values = [int(v) for v in MARKS_RE.findall(text)
                      if MIN_MARKS <= int(v) <= MAX_MARKS]
            repaired = False
            if not values:
                # Nothing parsed cleanly; retry any bracket-shaped token sitting in
                # the right margin, on its own and with a digit whitelist.
                tail = line[-1]
                if (tail.left > width * RIGHT_MARGIN
                        and MARK_CANDIDATE_RE.match(tail.text)):
                    if page_image is None:
                        page_image = Image.open(
                            work / "pages" / f"page-{page:03d}.png")
                    recovered = reread_mark(page_image, tail)
                    if recovered is not None:
                        values = [recovered]
                        repaired = True
                        repairs.append(f"Q{current_q}: read [{recovered}] from "
                                       f"{tail.text!r} on p{page}")

            for value in values:
                if not entry["parts"]:
                    # Marks before any sub-part label: a question with no parts.
                    entry["parts"].append({"part": None, "marks": None, "page": page,
                                           "marks_source": None})
                target = entry["parts"][-1]
                if target["marks"] is None:
                    target["marks"] = value
                    target["marks_source"] = "repair" if repaired else "ocr"
                else:
                    warnings.append(
                        f"Q{current_q}({target['part']}): a second mark allocation "
                        f"[{value}] found; keeping [{target['marks']}]")

    # A verified reading always wins over anything OCR produced or inferred.
    applied: list[str] = []
    for entry in questions.values():
        for part in entry["parts"]:
            key = f"{entry['question']}{part['part'] or ''}"
            if key in verified and part["marks"] != verified[key]:
                part["marks"] = verified[key]
                part["marks_source"] = "verified"
                part.pop("is_parent", None)
                applied.append(key)
    if applied:
        repairs.append(f"applied verified marks for {', '.join(sorted(applied))}")

    numbers = sorted(questions)
    if expected:
        missing = [n for n in range(expected[0], expected[1] + 1) if n not in questions]
        if missing:
            warnings.append(f"Booklet B covers Q{expected[0]}-Q{expected[1]} but no "
                            f"question found for {missing}")
    for number in numbers:
        entry = questions[number]
        if not entry["parts"]:
            warnings.append(f"Q{number}: no sub-parts found")
        labels = [p["part"] for p in entry["parts"] if p["part"]]
        for part in entry["parts"]:
            if part["marks"] is not None:
                continue
            # A parent of nested sub-parts carries no marks itself: 29(b) is just the
            # heading over 29(b)(i) and 29(b)(ii), which hold the allocations.
            if part["part"] and any(l.startswith(f"{part['part']}(") for l in labels):
                part["is_parent"] = True
                continue
            warnings.append(f"Q{number}({part['part']}): no mark allocation found")

    for entry in questions.values():
        entry["total_marks"] = sum(p["marks"] or 0 for p in entry["parts"])
        pages_text = " ".join(
            (work / "ocr" / f"page-{page:03d}.txt").read_text()
            for page in entry["pages"]
            if (work / "ocr" / f"page-{page:03d}.txt").exists())
        entry["scenario_anchors"] = scenario_anchors(pages_text)

    counted = sum(q["total_marks"] for q in questions.values())
    stated = stated_total_marks(work, bounds)
    if stated is not None and counted != stated:
        shortfall = stated - counted
        unknown = [(q, p) for q in questions.values() for p in q["parts"]
                   if p["marks"] is None and not p.get("is_parent")]
        # With a single unread allocation the stated total determines it outright.
        # With several it does not, so leave them for review rather than guessing.
        if len(unknown) == 1 and MIN_MARKS <= shortfall <= MAX_MARKS:
            entry, part = unknown[0]
            part["marks"] = shortfall
            part["marks_source"] = "inferred_from_total"
            entry["total_marks"] += shortfall
            counted += shortfall
            warnings = [w for w in warnings
                        if not w.startswith(f"Q{entry['question']}({part['part']}):")]
            repairs.append(f"Q{entry['question']}({part['part']}): inferred [{shortfall}] "
                           f"as the only allocation missing from the stated {stated}")
        else:
            warnings.append(f"marks add up to {counted} but Booklet B states {stated}; "
                            f"{shortfall} unaccounted for across "
                            f"{len(unknown)} unread allocation(s)")

    return {
        "year": bounds["year"],
        "booklet_b": {"start": booklet_b["start"], "end": booklet_b["end"]},
        "expected_questions": list(expected) if expected else None,
        "stated_total_marks": stated,
        "counted_marks": counted,
        "questions": [questions[n] for n in numbers],
        "mark_repairs": repairs,
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def cross_check_answers(work: Path, result: dict) -> list[str]:
    """Compare the question inventory against the segmented answers.

    Two independent reads of the same structure -- one from Booklet B, one from the
    answer pages -- so a disagreement means at least one is wrong.
    """
    path = work / "answers" / "segments.json"
    if not path.exists():
        return ["no segmented answers to cross-check against"]
    answers = json.loads(path.read_text())
    by_number = {q["question"]: q for q in answers["questions"]}

    notes: list[str] = []
    for entry in result["questions"]:
        answer = by_number.get(entry["question"])
        if answer is None:
            notes.append(f"Q{entry['question']}: no segmented answer")
            continue
        asked = [p["part"] for p in entry["parts"] if p["part"]]
        answered = [p["part"] for p in answer["parts"] if p["part"]]
        if asked and answered and set(asked) != set(answered):
            notes.append(f"Q{entry['question']}: parts {asked} in Booklet B but "
                         f"{answered} in the answers")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_DIR)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = index_paper(work)
        result["answer_cross_check"] = cross_check_answers(work, result)
        (work / "questions.json").write_text(json.dumps(result, indent=2))

        total = sum(q["total_marks"] for q in result["questions"])
        print(f"{year}: {len(result['questions'])} questions, "
              f"{sum(len(q['parts']) for q in result['questions'])} parts, "
              f"{total} marks")
        for entry in result["questions"]:
            parts = ", ".join(f"{p['part'] or '-'}[{p['marks'] or '?'}]"
                              for p in entry["parts"])
            pages = "-".join(str(p) for p in (entry["pages"][:1] + entry["pages"][-1:]))
            print(f"    Q{entry['question']:<3} p{pages:<6} {parts}")
        for warning in result["warnings"] + result["answer_cross_check"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
