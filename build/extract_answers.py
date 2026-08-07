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
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ocr_vision import Line, page_lines

REPO = Path(__file__).resolve().parent.parent
WORK_ANSWERS = REPO / "work-ans"
# The Booklet B question inventory, used only to bound the question numbers this
# paper can legitimately contain.
WORK_QUESTIONS = REPO / "work-b"

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

# These archives are multi-year compilations (CLAUDE.md section 1.5), and a paper's
# own answers are followed by the *previous* year's. 2023 runs out on page 6, whose
# right column opens "2022 / Booklet A / 1. (2)"; without a stop the 2022 answers and
# then a rotated "Allocation of questions by topic" grid — whose row labels OCR as
# "Booklet A" and "Booklet B" — get read as more of 2023.
YEAR_RE = re.compile(r"^\s*(?P<year>20[0-2]\d)\s*$")

# The marker glyph at the head of a question sometimes OCRs as stray punctuation:
# 2023 Q38 comes back as "÷38. (a) When switch S was closed...". Left in place the
# number never matches, the question is silently absorbed by Q37, and a whole
# question disappears from the paper.
LEADING_NOISE_RE = re.compile(r"^[^\w(]+")

# The closing bracket of a roman sub-part is sometimes read as another glyph --
# 2022 Q31(a)(ii) comes back as "i* The number of bacteria". Trusted only while a
# roman sequence is already open (see below), so an answer that merely begins with
# "i" or "v" cannot be mistaken for a label.
ROMAN_FALLBACK_RE = re.compile(
    r"^\(?\s*(?P<roman>i{1,3}|iv|v)\s*[)\].*·:;,]\s*(?P<body>.*)$", re.I)

# What is left of a label that was damaged rather than dropped: 2022 Q31(a)(ii)
# opens "i* The number of bacteria". Once the split has been made geometrically the
# debris is no longer needed and would otherwise be read aloud as answer text.
LABEL_DEBRIS_RE = re.compile(r"^\(?\s*(?:[a-h]|i{1,3}|iv|v)\s*[)\].*·:;,]\s*", re.I)


@dataclass
class Chunk:
    """One line of answer text, kept with the box it came from.

    The geometry is retained past parsing because recovering a sub-part label that
    OCR dropped depends on where the line sits, not on what it says.
    """
    line: Line
    text: str
    is_explanation: bool


@dataclass
class Answer:
    question: int
    part: str | None
    chunks: list[Chunk] = field(default_factory=list)
    repaired: bool = False

    @property
    def model_answer(self) -> list[str]:
        return [c.text for c in self.chunks if not c.is_explanation]

    @property
    def explanation(self) -> list[str]:
        return [c.text for c in self.chunks if c.is_explanation]

    def as_dict(self) -> dict:
        entry = {
            "part": self.part,
            "model_answer": " ".join(self.model_answer).strip(),
            "explanation": " ".join(self.explanation).strip(),
        }
        if self.repaired:
            # Surfaced so review starts with the entries least likely to be right.
            entry["label_recovered"] = True
        return entry


def drop_artefacts(lines: list[Line]) -> list[Line]:
    """Remove scan noise that Vision returns as an oversized, unsure box.

    Deliberately narrow. A plain confidence floor cannot be used: most of the
    low-confidence lines in this corpus are real sub-part labels -- "(b)", "(c)",
    "(b) (i)" -- and dropping one silently merges its answer into the previous
    sub-part, the worst failure this pipeline has (CLAUDE.md section 1.5).

    Requiring the box to also be far taller than a line of text targets rotated
    marginalia and bleed-through instead. Across all 14 papers this catches six
    lines, every one of them junk ("woul", "Guet tor", a run of Cyrillic), and no
    marker.
    """
    if not lines:
        return []
    median_height = statistics.median([l.bottom - l.top for l in lines]) or 1
    return [l for l in lines
            if not (l.confidence < 0.5 and (l.bottom - l.top) > 2 * median_height)]


