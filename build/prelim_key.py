"""Extract the Booklet A answer key from each school's suggested answers.

A misread digit here is the worst failure this project has. There is no partial
credit in Booklet A to soften it: the child is simply told she was wrong when she
was right, against a key she cannot see. So everything below is built to refuse
rather than to guess (CLAUDE.md section 1.6.1), and every key is checked against
the question inventory `index_mcq.py` built from the paper itself -- a key is
accepted only when it covers exactly the questions the booklet actually asks.

The corpus splits cleanly in two, and the split is worth knowing about because the
easy half is much the larger:

* **Twelve schools typed their answers**, so the key is in the PDF's text layer and
  can be read exactly rather than recognised. Two shapes appear. Most print a
  transposed table -- a row of "Q1..Q10" labels and then a row of ten digits --
  which arrives as a run of labels followed by a run of answers. ACS Junior prints
  a three-column grid of (question, answer) pairs, which arrives as alternating
  singletons. Reading a run of labels and then the same number of digits handles
  both without knowing which it is looking at.

* **Nanyang and Red Swastika scanned theirs** as a ruled grid of digits. Red
  Swastika prints "13. ( 2 )" inside one cell, which survives OCR intact once the
  row is joined back together. Nanyang prints the question and its answer in
  adjacent columns as bare digits, and Vision reads it only patchily -- at page
  scale roughly half the answer cells come back, and 2x and 3x return different
  halves. Rather than reconstruct a grid for the sake of one paper, its key is
  read off the scan by a person and committed to review/prelim-mcq-key.json, the
  precedent review/marks.json already sets for an allocation no OCR pass recovers.
  It is never trusted on its own: it must agree with every cell OCR did read, and
  a disagreement fails the extraction rather than quietly winning it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

import corpus
import prelims
from ocr_vision import Line, recognise

REPO = Path(__file__).resolve().parent.parent
WORK_A = REPO / "work-a"
WORK_ANS = REPO / "work-ans"

# The scan host stamps this on every page; it is never part of an answer.
WATERMARK_RE = re.compile(r"www\.sgexam\.com", re.I)
# "Q1", and Methodist Girls' "Q 1" -- the space is in the typed original, not the
# reading of it.
LABEL_RE = re.compile(r"^Q\s*(\d{1,2})$", re.I)
OPTION_RE = re.compile(r"^([1-4])$")
VALID_OPTIONS = {1, 2, 3, 4}


def text_tokens(src: Path) -> list[str]:
    """Every non-empty line of the PDF's text layer, in order."""
    tokens: list[str] = []
    with fitz.open(src) as doc:
        for page in doc:
            for line in WATERMARK_RE.sub("", page.get_text()).splitlines():
                line = line.strip()
                if line:
                    tokens.append(line)
    return tokens


def pair_runs(tokens: list[str], wanted: set[int]) -> tuple[dict[int, int], list[str]]:
    """Pair each run of question labels with the run of answers that follows it.

    Both printed shapes reduce to this. A transposed table gives ten labels then
    ten digits; ACS Junior's paired grid gives one label then one digit. Taking as
    many digits as there were labels, and no more, is what stops the run from
    walking on into the marks or the Booklet B answers below it.

    Blank cells are already gone -- four schools leave two empty columns at the end
    of the last row, which arrive as nothing at all rather than as a placeholder --
    so a label run and its answer run sit next to each other in the stream.
    """
    found: dict[int, int] = {}
    problems: list[str] = []
    index = 0
    while index < len(tokens):
        labels: list[int] = []
        while index < len(tokens):
            match = LABEL_RE.match(tokens[index])
            if not match:
                break
            labels.append(int(match.group(1)))
            index += 1
        if not labels:
            index += 1
            continue

        answers: list[int] = []
        while index < len(tokens) and len(answers) < len(labels):
            match = OPTION_RE.match(tokens[index])
            if not match:
                break
            answers.append(int(match.group(1)))
            index += 1

        # A label run inside the Booklet B answers ("Q29 (a)") has no digit run
        # after it and is simply not a Booklet A row.
        if not answers:
            continue
        if len(answers) != len(labels):
            problems.append(f"Q{labels[0]}-Q{labels[-1]}: {len(labels)} questions "
                            f"but {len(answers)} answers were printed after them")
            continue
        for question, answer in zip(labels, answers):
            if question not in wanted:
                continue
            if question in found and found[question] != answer:
                problems.append(f"Q{question}: read as both {found[question]} "
                                f"and {answer}")
                continue
            found[question] = answer
    return found, problems


