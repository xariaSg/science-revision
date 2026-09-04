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

import corpus
from mcq_runs import (MARKER_ZONE, NUMBER_RE, OPTION_RE, QUESTION_RE,
                      ROW_TOLERANCE, longest_increasing_run, page_rows,
                      recover_positions, row_at)
from ocr_vision import Line
from segment_answers import page_words

REPO = Path(__file__).resolve().parent.parent
WORK_A = REPO / "work-a"

# The paper stating its own range. Every PSLE paper in this corpus words it
# identically -- "For each question from 1 to 28, four options are given." -- and
# the school prelims do not: Red Swastika prints "For Questions 1 to 28, choose the
# most suitable answer" and Raffles Girls hyphenates it on the cover as "For
# Question 1-28". Both halves of the wording are therefore optional.
RANGE_RE = re.compile(r"for\s+(?:each\s+)?questions?\s+(?:from\s+)?"
                      r"(?P<first>\d{1,2})\s*(?:to|[-–—])\s*(?P<last>\d{1,3})\b", re.I)
# "(56 marks)", and the same thing with a bracket the scan mangled -- Methodist
# Girls' closes with "]" -- or squared off, as Nanyang's "[56 marks]" is, or bare
# on a cover line of its own, as Catholic High's and Henry Park's are.
TOTAL_MARKS_RE = re.compile(r"[(\[{]?\s*(?P<marks>\d{2,3})\s+marks\b", re.I)
# "Section A (28 x 2 marks)", "Booklet A [28 x 2 marks]", "Section A (28 x 2 = 56
# marks)". The single most useful statement on the page: it names the question
# count and the value of each in one place, so their product is a stated total that
# can be checked against a total stated elsewhere.
COUNT_TIMES_MARKS_RE = re.compile(r"(?P<count>\d{1,3})\s*[x×]\s*(?P<each>\d)\s*"
                                  r"(?:marks?\b|=)", re.I)
# "28 questions", on a cover line of its own (Catholic High, Henry Park, St
# Nicholas) or inline as Red Swastika's "Booklet A: 28 questions (56 marks)".
COUNT_QUESTIONS_RE = re.compile(r"(?P<count>\d{1,3})\s+questions\b", re.I)
# A section or booklet header that also states a mark total. It is the anchor of
# last resort: Nanyang prints no range statement anywhere, so "Section A: Multiple
# Choice Questions [56 marks]" is the only thing separating the cover's own
# numbered instructions from question 1.
SECTION_HEADER_RE = re.compile(r"(?:section|booklet)\s+A\b.*?\d{1,3}\s*"
                               r"(?:[x×]\s*\d\s*)?marks", re.I)
# Booklet A questions are worth 2 marks each on every paper in both corpora --
# verified against the stated total on all 14 PSLE papers (CLAUDE.md section 1.5),
# and printed outright as "28 x 2 marks" by five of the prelim schools. Used only
# to turn a stated total into a question count when the paper states no count at
# all, and recorded in `structure_source` when it is.
ASSUMED_MARKS_EACH = 2
# PSLE Booklet A has run 28 or 30 questions across this corpus. Used only to sanity
# check what was read, never to supply it.
MIN_QUESTIONS, MAX_QUESTIONS = 15, 45


# How far into a paper the front matter can reach. Nanyang's section header is on
# page 3, behind a cover and a blank page; nothing in either corpus is later.
FRONT_MATTER_PAGES = 6