def merge_rows(lines: list[Line]) -> list[Line]:
    """Join boxes sharing a visual row into one line, read left to right.

    Vision splits a row wherever the horizontal gap is wide, so a question marker
    and its answer come back separately: 2023 has "37. (a)" at y=1773 and "30°C" at
    y=1774. Ordering on `top` alone can then place an answer above its own marker,
    and it is attached to the previous question instead — which is how 2022 Q35(a)
    lost "400 g" and ended up with an empty model answer.

    Rows are grouped by vertical overlap rather than a pixel threshold, because line
    height varies with the scan (CLAUDE.md section 1.1).
    """
    if not lines:
        return []
    ordered = sorted(lines, key=lambda l: (l.top, l.left))
    rows: list[list[Line]] = [[ordered[0]]]
    for line in ordered[1:]:
        row = rows[-1]
        height = min(line.bottom - line.top, row[-1].bottom - row[-1].top)
        # Same row when the centres sit within half a line height of each other.
        if abs(line.cy - row[-1].cy) <= max(height, 1) * 0.5:
            row.append(line)
        else:
            rows.append([line])

    merged: list[Line] = []
    for row in rows:
        row.sort(key=lambda l: l.left)
        if len(row) == 1:
            merged.append(row[0])
            continue
        merged.append(Line(
            text=" ".join(l.text for l in row),
            left=min(l.left for l in row), top=min(l.top for l in row),
            right=max(l.right for l in row), bottom=max(l.bottom for l in row),
            confidence=min(l.confidence for l in row)))
    return merged


def split_columns(lines: list[Line], width: int) -> list[Line]:
    """Return lines in reading order: left column fully, then right."""
    # With clean line boxes the gutter is the widest gap between a left-column right
    # edge and a right-column left edge, around the middle of the page.
    centre = width / 2
    candidates = [l.left for l in lines if l.left > centre * 0.75]
    gutter = min(candidates, default=int(centre)) - 20 if candidates else int(centre)
    gutter = max(int(width * 0.35), min(int(width * 0.65), gutter))
    # Rows are merged per column: a marker in the left column and body text in the
    # right sit at the same height but are unrelated, and joining them across the
    # gutter is the exact failure the tesseract pass had (CLAUDE.md section 1.5).
    left = merge_rows([l for l in lines if l.cx < gutter])
    right = merge_rows([l for l in lines if l.cx >= gutter])
    return sorted(left, key=lambda l: l.top) + sorted(right, key=lambda l: l.top)


def expected_range(year: int, questions_root: Path = WORK_QUESTIONS) -> tuple[int, int] | None:
    """The Booklet B question numbers this paper should contain.

    Read from the question inventory rather than assumed to be Q29-Q40, because
    Booklet B numbering continues from Booklet A and is not guaranteed to be the
    same span every year (CLAUDE.md section 1.4).
    """
    path = questions_root / str(year) / "questions.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    stated = data.get("expected_questions")
    if isinstance(stated, list) and len(stated) == 2:
        return int(stated[0]), int(stated[1])
    numbers = [q["question"] for q in data.get("questions", [])]
    return (min(numbers), max(numbers)) if numbers else None


def booklet_parts(year: int, questions_root: Path = WORK_QUESTIONS) -> dict[int, list[str]]:
    """Sub-part labels the paper itself was indexed with, per question."""
    path = questions_root / str(year) / "questions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {q["question"]: [p["part"] for p in q["parts"]
                            if not p.get("is_parent") and p.get("part")]
            for q in data.get("questions", [])}


def satisfied_by(label: str, found: set[str | None]) -> bool:
    """Whether an indexed sub-part label is covered by an extracted one.

    The inventory sometimes stops at "b" where the answers correctly nest "b(i)"
    and "b(ii)" — the answer pages label sub-parts more precisely than the question
    scan does. A bare label is therefore satisfied by any nested form of itself,
    otherwise every such question would raise a false alarm.
    """
    return label in found or any(
        isinstance(f, str) and f.startswith(f"{label}(") for f in found)


