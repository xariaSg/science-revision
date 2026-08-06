"""Extract Booklet B answers into model answer and explanation, keyed to sub-part.

Replaces the tesseract draft in segment_answers.py for the answer pages. That pass
worked from word boxes and fought the scan the whole way: it merged lines across the
column gutter, read the dotted rule as tokens, and clipped the underlined
"Explanation:" heading to "ion:" -- which mattered most of all, because the heading
is the boundary between the two fields (CLAUDE.md section 1.5). The model answer
drives marking; the explanation drives teaching and is revealed after the mark.

Vision returns whole lines, correctly ordered and cleanly split by column, so the
markers can be parsed from line text instead of reconstructed from word geometry.

Answer pages are two columns, left read fully before right, and Booklet B's answers
begin partway down a column under a "Booklet B" header -- the left half of that same
page is still finishing Booklet A's MCQ answers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ocr_vision import Line, page_lines

REPO = Path(__file__).resolve().parent.parent
WORK_ANSWERS = REPO / "work-ans"

# "29. (a) Roots absorb water..." — number, optional part, optional roman, body.
MARKER_RE = re.compile(
    r"^\s*(?:(?P<question>\d{1,2})\s*[.,])?\s*"
    r"(?:\((?P<part>[a-h])\)\s*)?"
    r"(?:\((?P<roman>i{1,3}|iv|v)\)\s*)?"
    r"(?P<body>.*)$", re.I)
EXPLANATION_RE = re.compile(r"^\s*Explanation\s*:\s*(?P<rest>.*)$", re.I)
BOOKLET_RE = re.compile(r"^\s*Booklet\s+(?P<label>[AB])\b", re.I)
FURNITURE_RE = re.compile(
    r"PSLE\s+Yearly\s+Science|Educational\s+Publishing\s+House|^\s*\d{1,2}\s*$", re.I)
ROMANS = {"i", "ii", "iii", "iv", "v"}


@dataclass
class Answer:
    question: int
    part: str | None
    model_answer: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "part": self.part,
            "model_answer": " ".join(self.model_answer).strip(),
            "explanation": " ".join(self.explanation).strip(),
        }


def split_columns(lines: list[Line], width: int) -> list[Line]:
    """Return lines in reading order: left column fully, then right."""
    # With clean line boxes the gutter is the widest gap between a left-column right
    # edge and a right-column left edge, around the middle of the page.
    centre = width / 2
    candidates = [l.left for l in lines if l.left > centre * 0.75]
    gutter = min(candidates, default=int(centre)) - 20 if candidates else int(centre)
    gutter = max(int(width * 0.35), min(int(width * 0.65), gutter))
    left = sorted([l for l in lines if l.cx < gutter], key=lambda l: l.top)
    right = sorted([l for l in lines if l.cx >= gutter], key=lambda l: l.top)
    return left + right


def extract(work: Path) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    answers: dict[tuple[int, str | None], Answer] = {}
    order: list[tuple[int, str | None]] = []
    booklet: str | None = None
    question: int | None = None
    part: str | None = None
    roman: str | None = None
    in_explanation = False
    warnings: list[str] = []

    for page in range(1, manifest["num_pages"] + 1):
        image = work / "pages" / f"page-{page:03d}.png"
        lines = page_lines(image)
        width = manifest["pages"][page - 1]["width"]

        for line in split_columns(lines, width):
            text = line.text.strip()
            if not text or FURNITURE_RE.search(text):
                continue

            header = BOOKLET_RE.match(text)
            if header:
                booklet = header.group("label").upper()
                question = part = roman = None
                in_explanation = False
                continue

            explanation = EXPLANATION_RE.match(text)
            if explanation:
                in_explanation = True
                text = explanation.group("rest").strip()
                if not text:
                    continue

            marker = MARKER_RE.match(text)
            body = marker.group("body").strip() if marker else text
            if marker and marker.group("question"):
                question = int(marker.group("question"))
                part = roman = None
                in_explanation = False
            if marker and marker.group("part"):
                part = marker.group("part").lower()
                roman = None
                in_explanation = False
            if marker and marker.group("roman"):
                roman = marker.group("roman").lower()
                in_explanation = False

            if booklet != "B" or question is None:
                continue

            label = f"{part}({roman})" if part and roman else (roman or part)
            key = (question, label)
            if key not in answers:
                answers[key] = Answer(question, label)
                order.append(key)
            if body:
                target = (answers[key].explanation if in_explanation
                          else answers[key].model_answer)
                target.append(body)

    grouped: dict[int, list[Answer]] = {}
    for key in order:
        grouped.setdefault(key[0], []).append(answers[key])

    numbers = sorted(grouped)
    if not numbers:
        warnings.append("no Booklet B answers found")
    else:
        gaps = [n for n in range(numbers[0], numbers[-1] + 1) if n not in grouped]
        if gaps:
            warnings.append(f"no answer extracted for question(s) {gaps}")
    for number, entries in grouped.items():
        empty = [e.part for e in entries if not e.model_answer]
        if empty:
            warnings.append(f"Q{number}: empty model answer for part(s) {empty}")

    return {
        "year": manifest["year"],
        "source": "EPH suggested answer",
        "authoritative": False,
        "ocr": "macos-vision",
        "questions": [{"question": n,
                       "parts": [e.as_dict() for e in grouped[n]]} for n in numbers],
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_ANSWERS)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = extract(work)
        (work / "answers.json").write_text(json.dumps(result, indent=2))
        parts = sum(len(q["parts"]) for q in result["questions"])
        withexp = sum(1 for q in result["questions"] for p in q["parts"]
                      if p["explanation"])
        numbers = [q["question"] for q in result["questions"]]
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{year}: {len(numbers)} questions ({span}), {parts} parts, "
              f"{withexp} with an explanation block")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