def read_structure(rows: list[tuple[int, Line]]) -> dict:
    """Everything the paper says about its own shape, with nothing reconciled yet.

    Booklet A states its shape in up to four ways and no school prints all four:

        Section A (28 x 2 marks)          <- count and value together
        Booklet A: 28 questions (56 marks)
        For each question from 1 to 28,   <- the range
                             (56 marks)   <- the total

    Collected as separate claims, each remembering the row it was printed on,
    because the reconciliation below needs to know how many *independent* printed
    statements support a count -- not how many regexes happened to fire.
    """
    claims: list[dict] = []
    anchor = 0
    last_header = None

    for index, (page, line) in enumerate(rows):
        if page > FRONT_MATTER_PAGES:
            break
        text = line.text.strip()
        claim: dict = {"row": index, "page": page, "text": text, "kinds": []}

        match = RANGE_RE.search(text)
        if match:
            first, last = int(match.group("first")), int(match.group("last"))
            claim.update(first=first, last=last, count=last - first + 1)
            claim["kinds"].append("range")
            last_header = index if last_header is None else max(last_header, index)

        match = COUNT_TIMES_MARKS_RE.search(text)
        if match:
            count, each = int(match.group("count")), int(match.group("each"))
            # The one form that states a count and the value of each together, so
            # their product is a total this row vouches for by itself.
            claim.setdefault("count", count)
            claim.update(each=each, total=count * each)
            claim["kinds"].append("count_x_marks")
        else:
            match = COUNT_QUESTIONS_RE.search(text)
            if match:
                claim.setdefault("count", int(match.group("count")))
                claim["kinds"].append("count")

        if "total" not in claim:
            match = TOTAL_MARKS_RE.search(text)
            if match:
                claim["total"] = int(match.group("marks"))
                claim["kinds"].append("total")

        if SECTION_HEADER_RE.search(text):
            last_header = index if last_header is None else max(last_header, index)

        # One row is one printed statement, however many of its facts were read
        # off it. Red Swastika's "Booklet A: 28 questions (56 marks)" states the
        # count and the total at once, and counting it twice would let a single
        # line outvote two independent ones.
        if claim["kinds"]:
            claims.append(claim)

    # The front matter ends after the last statement the paper made about its own
    # shape, in whatever form it made it. Anchoring only on a range statement or a
    # section header leaves Henry Park at row 0 -- the scan drops the leading "F"
    # of "For each question", and its "Booklet A" heading and its "(56 marks)" are
    # on separate lines, so neither pattern fires -- which puts the cover's own
    # numbered instructions back in competition with question 1.
    rowed = [c["row"] for c in claims] + ([last_header] if last_header else [])
    if rowed:
        anchor = max(rowed)
    return {"claims": claims, "anchor": anchor}


def reconcile_structure(structure: dict) -> tuple[tuple[int, int] | None, int | None,
                                                  int | None, str, list[str]]:
    """Settle on a question range from claims that may contradict each other.

    Rosyth is why this is not simply "read the range statement": it prints
    "Booklet A [28 x 2 marks]" and, on the very next line, a range statement whose
    "28" the scan renders as "23". One of those is a digit inside a sentence and
    the other is an arithmetic claim, so they are not equally good evidence.

    The tie is broken the way CLAUDE.md section 1.5 already breaks it -- on the
    invariant that the marks divide evenly. 56 marks over 23 questions is not a
    whole number of marks per question, and over 28 it is exactly 2, so the range
    statement is the misread and the paper is 28 questions long. A count claim
    that cannot divide the total is rejected outright; among those that survive,
    the one the most separate printed statements support wins.

    Returns (range, stated total, marks each, how it was decided, warnings).
    """
    claims = structure["claims"]
    warnings: list[str] = []
    if not claims:
        return None, None, None, "nothing stated", warnings

    totals = [c["total"] for c in claims if c.get("total")]
    stated_total = max(set(totals), key=totals.count) if totals else None
    each = next((c["each"] for c in claims if c.get("each")), None)

    counts: dict[int, list[dict]] = {}
    for claim in claims:
        if claim.get("count"):
            counts.setdefault(claim["count"], []).append(claim)
    each = each or next((c["each"] for c in claims if c.get("each")), None)

    divides = {n: cs for n, cs in counts.items()
               if stated_total is None or stated_total % n == 0}
    rejected = sorted(set(counts) - set(divides))
    if rejected:
        warnings.append(
            f"ignored a stated question count of {rejected} — "
            f"{stated_total} marks does not divide evenly by it; "
            f"read {sorted(divides) or 'nothing usable'} instead")

    if divides:
        # Most independent statements first, then the arithmetic form, which states
        # the count and its value together and so checks itself.
        def support(number: int) -> tuple[int, int]:
            cs = divides[number]
            return len(cs), any("count_x_marks" in c["kinds"] for c in cs)
        count = max(divides, key=support)
        source = "+".join(sorted({k for c in divides[count]
                                  for k in c["kinds"]}))
    elif stated_total:
        # No usable count stated anywhere -- Nanyang prints only "[56 marks]". The
        # per-question value is the one Booklet A constant there is.
        per = each or ASSUMED_MARKS_EACH
        if stated_total % per:
            return None, stated_total, each, "unusable", warnings + [
                f"{stated_total} marks does not divide by {per} marks per question"]
        count = stated_total // per
        source = f"total/{per}" + ("" if each else " (assumed 2 marks each)")
    else:
        return None, None, each, "nothing usable", warnings

    first = next((c["first"] for c in claims
                  if "range" in c["kinds"] and c.get("count") == count), 1)
    return (first, first + count - 1), stated_total, each, source, warnings