def recover_label(answer: Answer, label: str) -> Answer | None:
    """Split a sub-part whose label OCR never emitted, using indentation alone.

    When Vision drops a "(b)" glyph the rest of that line is still read, so the
    answer to (b) is appended to (a) and the merge is invisible in the text. What
    survives is geometry: the box still starts where the label was, so the line is
    outdented from the body lines around it. That outdent is the split point.

    Deliberately refuses whenever the evidence is not clean -- no candidate, or
    more than one -- because a wrong split hands the child one sub-part's answer
    labelled as another's. A refusal leaves the warning standing for a human.
    """
    body = [c for c in answer.chunks if not c.is_explanation]
    if len(body) < 2:
        return None
    # The body indent is what the sub-part's own continuation lines sit at.
    indent = statistics.median([c.line.left for c in body])
    step = max(indent * 0.05, 20)
    candidates = [i for i, c in enumerate(body)
                  if i > 0 and c.line.left < indent - step]
    if len(candidates) != 1:
        return None

    cut = candidates[0]
    index = answer.chunks.index(body[cut])
    moved, answer.chunks = answer.chunks[index:], answer.chunks[:index]
    head = LABEL_DEBRIS_RE.sub("", moved[0].text)
    if head:
        moved[0] = Chunk(moved[0].line, head, moved[0].is_explanation)
    return Answer(answer.question, label, moved, repaired=True)


