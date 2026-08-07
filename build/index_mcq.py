"""Build the Booklet A question inventory: which MCQs exist and their page.

The same shape as index_questions.py does for Booklet B, and for the same reason --
the app shows the original page and the student answers beside it, so nothing needs
to be transcribed or cropped (CLAUDE.md section 2.1). Booklet A needs less: every
question is worth the same, there are no sub-parts, and the whole rubric is one
digit. What it needs instead is certainty about *which* question a page is showing,
because an off-by-one against the answer key marks a whole paper wrong.

Three things make that certain, and all three are read off the paper:

    For each question from 1 to 28, four options are given.   <- the range, stated
                                                (56 marks)   <- the total, stated
    1  Which is a characteristic of all living things?        <- number, left margin
        (1) They can reproduce.                               <- options, indented

The range statement is the anchor. It sits on the first question page, so it also
separates real questions from the numbered instructions on the cover -- "1. Write
your Index No..." is a left-margin number too, and without the anchor it competes
with Q1 for the start of the run.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ocr_vision import Line, page_lines
from extract_answers import drop_artefacts, merge_rows
from segment_answers import page_words

REPO = Path(__file__).resolve().parent.parent
WORK_A = REPO / "work-a"

# "For each question from 1 to 28, four options are given." — the paper stating its
# own range. Present on both eras in this corpus, worded identically.
RANGE_RE = re.compile(r"for\s+each\s+question\s*s?\s+from\s+(?P<first>\d{1,2})"
                      r"\s+to\s+(?P<last>\d{1,3})", re.I)
TOTAL_MARKS_RE = re.compile(r"\((?P<marks>\d{2,3})\s+marks\)", re.I)
# A question number opening a line: bare, or with a stop the scan may have added.
QUESTION_RE = re.compile(r"^(?P<question>\d{1,3})\s*[.)]?(?:\s+(?P<rest>\S.*))?$")
# The same as a standalone token, which is how tesseract returns it.
NUMBER_RE = re.compile(r"^(?P<question>\d{1,3})\s*[.)]?$")
OPTION_RE = re.compile(r"[(\[]\s*([1-4])\s*[)\]]")
# Page furniture. It sits between the last option of one question and the first row
# of the next, so it has to be stepped over when a question start is inferred from
# the option block above it.
FURNITURE_RE = re.compile(r"^\s*(?:\d{1,3}|BLANK\s+PAGE)\s*$|Go\s+on\s+to|"
                          r"\d{4}/0?2\s*\(?A\)?|Singapore\s+Examinations|©", re.I)
# Fraction of page width within which a question number sits. Options are indented
# past this on every paper here, so the zone also keeps "(1) ..." out of the run.
MARKER_ZONE = 0.22
# How far apart a number and the row it belongs to may sit vertically, as a
# fraction of page height. The two readers box the same row slightly differently.
ROW_TOLERANCE = 0.012
# How far a positionally recovered number may sit from where this paper puts its
# question numbers, in page-width fractions. Calibrated per paper, not assumed.
MARKER_DRIFT = 0.05
# PSLE Booklet A has run 28 or 30 questions across this corpus. Used only to sanity
# check what was read, never to supply it.
MIN_QUESTIONS, MAX_QUESTIONS = 15, 45


def longest_increasing_run(values: list[int]) -> set[int]:
    """Indices of the longest strictly increasing subsequence of `values`.

    Question numbers count upwards in reading order and the things that look like
    them -- page numbers, quantities, "20 cm" -- do not. Increasing rather than
    consecutive because OCR drops the occasional number, and demanding +1 each time
    throws away every question after the first dropout (CLAUDE.md section 1.5.1).
    """
    if not values:
        return set()
    # O(n^2) is ample: a paper yields a few dozen candidates.
    length = [1] * len(values)
    previous = [-1] * len(values)
    for i, value in enumerate(values):
        for j in range(i):
            if values[j] < value and length[j] + 1 > length[i]:
                length[i], previous[i] = length[j] + 1, j
    index = max(range(len(values)), key=lambda i: length[i])
    chosen: set[int] = set()
    while index != -1:
        chosen.add(index)
        index = previous[index]
    return chosen


def page_rows(work: Path, page: int) -> list[Line]:
    """One line per visual row, in reading order. Booklet A is single-column."""
    image = work / "pages" / f"page-{page:03d}.png"
    if not image.exists():
        return []
    rows = merge_rows(drop_artefacts(page_lines(image)))
    return sorted(rows, key=lambda line: (line.top, line.left))


def _row_at(rows: list[tuple[int, Line]], page: int, top: int,
            tolerance: int) -> int | None:
    """The row index a loose number belongs to: the nearest on the same page."""
    best, distance = None, tolerance
    for index, (row_page, line) in enumerate(rows):
        if row_page != page:
            continue
        gap = abs(line.top - top)
        if gap <= distance:
            best, distance = index, gap
    return best


def _after_option_block(rows: list[tuple[int, Line]], before: int,
                        after: int) -> int | None:
    """The row following the first complete run of options (1)-(4) in a band.

    Every Booklet A question offers exactly four options, so the row after the
    fourth ends one question and begins the next. Taking the *first* complete run
    matters: the missing question has options of its own further down the band, and
    on 2024 they are labels on a diagram, so a later "(4)" is not the boundary.

    Returns None unless a full run is found inside the band, which is what a
    question whose options are pictures rather than text will do.
    """
    seen: set[int] = set()
    for index in range(before + 1, after):
        seen.update(int(value) for value in OPTION_RE.findall(rows[index][1].text))
        if seen < {1, 2, 3, 4}:
            continue
        # A question that ends at the foot of a page has the footer and the next
        # page's number between its last option and the question following it.
        start = index + 1
        while start < after and FURNITURE_RE.search(rows[start][1].text.strip()):
            start += 1
        if start >= after:
            return None
        if rows[start][0] != rows[index][0]:
            # The next question is overleaf, so it owns that page from the top. Its
            # own first row is not always readable -- 2015 Q12 and 2021 Q27 are
            # near-solid diagrams whose stem Vision never returns -- and anchoring
            # on the first thing it *did* read would leave the page looking as
            # though it belonged to the question before.
            page = rows[start][0]
            while start > index and rows[start - 1][0] == page:
                start -= 1
        return start
    return None


def _recover_positions(rows: list[tuple[int, Line]], manifest: dict,
                       chosen: list[tuple[int, int, int]],
                       loose: list[tuple[int, int, int, int]],
                       expected: tuple[int, int],
                       margins: list[int]) -> tuple[list[tuple[int, int, int]], list[str]]:
    """Place the questions neither reader could name, from position alone.

    This is where Booklet A is easier than anything in Booklet B: the paper states
    its own range, and the numbering is dense, so a missing question's *number* is
    never in doubt -- only where on the page it starts. So nothing here tries to
    read a digit. It looks for a left-margin number, of any value, sitting in the
    stretch between the two questions either side of the gap, at the indent this
    paper puts its question numbers at.

    2025 Q19 is the case it exists for: tesseract reads the marker as "49", which
    no amount of digit-fixing turns into 19, but its position between Q18 and Q20
    settles the matter regardless.

    When even that is missing -- 2017 and 2024 both lose a "4" so completely that
    the question's first row starts at the body indent, with nothing to its left --
    the layout still says where the question begins: every MCQ carries options (1)
    to (4), so the row after the previous question's fourth option is the next
    question's first.

    Both tiers refuse whenever the band is ambiguous, so an unclear stretch is left
    as a gap for a human rather than guessed at.
    """
    if not chosen:
        return chosen, []
    width = manifest["pages"][0]["width"]
    typical = sorted(margins)[len(margins) // 2]
    drift = width * MARKER_DRIFT
    placed = {number: index for index, _, number in chosen}

    def gap_runs() -> list[list[int]]:
        """Missing numbers grouped into consecutive stretches."""
        runs: list[list[int]] = []
        for number in range(expected[0], expected[1] + 1):
            if number in placed:
                continue
            if runs and runs[-1][-1] == number - 1:
                runs[-1].append(number)
            else:
                runs.append([number])
        return runs

    def by_position(number: int, before: int, after: int) -> int | None:
        """A left-margin number of any value, alone in the band."""
        found = set()
        for page, top, left, _ in loose:
            if abs(left - typical) > drift:
                continue
            # Matched by row rather than by raw y, so the previous question's own
            # marker -- which sits a few pixels below the row it opens -- cannot be
            # mistaken for a candidate inside the band.
            index = _row_at(rows, page, top,
                            int(manifest["pages"][page - 1]["height"] * ROW_TOLERANCE))
            if index is not None and before < index < after:
                found.add(index)
        return found.pop() if len(found) == 1 else None

    recovered: list[str] = []
    for run in gap_runs():
        before, after = placed.get(run[0] - 1), placed.get(run[-1] + 1)
        if before is None or after is None:
            continue
        if len(run) == 1:
            index = by_position(run[0], before, after)
            if index is not None:
                placed[run[0]] = index
                recovered.append(f"Q{run[0]}: placed on p{rows[index][0]} from its "
                                 f"position between Q{run[0] - 1} and Q{run[0] + 1}")
                continue

        # Walk the band one option block at a time. A run of two -- 2018 loses both
        # Q5 and Q6 -- is placed only if *every* question in it lands, so a partial
        # reading cannot shift the rest of the paper by one.
        cursor, found = before, []
        for number in run:
            index = _after_option_block(rows, cursor, after)
            if index is None:
                break
            found.append((number, index))
            cursor = index
        if len(found) != len(run):
            continue
        for number, index in found:
            placed[number] = index
            recovered.append(f"Q{number}: placed on p{rows[index][0]} as the row "
                             f"after Q{number - 1}'s fourth option")

    merged = sorted((index, rows[index][0], number)
                    for number, index in placed.items())
    return merged, recovered


def index_paper(work: Path) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    year = manifest["year"]

    rows: list[tuple[int, Line]] = []
    for page in range(1, manifest["num_pages"] + 1):
        rows.extend((page, line) for line in page_rows(work, page))

    expected: tuple[int, int] | None = None
    stated_marks: int | None = None
    anchor = 0
    for index, (page, line) in enumerate(rows):
        match = RANGE_RE.search(line.text)
        if match:
            expected = (int(match.group("first")), int(match.group("last")))
            # Everything before the statement is front matter -- the cover's own
            # numbered instructions included. The run starts here.
            anchor = index
            break
    for _, line in rows[anchor:anchor + 12]:
        marks = TOTAL_MARKS_RE.search(line.text)
        if marks:
            stated_marks = int(marks.group("marks"))
            break

    def in_range(number: int) -> bool:
        return not expected or expected[0] <= number <= expected[1]

    # Vision reads the number as part of the question's own first row.
    candidates: dict[int, tuple[int, int]] = {}   # row index -> (page, number)
    for index in range(anchor, len(rows)):
        page, line = rows[index]
        width = manifest["pages"][page - 1]["width"]
        if line.left > width * MARKER_ZONE:
            continue
        match = QUESTION_RE.match(line.text.strip())
        if match and in_range(int(match.group("question"))):
            candidates[index] = (page, int(match.group("question")))

    # Tesseract, as a second reader. The two drop different glyphs -- Vision loses
    # 2025's "10" and "11" entirely while tesseract reads both -- so the union
    # covers far more of the paper than either alone, and neither is trusted to
    # place a number the other contradicts.
    margins: list[int] = []
    loose: list[tuple[int, int, int, int]] = []   # page, top, left, number
    for page in range(1, manifest["num_pages"] + 1):
        words, width, height = page_words(work, page)
        for word in words:
            if word.left > width * MARKER_ZONE:
                continue
            match = NUMBER_RE.match(word.text)
            if not match:
                continue
            loose.append((page, word.top, word.left, int(match.group("question"))))

    for page, top, left, number in loose:
        if not in_range(number):
            continue
        index = _row_at(rows, page, top,
                        int(manifest["pages"][page - 1]["height"] * ROW_TOLERANCE))
        if index is None or index < anchor:
            continue
        if index in candidates and candidates[index][1] != number:
            # The readers disagree about this row. Keep Vision's, which read the
            # number in the context of the question text rather than alone.
            continue
        candidates.setdefault(index, (page, number))
        margins.append(left)

    ordered = sorted(candidates)
    accepted_index = longest_increasing_run([candidates[i][1] for i in ordered])
    chosen = [(ordered[i], *candidates[ordered[i]]) for i in sorted(accepted_index)]
    margins.extend(rows[index][1].left for index, _, _ in chosen)

    warnings: list[str] = []
    repairs: list[str] = []
    if expected and margins:
        chosen, recovered = _recover_positions(rows, manifest, chosen, loose,
                                               expected, margins)
        repairs.extend(recovered)
    questions: dict[int, dict] = {}
    for position, (index, _page, number) in enumerate(chosen):
        # A question runs to the next one, so its pages are every page its rows
        # touch. Diagram-heavy questions routinely spill onto the following page.
        end = chosen[position + 1][0] if position + 1 < len(chosen) else len(rows)
        pages: list[int] = []
        options: set[int] = set()
        for row_page, line in rows[index:end]:
            if row_page not in pages:
                pages.append(row_page)
            options.update(int(v) for v in OPTION_RE.findall(line.text))
        questions[number] = {"question": number, "pages": pages,
                             "options": sorted(options)}

    numbers = sorted(questions)
    if not numbers:
        warnings.append("no questions found")
    else:
        low, high = expected or (numbers[0], numbers[-1])
        missing = [n for n in range(low, high + 1) if n not in questions]
        if missing:
            warnings.append(f"no question found for {missing}")
        if not MIN_QUESTIONS <= len(numbers) <= MAX_QUESTIONS:
            warnings.append(f"found {len(numbers)} questions, outside the plausible "
                            f"range {MIN_QUESTIONS}-{MAX_QUESTIONS}")
    if expected is None:
        warnings.append("no 'For each question from N to M' statement found; the "
                        "question range is whatever was read, not what the paper says")

    # Every Booklet A question offers exactly four options. A question showing
    # fewer has usually had them drawn rather than written -- 2012 Q1's options are
    # four bird pictures -- so this is a note for review, not a failure.
    incomplete = [n for n in numbers if len(questions[n]["options"]) != 4]
    if incomplete:
        warnings.append(f"fewer than four options were read for {incomplete}; they "
                        f"are probably pictures, but check the page")

    marks_each = None
    if stated_marks and numbers:
        marks_each, remainder = divmod(stated_marks, len(numbers))
        if remainder:
            warnings.append(f"{len(numbers)} questions do not divide the stated "
                            f"{stated_marks} marks evenly")
            marks_each = None

    return {
        "year": year,
        "num_pages": manifest["num_pages"],
        "booklet_a": {"start": 1, "end": manifest["num_pages"]},
        "expected_questions": list(expected) if expected else None,
        "stated_total_marks": stated_marks,
        "marks_per_question": marks_each,
        "questions": [questions[n] for n in numbers],
        "repairs": repairs,
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_A)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = index_paper(work)
        (work / "questions.json").write_text(json.dumps(result, indent=2))
        numbers = [q["question"] for q in result["questions"]]
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{year}: {len(numbers)} questions ({span}), "
              f"{result['stated_total_marks']} marks, "
              f"{result['marks_per_question']} each")
        for repair in result["repairs"]:
            print(f"    {repair} — check this against the scan")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