def index_paper(work: Path) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    year = manifest["year"]
    paper = manifest.get("paper") or str(year)

    rows: list[tuple[int, Line]] = []
    for page in range(1, manifest["num_pages"] + 1):
        rows.extend((page, line) for line in page_rows(work, page))

    # Everything before the last front-matter structure statement is the cover --
    # its own numbered instructions included. The question run starts there.
    structure = read_structure(rows)
    anchor = structure["anchor"]
    expected, stated_marks, stated_each, structure_source, structure_warnings = \
        reconcile_structure(structure)

    def in_range(number: int) -> bool:
        return not expected or expected[0] <= number <= expected[1]

    # Vision reads the number as part of the question's own first row.
    candidates: dict[int, tuple[int, int]] = {}   # row index -> (page, number)
    # From *after* the anchor, never from the anchor itself. Raffles Girls states
    # its range inside a numbered cover instruction -- "5. For Question 1-28, use
    # 2B pencil..." -- so the anchor row reads as a left-margin "5.", and admitting
    # it made question 5 appear to start on the cover. That collapses the band the
    # first four questions would have been recovered from, and the paper indexes
    # from Q5 with no gap in the sequence to notice.
    for index in range(anchor + 1, len(rows)):
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
        index = row_at(rows, page, top,
                        int(manifest["pages"][page - 1]["height"] * ROW_TOLERANCE))
        if index is None or index <= anchor:
            continue
        if index in candidates and candidates[index][1] != number:
            # The readers disagree about this row. Keep Vision's, which read the
            # number in the context of the question text rather than alone.
            continue
        candidates.setdefault(index, (page, number))
        margins.append(left)

    def longest_run(pool: dict[int, tuple[int, int]]) -> list[tuple[int, int, int]]:
        ordered = sorted(pool)
        accepted = longest_increasing_run([pool[i][1] for i in ordered])
        return [(ordered[i], *pool[ordered[i]]) for i in sorted(accepted)]

    chosen = longest_run(candidates)
    margins.extend(rows[index][1].left for index, _, _ in chosen)

    warnings: list[str] = list(structure_warnings)
    repairs: list[str] = []
    if expected and margins:
        chosen, recovered = recover_positions(rows, manifest, chosen, loose,
                                               expected, margins, anchor)
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
        warnings.append("the paper states neither a question range, a question "
                        "count nor a mark total; the range is whatever was read, "
                        "not what the paper says")

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
    marks_source = "stated total / questions found"
    if marks_each is None and stated_each:
        # Five schools print "28 x 2 marks", which says the value of a question
        # outright and does not depend on having found all of them.
        marks_each, marks_source = stated_each, "stated per question"
    if marks_each is None:
        # Nan Hua, Raffles Girls and Red Swastika state no mark total for Booklet A
        # anywhere in the booklet -- Raffles prints "56" in a score table with no
        # word "marks" beside it. Every Booklet A question in both corpora is worth
        # 2 (CLAUDE.md section 1.5), so the mark is recoverable, but it is recorded
        # as assumed rather than read: a question the app scores 0 for is worse
        # than one whose provenance is on the record.
        marks_each, marks_source = ASSUMED_MARKS_EACH, "assumed"
        warnings.append(f"no mark total is printed in this booklet; assuming "
                        f"{ASSUMED_MARKS_EACH} marks per question")

    return {
        "paper": paper,
        "year": year,
        "school": manifest.get("school"),
        "num_pages": manifest["num_pages"],
        "booklet_a": {"start": 1, "end": manifest["num_pages"]},
        "expected_questions": list(expected) if expected else None,
        "structure_source": structure_source,
        "stated_total_marks": stated_marks,
        "marks_per_question": marks_each,
        "marks_source": marks_source,
        "questions": [questions[n] for n in numbers],
        "repairs": repairs,
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*",
                        help="paper ids to index, e.g. 2024 2025-prelim-rosyth "
                             "(default: every paper rendered under --work)")
    parser.add_argument("--years", nargs="*", type=int,
                        help="deprecated alias for --papers, kept for the PSLE "
                             "corpus where a year is the paper id")
    parser.add_argument("--work", type=Path, default=WORK_A)
    args = parser.parse_args(argv)

    papers = (args.papers or [str(y) for y in args.years or []]
              or corpus.discover(args.work, "manifest.json"))
    exit_code = 0
    for paper in papers:
        work = args.work / paper
        result = index_paper(work)
        (work / "questions.json").write_text(json.dumps(result, indent=2))
        numbers = [q["question"] for q in result["questions"]]
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{paper}: {len(numbers)} questions ({span}), "
              f"{result['stated_total_marks']} marks, "
              f"{result['marks_per_question']} each "
              f"[{result['structure_source']}]")
        for repair in result["repairs"]:
            print(f"    {repair} — check this against the scan")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