def extract(work: Path, questions_root: Path = WORK_QUESTIONS) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    year = manifest["year"]
    expected = expected_range(year, questions_root)
    answers: dict[tuple[int, str | None], Answer] = {}
    order: list[tuple[int, str | None]] = []
    booklet: str | None = None
    question: int | None = None
    part: str | None = None
    roman: str | None = None
    in_explanation = False
    warnings: list[str] = []
    rejected: list[int] = []
    stopped_at: str | None = None

    for page in range(1, manifest["num_pages"] + 1):
        if stopped_at:
            break
        image = work / "pages" / f"page-{page:03d}.png"
        lines = drop_artefacts(page_lines(image))
        width = manifest["pages"][page - 1]["width"]

        for line in split_columns(lines, width):
            text = line.text.strip()
            if not text or FURNITURE_RE.search(text):
                continue

            # A bare year heads the next paper in the compilation. Once this
            # paper's Booklet B has been read, that is the end of it.
            foreign = YEAR_RE.match(text)
            if foreign and int(foreign.group("year")) != year and answers:
                stopped_at = f"page {page} ({foreign.group('year')} answers begin)"
                break

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

            text = LEADING_NOISE_RE.sub("", text)
            marker = MARKER_RE.match(text)
            body = marker.group("body").strip() if marker else text
            if marker and marker.group("question"):
                number = int(marker.group("question"))
                # A number outside the paper's own range is misread furniture, not
                # a question: 2021 yields a "Q83" whose sub-parts are really Q40's.
                # Dropping the number alone keeps the body and its (b)/(c)/(d)
                # labels flowing into the question actually being answered.
                if expected and not expected[0] <= number <= expected[1]:
                    # Only worth reporting once inside Booklet B. Before that the
                    # rejects are just Booklet A's own numbering, which is skipped
                    # anyway and would bury the real signal under "1..28".
                    if booklet == "B":
                        rejected.append(number)
                else:
                    question = number
                    part = roman = None
                    in_explanation = False
            if marker and marker.group("part"):
                part = marker.group("part").lower()
                roman = None
                in_explanation = False
            if marker and marker.group("roman"):
                roman = marker.group("roman").lower()
                in_explanation = False
            elif roman and marker and not marker.group("question") \
                    and not marker.group("part"):
                # Only mid-sequence: "(i)" has already been read, so a line opening
                # with a damaged "(ii)" is a label rather than prose.
                fallback = ROMAN_FALLBACK_RE.match(text)
                if fallback and fallback.group("roman").lower() != roman:
                    roman = fallback.group("roman").lower()
                    body = fallback.group("body").strip()
                    in_explanation = False

            if booklet != "B" or question is None:
                continue

            label = f"{part}({roman})" if part and roman else (roman or part)
            key = (question, label)
            if key not in answers:
                answers[key] = Answer(question, label)
                order.append(key)
            if body:
                answers[key].chunks.append(Chunk(line, body, in_explanation))

    grouped: dict[int, list[Answer]] = {}
    for key in order:
        grouped.setdefault(key[0], []).append(answers[key])

    # A sub-part label that OCR never emitted is the most dangerous failure here:
    # the label vanishes, its answer is appended to the previous sub-part, and the
    # result looks perfectly well-formed (CLAUDE.md section 1.5). Nothing in the
    # text can reveal it, so it is caught by comparing against the sub-parts the
    # paper itself was indexed with.
    repairs: list[str] = []
    for number, paper_parts in booklet_parts(year, questions_root).items():
        if number not in grouped:
            continue
        found = {e.part for e in grouped[number]}
        missing = [p for p in paper_parts if not satisfied_by(p, found)]
        # Repaired one at a time, re-reading `found` each pass, so a question that
        # lost two labels is only fixed if each split is independently clean.
        for label in list(missing):
            position = paper_parts.index(label)
            if position == 0:
                continue
            # Matched leniently: the inventory may say "a" where the answers
            # correctly nest "a(i)", and that is the entry the lost text is in.
            before = paper_parts[position - 1]
            previous = next((e for e in grouped[number]
                             if e.part and (e.part == before
                                            or e.part.startswith(f"{before}("))), None)
            if previous is None:
                continue
            recovered = recover_label(previous, label)
            if recovered is None:
                continue
            grouped[number].insert(grouped[number].index(previous) + 1, recovered)
            missing.remove(label)
            repairs.append(f"Q{number}({label})")
        if missing:
            warnings.append(
                f"Q{number}: the paper has sub-part(s) {missing} but no answer was "
                f"keyed to them — their text is probably absorbed by the part before")

    # Coverage warnings run last so they describe the answers as finally split.
    numbers = sorted(grouped)
    if not numbers:
        warnings.append("no Booklet B answers found")
    else:
        # Checked against the paper's own stated range, not just the span that
        # happened to be read, so a question dropped off either end still shows up.
        low, high = expected or (numbers[0], numbers[-1])
        gaps = [n for n in range(low, high + 1) if n not in grouped]
        if gaps:
            warnings.append(f"no answer extracted for question(s) {gaps}")
    for number in numbers:
        empty = [e.part for e in grouped[number] if not e.model_answer]
        if empty:
            warnings.append(f"Q{number}: empty model answer for part(s) {empty}")

    return {
        "year": year,
        "source": "EPH suggested answer",
        "authoritative": False,
        "ocr": "macos-vision",
        "expected_questions": list(expected) if expected else None,
        "stopped_at": stopped_at,
        "rejected_numbers": sorted(set(rejected)),
        "recovered_labels": repairs,
        "questions": [{"question": n,
                       "parts": [e.as_dict() for e in grouped[n]]} for n in numbers],
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_ANSWERS)
    parser.add_argument("--questions-root", type=Path, default=WORK_QUESTIONS)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = extract(work, args.questions_root)
        (work / "answers.json").write_text(json.dumps(result, indent=2))
        parts = sum(len(q["parts"]) for q in result["questions"])
        withexp = sum(1 for q in result["questions"] for p in q["parts"]
                      if p["explanation"])
        numbers = [q["question"] for q in result["questions"]]
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{year}: {len(numbers)} questions ({span}), {parts} parts, "
              f"{withexp} with an explanation block")
        if result["stopped_at"]:
            print(f"    stopped at {result['stopped_at']}")
        if result["rejected_numbers"]:
            print(f"    ignored out-of-range number(s) {result['rejected_numbers']}")
        if result["recovered_labels"]:
            print(f"    recovered dropped label(s) {result['recovered_labels']}"
                  f" — check these against the scan")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