# ---------------------------------------------------------------------------
# The scanned keys.

# "1. ( 1 )" -- Red Swastika prints the question number and its answer inside one
# ruled cell, so the pair survives OCR as one string and needs no geometry at all.
INLINE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[.)]\s*[（(]\s*([1-4])\s*[)）]")
# How close two tokens must sit to be read as one cell: their centres within this
# fraction of a glyph height of each other, and no more than this many heights of
# space between them. Deliberately measured on the two tokens themselves rather
# than by first grouping the page into rows. Row grouping drifts -- at 3x Nanyang's
# second and third grid rows merge, which puts question 22 beside question 23's
# answer and yields a confident, wrong "22 -> 3". Those rows are 46px apart and a
# digit is about 40px tall, so no band width separates them reliably; comparing a
# pair directly needs no band at all.
SAME_CELL_DRIFT = 0.5
SAME_CELL_GAP = 4.0
# Nanyang's grid is read at more than one scale because Vision drops different
# cells at each: 2x loses its "12" and 3x loses its "16".
SCALES = (1, 2, 3)


def _adjacent(first: Line, second: Line) -> bool:
    """Whether two recognised strings sit side by side in the same ruled cell."""
    height = min(first.bottom - first.top, second.bottom - second.top) or 1
    return (abs(first.cy - second.cy) <= SAME_CELL_DRIFT * height
            and 0 <= second.left - first.right <= SAME_CELL_GAP * height)


def ocr_evidence(paper: str, wanted: set[int]) -> tuple[dict[int, int], list[str]]:
    """What OCR can establish about a scanned key, conceding what it cannot.

    Two shapes of evidence, and neither is asked to guess:

    * **A number and its answer inside one cell** ("13. ( 2 )"). Unambiguous, so
      it is taken wherever it appears. The cell sometimes arrives as two separate
      strings, which is why rows are joined before matching -- Red Swastika's "3."
      and its "( 3 )" come back separately and the pair is lost otherwise.

    * **A two-digit number with a single digit beside it** in a ruled grid.
      Restricted to two-digit numbers on purpose: in Nanyang's grid the question
      column and the answer column are adjacent and both hold bare digits, so a
      lone "2" beside a lone "3" could be question 2 answered 3 or question 3
      being answered 2. Ten upwards there is no such ambiguity, and below ten
      this returns nothing rather than a coin flip.
    """
    found: dict[int, int] = {}
    conflicts: set[int] = set()
    problems: list[str] = []
    pages = sorted((WORK_ANS / paper / "pages").glob("answer-*.png"))

    def record(question: int, answer: int) -> None:
        if question not in wanted or answer not in VALID_OPTIONS:
            return
        if question in found and found[question] != answer:
            conflicts.add(question)
        found[question] = answer

    for page in pages:
        image = Image.open(page)
        for scale in SCALES:
            if scale == 1:
                target = page
            else:
                scaled = image.resize((image.width * scale, image.height * scale),
                                      Image.LANCZOS)
                target = WORK_ANS / f".key-{scale}x.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                scaled.save(target)
            lines = sorted((l for l in recognise(target)
                            if "sgexam" not in l.text.lower()),
                           key=lambda l: (l.top, l.left))

            for index, line in enumerate(lines):
                # A cell that survived whole: "13. ( 2 )".
                for question, answer in INLINE_RE.findall(line.text):
                    record(int(question), int(answer))

                for other in lines[index + 1:]:
                    if other.top > line.bottom + (line.bottom - line.top):
                        break   # sorted by top: nothing lower down can adjoin
                    if not _adjacent(line, other):
                        continue
                    # A cell the reader split in two: "3." then "( 3 )".
                    for question, answer in INLINE_RE.findall(
                            f"{line.text} {other.text}"):
                        record(int(question), int(answer))
                    head = line.text.strip().lstrip("|").strip()
                    neighbour = other.text.strip()
                    if (head.isdigit() and len(head) == 2
                            and neighbour.isdigit() and len(neighbour) == 1):
                        record(int(head), int(neighbour))

    for question in sorted(conflicts):
        found.pop(question, None)
        problems.append(f"Q{question}: two reads of the scan disagreed; "
                        f"it is not counted as evidence either way")
    return found, problems


