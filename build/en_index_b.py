"""Build the English Booklet B inventory: sections, questions, how each is answered.

Booklet B is five sections and none of them is multiple choice:

    Grammar cloze              26-35   10 marks   a letter A-Q from a printed bank
    Editing                    36-45   10 marks   the corrected word
    Comprehension cloze        46-60   15 marks   one word per blank
    Synthesis & transformation 61-65   10 marks   the sentence rewritten
    Comprehension              66-75   20 marks   open-ended

Every question in the first three is a blank *inside a passage*, so the page is
the unit of display and not the question -- cropping to question 47 would cut
away the paragraph it is a blank in. That is the same conclusion CLAUDE.md 7.3
reaches for Chinese 短文填空, and it is why a question here records its section's
pages rather than a span of its own.

**Two of the five sections state no question range.** Editing says only "Write the
correct word in each of the boxes. (10 marks)" and the cloze only "Fill in each
blank with a suitable word. (15 marks)"; the numbers are printed as `(37)`, `(40)`
in the margin beside the passage, and Vision reads about half of them. So the
range is derived, and the derivation is arithmetic rather than assumption: a run
of sections that state no range is bounded by the stated ranges either side --
Q26-35 before and Q61-65 after -- and the 25 questions between them must equal the
sum of those sections' marks, 10 + 15. When it does, every question in the run is
worth exactly one mark and the split falls out. When it does not, the booklet is
not indexed at all.

That check is what makes this safe rather than plausible. CLAUDE.md 7.3 warns
against taking a section's last question from the highest number seen, because a
missed question moves it and leaves no gap for anyone to notice. Nothing here
reads a number to find a boundary; the boundaries come from the marks the paper
prints, and the numbers Vision *did* read are used only to corroborate them.

**The comprehension section is deliberately not built.** Its answers are tables,
ticks and explanations rather than a blank to fill, and marking them needs the
kind of hand-authored rubric CLAUDE.md 3.1 describes and section 10.5 explains is
not worth faking. It is indexed so the student can read it and so the section
before it is bounded, and it carries `response_mode: "not_built"` -- the app shows
the pages and offers no answer box, which is the honest state rather than a
half-working one.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from extract_answers import drop_artefacts, merge_rows
from mcq_runs import page_rows
from ocr_vision import Line, page_lines

REPO = Path(__file__).resolve().parent.parent
WORK_EN_B = REPO / "work-en-b"

# A section states its marks exactly once, at the end of its instruction. That is
# the anchor: unlike a range statement, every section in this booklet prints one.
# The brackets are optional -- Nan Hua's grammar-cloze and editing instructions
# both end in a bare "10  marks" with nothing around it, where every other
# section on the same paper, and every section of every other school seen so
# far, wraps it "(10 marks)". Per-question allocations inside the comprehension
# are written "[2m]" and "(1m)", which this deliberately does not match: the
# word "marks" spelled out is what a section total states and a per-question
# figure never does.
MARKS_RE = re.compile(r"[(\[{]?\s*(?P<marks>\d{1,3})\s+marks?\s*[)\]}]?", re.I)
# "Section E: Grammar Cloze (10 x 1 mark)" -- Raffles Girls states every
# section's total this way, matching Booklet A's SECTION_TOTAL_RE. Read
# separately from MARKS_RE for the same reason as there: "10 x 1 mark" read as
# a bare "N marks" phrase reports 1, not 10. Unlike Booklet A's heading, which
# sits *before* the row this module anchors on, this one doubles as the anchor
# itself -- the range and response mode it needs are only ever a few rows
# below it, never above.
SECTION_TOTAL_RE = re.compile(r"(?P<count>\d{1,3})\s*[x×]\s*(?P<per>\d{1,3})"
                              r"\s*marks?\b", re.I)
# How many rows below an "N x M mark" heading its own descriptive sentence (and
# so its range and response-mode wording) can be expected within. Generous
# against the two or three lines every section seen so far actually takes.
HEADING_LOOKAHEAD = 8
# A range, worded four ways across this booklet: "numbered 26 to 35", "questions
# 61 to 65", "answer questions 66 to 75", "For each of the questions 61 to 65".
RANGE_RE = re.compile(r"(?:questions?|blanks?|numbered)\s+(?:from\s+)?"
                      r"(?P<first>\d{1,3})\s*(?:to|[-–—])\s*(?P<last>\d{1,3})\b",
                      re.I)
# A blank's number printed in the margin beside the passage: "(37)". Read only to
# corroborate a derived range, never to set one.
BLANK_RE = re.compile(r"[(\[]\s*(?P<number>\d{1,3})\s*[)\]]")
# "Booklet B / 65" in the cover's score box: the booklet's own total, and an
# independent check on the sections adding up.
BOOKLET_TOTAL_RE = re.compile(r"booklet\s*B\s*[/|]\s*(?P<total>\d{1,3})\b", re.I)

# How a section is answered, decided from the instruction the paper prints. The
# order matters: the letter-bank cloze also says "word", so it is tested first.
# Anything unmatched falls through to "not_built" rather than to a guess -- an app
# that offers the wrong kind of answer box is worse than one that offers none.
RESPONSE_MODES = [
    ("letter", re.compile(r"write\s+its\s+letter|letter\s*\(?[A-Z]\s*to\s*[A-Z]", re.I)),
    ("word", re.compile(r"write\s+the\s+correct\s+word|suitable\s+word|"
                        r"fill\s+in\s+each\s+blank", re.I)),
    ("sentence", re.compile(r"rewrite\s+the\s+given\s+sentence|in\s+one\s+sentence|"
                            r"using\s+the\s+word\(?s?\)?\s+provided", re.I)),
]
# The modes a student can actually answer in. "letter" and "word" are both one
# short token typed into a box and are marked by comparing it with the key;
# "sentence" is free text and is self-marked against the model answer, because
# there is no rubric for it and CLAUDE.md 3 is explicit that inventing one
# teaches wrong English with full confidence.
ANSWERABLE = {"letter", "word", "sentence"}


def load_rows(work: Path, manifest: dict) -> list[tuple[int, Line]]:
    rows: list[tuple[int, Line]] = []
    for page in range(1, manifest["num_pages"] + 1):
        rows.extend((page, line) for line in page_rows(work, page))
    return rows


# Where the booklet's right-hand margin column begins, as a fraction of the page
# width. Booklet B prints "Do not write in this space" down the outer edge of
# every question page, and `merge_rows` joins it into whichever instruction row
# it happens to sit level with -- "rewrite the given sentence(s) using the
# word(s) Do not write in this provided". It is a separate column and has to be
# treated as one, the lesson CLAUDE.md 1.6 records for the answer pages' gutter.
MARGIN_COLUMN = 0.78


def instruction_text(work: Path, page: int, rows: list[tuple[int, Line]],
                     start: int, end: int, width: int) -> str:
    """The instruction block, read from the page's left column alone.

    Taken from the unmerged Vision lines rather than from `rows`, because the
    merge that makes a question's row one line is exactly what pastes the margin
    note into it. Bounded by the vertical extent of the same rows the caller
    settled on, so the two always describe the same block of the page.
    """
    fallback = " ".join(rows[i][1].text for i in range(start, end + 1)).strip()
    image = work / "pages" / f"page-{page:03d}.png"
    if not image.exists():
        return fallback
    top, bottom = rows[start][1].top - 1, rows[end][1].bottom + 1
    kept = [line for line in drop_artefacts(page_lines(image))
            if top <= line.cy <= bottom and line.left < width * MARGIN_COLUMN]
    # Banded into visual rows *after* the margin is dropped, not merely sorted by
    # `top`. The right-aligned "(10 marks)" sits a few pixels higher than the line
    # of the sentence it shares a row with, so ordering on `top` alone lands it
    # mid-sentence -- "Write the (10 marks) correct word" -- which then matches
    # none of the response-mode patterns and quietly turns a built section into an
    # unbuilt one. The same failure CLAUDE.md 7.4 records for the Chinese key,
    # one axis over.
    banded = sorted(merge_rows(kept), key=lambda line: (line.top, line.left))
    return " ".join(line.text.strip() for line in banded
                    if line.text.strip()).strip() or fallback


def read_sections(work: Path, manifest: dict,
                  rows: list[tuple[int, Line]]) -> list[dict]:
    """Every section the booklet prints, anchored on its stated mark total.

    The range, where the section states one, is looked for only in the rows above
    the marks statement *on its own page*. Searching back to the previous section
    would sweep in that section's whole passage, and a passage is full of numbers.
    """
    found: list[dict] = []
    for index, (page, line) in enumerate(rows):
        heading = SECTION_TOTAL_RE.search(line.text)
        if heading:
            # The heading doubles as the anchor, so the block is read forward
            # from it rather than back from it -- the opposite direction from
            # the plain-total case below, and its own row is included, since
            # "Section H: Transformation / Synthesis (5 x 2 marks)" states the
            # range itself with nothing else needed above or below it.
            window = min(index + HEADING_LOOKAHEAD, len(rows))
            block = " ".join(rows[i][1].text for i in range(index, window))
            section = {"row": index, "page": page, "block_row": index,
                      "marks": int(heading.group("count")) * int(heading.group("per")),
                      "instruction": line.text.strip(), "first": None, "last": None}
        else:
            match = MARKS_RE.search(line.text)
            if not match:
                continue
            start = index
            while start > 0 and rows[start - 1][0] == page:
                start -= 1
            width = manifest["pages"][page - 1]["width"]
            block = instruction_text(work, page, rows, start, index, width)
            section = {"row": index, "page": page, "block_row": start,
                      "marks": int(match.group("marks")),
                      "instruction": block.strip(), "first": None, "last": None}

        range_match = RANGE_RE.search(block)
        if not range_match:
            # Raffles Girls fronts every section with "Section X: Name (Total
            # marks)" *before* its instruction, not after -- the reverse of the
            # order this module otherwise assumes, and true even for a section
            # whose own total is a plain "20 marks" and so is anchored and read
            # backward above. A forward window catches the range wherever the
            # backward block missed it, exactly as it already does for the
            # "N x M mark" heading case.
            window = min(index + HEADING_LOOKAHEAD, len(rows))
            range_match = RANGE_RE.search(
                " ".join(rows[i][1].text for i in range(index, window)))
        if range_match:
            first, last = (int(range_match.group("first")),
                           int(range_match.group("last")))
            if first <= last:
                section["first"], section["last"] = first, last
        section["response_mode"] = next(
            (mode for mode, pattern in RESPONSE_MODES if pattern.search(block)),
            "not_built")
        found.append(section)
    return found


def fill_ranges(sections: list[dict]) -> list[str]:
    """Give every section a range, or say why one could not be settled.

    A run of sections stating no range is bounded by the stated ranges either
    side, and the questions between them must equal the sum of the run's marks --
    one mark per blank, which is what a cloze is. That arithmetic is the check:
    when it holds the split is forced, and when it does not nothing is filled in.
    """
    problems: list[str] = []
    position = 0
    while position < len(sections):
        if sections[position]["first"] is not None:
            position += 1
            continue
        run = []
        while position < len(sections) and sections[position]["first"] is None:
            run.append(sections[position])
            position += 1

        before = run[0]
        index = sections.index(before)
        previous = sections[index - 1] if index else None
        following = sections[position] if position < len(sections) else None
        if previous is None or previous["last"] is None:
            problems.append(f"{len(run)} section(s) state no question range and "
                            f"nothing before them does either")
            continue
        if following is None or following["first"] is None:
            problems.append(f"{len(run)} section(s) state no question range and "
                            f"nothing after them does either")
            continue

        span = following["first"] - previous["last"] - 1
        marks = sum(section["marks"] for section in run)
        if span != marks:
            problems.append(
                f"Q{previous['last'] + 1}-Q{following['first'] - 1} is {span} "
                f"questions but the {len(run)} section(s) covering it state "
                f"{marks} marks; the ranges are left unset rather than guessed")
            continue
        cursor = previous["last"] + 1
        for section in run:
            section["first"] = cursor
            section["last"] = cursor + section["marks"] - 1
            section["range_source"] = "derived from the stated marks"
            cursor = section["last"] + 1
    return problems


def corroborate(rows: list[tuple[int, Line]], section: dict,
                pages: list[int]) -> str | None:
    """Check a derived range against the blank numbers actually printed.

    Vision reads roughly half of them, so this can confirm a range and can never
    set one: the highest number seen is a lower bound on the section's last, and
    every number seen must fall inside the range derived from the marks.
    """
    seen = {int(match.group("number"))
            for page, line in rows if page in pages
            for match in BLANK_RE.finditer(line.text)}
    inside = {n for n in seen if section["first"] <= n <= section["last"]}
    stray = {n for n in seen
             if 1 <= n <= 200 and not section["first"] <= n <= section["last"]}
    # Options and sub-part markers are bracketed numbers too, so a stray is only
    # reported when it sits in the numbering the booklet actually uses.
    stray = {n for n in stray if n >= section["first"] - 30}
    if stray:
        return (f"Q{section['first']}-{section['last']}: the blank numbers "
                f"{sorted(stray)} are printed on these pages but fall outside the "
                f"range derived for them")
    if not inside:
        return (f"Q{section['first']}-{section['last']}: no blank number was read "
                f"on these pages, so the derived range is unconfirmed")
    return None


def index_paper(work: Path) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    paper = manifest.get("paper") or str(manifest["year"])
    rows = load_rows(work, manifest)

    sections = read_sections(work, manifest, rows)
    warnings: list[str] = []
    notes: list[str] = []
    if not sections:
        warnings.append("no section found; no mark total is printed anywhere this "
                        "pass could read")

    warnings.extend(fill_ranges(sections))

    for position, section in enumerate(sections):
        end = (sections[position + 1]["block_row"] if position + 1 < len(sections)
               else len(rows))
        section["pages"] = sorted({page for page, _ in
                                   rows[section["block_row"]:end]})

    settled = [s for s in sections if s["first"] is not None]
    for section in settled:
        if section.get("range_source"):
            problem = corroborate(rows, section, section["pages"])
            if problem:
                notes.append(problem)

    # The sections must partition one unbroken run of questions.
    for earlier, later in zip(settled, settled[1:]):
        if later["first"] != earlier["last"] + 1:
            warnings.append(f"Q{earlier['last']} is followed by Q{later['first']}; "
                            f"the sections do not run consecutively")

    stated_total = sum(s["marks"] for s in sections)
    printed_total = next((int(m.group("total")) for _, line in rows
                          for m in [BOOKLET_TOTAL_RE.search(line.text)] if m), None)
    if printed_total is not None and printed_total != stated_total:
        warnings.append(f"the cover prints {printed_total} marks for Booklet B "
                        f"but its sections state {stated_total}")

    questions: list[dict] = []
    for position, section in enumerate(settled):
        count = section["last"] - section["first"] + 1
        marks_each, remainder = divmod(section["marks"], count)
        if remainder:
            warnings.append(f"Q{section['first']}-{section['last']}: "
                            f"{section['marks']} marks does not divide evenly by "
                            f"{count} questions")
            marks_each = None
        section["marks_per_question"] = marks_each
        for number in range(section["first"], section["last"] + 1):
            questions.append({
                "question": number,
                "section": sections.index(section),
                # The page, not a crop: these questions are blanks inside a
                # passage and a crop would cut away what they are asking about.
                "pages": section["pages"],
                "marks": marks_each,
                "response_mode": section["response_mode"],
            })

    unbuilt = [s for s in settled if s["response_mode"] not in ANSWERABLE]
    for section in unbuilt:
        notes.append(f"Q{section['first']}-{section['last']} is not built: its "
                     f"instruction matches none of {sorted(ANSWERABLE)}, so it is "
                     f"shown to read but offers no answer box")

    answerable = [q for q in questions if q["response_mode"] in ANSWERABLE]
    return {
        "paper": paper,
        "year": manifest["year"],
        "school": manifest.get("school"),
        "subject": "english",
        "num_pages": manifest["num_pages"],
        "booklet_b": {"start": min((p for s in settled for p in s["pages"]),
                                   default=1),
                      "end": manifest["num_pages"]},
        "sections": [{"section": i, "first": s["first"], "last": s["last"],
                      "marks": s["marks"],
                      "marks_per_question": s.get("marks_per_question"),
                      "response_mode": s["response_mode"],
                      "range_source": s.get("range_source", "stated"),
                      "instruction": s["instruction"], "pages": s["pages"]}
                     for i, s in enumerate(sections)],
        "stated_total_marks": stated_total,
        "printed_total_marks": printed_total,
        "questions": questions,
        "answerable": len(answerable),
        "answerable_marks": sum(q["marks"] or 0 for q in answerable),
        "warnings": warnings,
        "notes": notes,
        "needs_review": bool(warnings),
    }


def discover(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir()
                  if path.is_dir() and (path / "manifest.json").exists())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*")
    parser.add_argument("--work", type=Path, default=WORK_EN_B)
    args = parser.parse_args(argv)

    exit_code = 0
    for paper in args.papers or discover(args.work):
        work = args.work / paper
        result = index_paper(work)
        (work / "questions.json").write_text(json.dumps(result, indent=2))
        print(f"{paper}: {len(result['questions'])} questions, "
              f"{len(result['sections'])} sections, "
              f"{result['stated_total_marks']} marks "
              f"({result['answerable']} answerable, "
              f"{result['answerable_marks']} marks)")
        for section in result["sections"]:
            span = (f"Q{section['first']}-{section['last']}"
                    if section["first"] is not None else "range unsettled")
            print(f"    {span:16s} {section['marks']:2d} marks  "
                  f"{section['response_mode']:10s} p{section['pages']}  "
                  f"[{section['range_source']}]")
        for note in result["notes"]:
            print(f"    note: {note}")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