VERIFIED_KEY = REPO / "review" / "prelim-mcq-key.json"


def verified_key(paper: str) -> dict[int, int]:
    """A key read off the scan by a person and recorded in the repo.

    Two schools printed their Booklet A key as a picture of a table rather than as
    text, and one of them -- Nanyang -- draws it as a bare grid of digits that
    Vision reads only patchily: at page scale roughly half the answer cells come
    back, and re-reading at 2x and 3x returns different halves.

    Rather than build a grid reconstructor exercised by a single paper, this
    follows the precedent review/marks.json already sets for a mark allocation no
    OCR pass can recover: a person reads it once and it is committed, because
    work-ans/ is regenerated. What keeps it honest is that it is never trusted
    alone -- extract() checks it against every cell OCR did manage to read, and a
    disagreement is a hard failure rather than a silent overwrite.
    """
    if not VERIFIED_KEY.exists():
        return {}
    data = json.loads(VERIFIED_KEY.read_text())
    entry = data.get(paper, {})
    return {int(q): int(a) for q, a in entry.get("answers", {}).items()
            if int(a) in VALID_OPTIONS}


# ---------------------------------------------------------------------------


def booklet_questions(paper: str) -> list[int]:
    path = WORK_A / paper / "questions.json"
    if not path.exists():
        raise FileNotFoundError(f"{paper}: run build/index_mcq.py first ({path})")
    data = json.loads(path.read_text())
    return [q["question"] for q in data["questions"]]


def extract(paper: str, school: str | None = None) -> dict:
    wanted = booklet_questions(paper)
    expected = set(wanted)
    src = prelims.part_path(paper, "Answers")

    found, problems = pair_runs(text_tokens(src), expected)
    source = "pdf text layer"

    if len(found) < len(expected):
        # The typed half is either complete or absent; anything in between means
        # the key was scanned, so start again from the scan rather than mixing a
        # part-read text layer into it.
        found, problems = ocr_evidence(paper, expected)
        source = "scan"

        verified = verified_key(paper)
        if verified:
            disagreed = sorted(q for q, a in found.items()
                               if q in verified and verified[q] != a)
            if disagreed:
                # Refuse. One of the two readings is wrong and there is nothing
                # here that says which, so nothing is marked against either.
                problems.append(
                    f"review/prelim-mcq-key.json disagrees with the scan on "
                    f"{['Q%d' % q for q in disagreed]}: recorded "
                    f"{[verified[q] for q in disagreed]} against "
                    f"{[found[q] for q in disagreed]} read off the page")
                found = {}
            else:
                filled = sorted(set(verified) - set(found))
                found = {**found, **verified}
                source = (f"scan, confirmed by review/prelim-mcq-key.json"
                          + (f" (which supplied {['Q%d' % q for q in filled]})"
                             if filled else ""))

    missing = sorted(expected - set(found))
    invalid = sorted(q for q, a in found.items() if a not in VALID_OPTIONS)
    warnings = list(problems)
    if missing:
        warnings.append(f"no answer found for {missing}")
    if invalid:
        warnings.append(f"answers outside 1-4 for {invalid}")

    return {
        "paper": paper,
        "school": school,
        "source": f"{school or paper} suggested answers",
        "read_from": source,
        "authoritative": False,
        "num_questions": len([q for q in found if q not in invalid]),
        "booklet_questions": len(expected),
        "answers": [{"question": q, "answer": found[q]}
                    for q in sorted(found) if q not in invalid],
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*")
    args = parser.parse_args(argv)

    registry = {p["paper"]: p for p in prelims.load_registry()}
    papers = args.papers or sorted(registry, key=corpus.sort_key)
    exit_code = 0
    for paper in papers:
        result = extract(paper, (registry.get(paper) or {}).get("school"))
        out = WORK_ANS / paper / "mcq-answers.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2))
        print(f"{result['school'] or paper:16s} "
              f"{result['num_questions']:2d}/{result['booklet_questions']:2d} "
              f"answers  [{result['read_from']}]")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
