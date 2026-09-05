"""Build the English Booklet A question inventory: sections, questions, pages.

Booklet A is multiple choice with options (1)-(4), which is Science's Booklet A,
so `build/mcq_runs.py` finds the questions in both. Everything about the paper's
*shape* is different, and the difference is not cosmetic:

    Science Booklet A          one range statement, 28 questions, 2 marks each
    English Booklet A          four range statements, 25 questions, 1 mark each

English states its shape a section at a time, and each statement carries its own
total:

    For each question from 1 to 10, four options are given.        (10 marks)
    For each question from 11 to 15, four options are given.        (5 marks)
    For each question from 16 to 20, choose the word(s) closest...  (5 marks)
    For each question from 21 to 25, choose the best answer.        (5 marks)

That is a better source than Science's single statement, not a worse one -- it is
the shape CLAUDE.md section 7.3 describes for Chinese, where the paper states a
count and a total per section and the index is checked against every one of them.
`reconcile_structure` in index_mcq.py exists because a Science paper says its
shape once and the reading of it may be wrong; here four independent statements
must agree with what was found, and a paper that indexes at all indexes right.

Two things follow from the layout that Science's Booklet A never has to handle:

* **A question can be unanswerable from its own page.** Q21-25 ask about a poster
  and an article printed two pages earlier, and the page introducing them says so
  ("...and answer questions 21 to 25"). Those pages are recorded as the section's
  `context_pages` and shown with every question in it. Getting this wrong is not
  a cosmetic failure: the student is shown a question about a text they cannot
  see.

* **Booklet A's last page belongs to Booklet B.** The paper prints Booklet B's
  comprehension passage at the back of Booklet A and says so in as many words --
  "Refer to the passage below when you answer questions 66 to 75 in Booklet B."
  Left alone it is swept into the last question's page span, so the student
  answering Q25 is shown a page of Booklet B's passage under it.

Both are read off the paper rather than assumed, which is the same discipline
sections 1.5 and 7.3 arrive at: the paper states its own structure, so nothing
here needs a per-paper constant.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import mcq_runs
from mcq_runs import (MARKER_ZONE, NUMBER_RE, OPTION_RE, QUESTION_RE,
                      ROW_TOLERANCE, longest_increasing_run, page_rows,
                      recover_positions, row_at)
from ocr_vision import Line
from segment_answers import page_words

REPO = Path(__file__).resolve().parent.parent
WORK_EN_A = REPO / "work-en-a"

# A section header: the paper stating the range one section covers. Worded three
# ways across this corpus -- "For each question from 1 to 10", "For each question
# from 11 to 15", "For questions 21 to 25" -- so both halves are optional, as
# they are in index_mcq.RANGE_RE for the same reason. The leading "f" is also
# optional: Methodist Girls' Q16-20 header OCRs as "-or each question from 16 to
# 20", the dash replacing the letter rather than dropping it outright, and
# CLAUDE.md 10.3 records the same class of failure losing "F" entirely on
# Henry Park's Science prelim. Requiring only "or each question(s) ... N to M"
# is specific enough that nothing else in a paper reads as one by accident.
SECTION_RE = re.compile(r"f?or\s+(?:each\s+)?questions?\s+(?:from\s+)?"
                        r"(?P<first>\d{1,3})\s*(?:to|[-–—])\s*(?P<last>\d{1,3})\b",
                        re.I)
# "(10 marks)", "[5 marks]", "5 marks" bare on a line of its own.
MARKS_RE = re.compile(r"[(\[{]?\s*(?P<marks>\d{1,3})\s+marks?\b", re.I)
# "(10 x 1 mark)" -- a section's own heading stating question count and
# per-question value rather than a total. Matched separately from MARKS_RE:
# read as a plain "N marks" phrase, "10 x 1 mark" would report 1, not 10.
SECTION_TOTAL_RE = re.compile(r"(?P<count>\d{1,3})\s*[x×]\s*(?P<per>\d{1,3})"
                              r"\s*marks?\b", re.I)
# A range named by something that is not a section header. Two of them appear in
# this booklet and they mean opposite things, which is why the range they name is
# what separates them: "...and answer questions 21 to 25" introduces the material
# for a section still to come, and "...questions 66 to 75 in Booklet B" hands over
# to the other booklet entirely.
RANGE_MENTION_RE = re.compile(r"questions?\s+(?P<first>\d{1,3})\s*(?:to|[-–—])\s*"
                              r"(?P<last>\d{1,3})\b", re.I)
BOOKLET_B_RE = re.compile(r"booklet\s*B\b", re.I)
# St Nicholas never states its Visual Text section's range with "for each
# question..." at all -- the only sentence naming Q21-25 is the stimulus
# introduction itself, "Study the poster (Text 1) and a school newsletter
# article (Text 2) and answer questions 21 to 25 (5 marks)", doing both jobs at
# once. Requiring "study the" rules out the Booklet B handover, which reads
# "questions N to M" too but never that way, and neither statement can be
# confused for the other by wording alone -- one hands the booklet over, the
# other opens a section of it.
STIMULUS_SECTION_RE = re.compile(
    r"study\s+the\b.{0,120}?\band\s+answer\s+questions?\s+(?:from\s+)?"
    r"(?P<first>\d{1,3})\s*(?:to|[-–—])\s*(?P<last>\d{1,3})\b", re.I)

# How far into the booklet a section header can be. Unlike Science's front matter
# (index_mcq.FRONT_MATTER_PAGES) there is no such bound here -- the last section
# header of this paper is on page 9 of 10 -- so headers are searched for over the
# whole booklet and it is the *first* one that ends the cover.
#
# English Paper 2 Booklet A has run 25 questions across the papers seen. Used only
# to sanity check what was read, never to supply it.
MIN_QUESTIONS, MAX_QUESTIONS = 10, 45


def load_rows(work: Path, manifest: dict) -> list[tuple[int, Line]]:
    rows: list[tuple[int, Line]] = []
    for page in range(1, manifest["num_pages"] + 1):
        rows.extend((page, line) for line in page_rows(work, page))
    return rows


def read_sections(rows: list[tuple[int, Line]]) -> list[dict]:
    """Every section header the booklet prints, with the marks stated beside it.

    The mark total is printed right-aligned on its own line, usually one or two
    rows below the instruction it belongs to and occasionally interleaved with
    it -- on this paper "(5 marks)" for Q11-15 lands *between* the second and
    third lines of that section's instruction. So it is taken from the rows
    between one header and the next rather than from the header's own row, and
    the first such figure wins: a later one belongs to the next section.

    Raffles Girls states it differently again, and earlier: a "Section A:
    Grammar (10 x 1 mark)" heading sits on its own row immediately *before* the
    "For each question..." row this function anchors on, and a plain MARKS_RE
    search of "10 x 1 mark" itself would misread it as 1 mark, catching the
    "1" rather than the "10" -- SECTION_TOTAL_RE reads count and per-question
    value separately and multiplies them, and is checked only on that one
    heading row rather than widening the search generally.
    """
    found = []
    for index, (page, line) in enumerate(rows):
        match = SECTION_RE.search(line.text)
        if not match:
            continue
        first, last = int(match.group("first")), int(match.group("last"))
        if last < first:
            continue
        found.append({"row": index, "page": page, "first": first, "last": last,
                      "count": last - first + 1, "self_stimulus": False,
                      "instruction": line.text.strip(), "marks": None})

    # STIMULUS_SECTION_RE only ever opens a section that nothing above already
    # did. Methodist Girls and Raffles Girls both print the stimulus sentence
    # *and*, several pages later, a proper "For each question from 21 to 25..."
    # header for the same range -- there the stimulus sentence is exactly what
    # `find_context` is for, and treating it as a section of its own would file
    # Q21-25 twice. St Nicholas prints only the stimulus sentence, and nothing
    # else ever states that range, which is what makes it safe to open one from.
    covered = {n for section in found
              for n in range(section["first"], section["last"] + 1)}
    for index, (page, line) in enumerate(rows):
        match = STIMULUS_SECTION_RE.search(line.text)
        if not match:
            continue
        first, last = int(match.group("first")), int(match.group("last"))
        if last < first or set(range(first, last + 1)) & covered:
            continue
        found.append({"row": index, "page": page, "first": first, "last": last,
                      "count": last - first + 1, "self_stimulus": True,
                      "instruction": line.text.strip(), "marks": None})
    found.sort(key=lambda section: section["row"])

    for position, section in enumerate(found):
        end = (found[position + 1]["row"] if position + 1 < len(found)
               else len(rows))
        heading = section["row"] - 1
        if heading >= 0:
            total_match = SECTION_TOTAL_RE.search(rows[heading][1].text)
            if total_match:
                section["marks"] = (int(total_match.group("count"))
                                    * int(total_match.group("per")))
        if section["marks"] is None:
            for index in range(section["row"], end):
                match = MARKS_RE.search(rows[index][1].text)
                if match:
                    section["marks"] = int(match.group("marks"))
                    break
        section["marks_source"] = "stated" if section["marks"] is not None else "assumed"
        if section["marks"] is None:
            # Red Swastika's Visual Text section (CLAUDE.md 11.2's "Q21-25 ask
            # about a poster... and the page introducing them says so") prints
            # no mark total anywhere at all -- the same failure section 10.3
            # documents for three Science prelim schools. English's Booklet A
            # has no exception to fall back on: every question is worth exactly
            # 1 mark, so the total is the question count, recorded as assumed
            # rather than read -- the same distinction `marks_source: "assumed"`
            # draws for Science, so a silently-invented total is never confused
            # with one the paper actually states.
            section["marks"] = section["count"]
    return found


def find_handover(rows: list[tuple[int, Line]], after: int) -> int | None:
    """The row where Booklet A stops being Booklet A.

    This booklet ends with Booklet B's comprehension passage bound into the back
    of it, under a sentence saying exactly that. Searched only after the last
    question found, so a "(Go on to Booklet B)" footer partway through -- or the
    cover's "Total Time for Booklets A and B" -- cannot truncate the paper.
    """
    for index in range(after + 1, len(rows)):
        if BOOKLET_B_RE.search(rows[index][1].text):
            return index
    return None


def find_context(rows: list[tuple[int, Line]], start: int, end: int,
                 later: set[int]) -> tuple[int, set[int]] | None:
    """A stimulus statement in the band `start`..`end`, and the range it serves.

    A stimulus statement names a range of questions that have not been reached
    yet -- "Study the poster (Text 1) and the extract from an article (Text 2)
    and answer questions 21 to 25" -- and everything after it up to the next
    section header is the material those questions are about.

    It is told apart from a section header by not being one (the header says "for
    each question", this says "answer questions") and from the Booklet B handover
    by the range it names being a range this booklet actually asks.

    The boundary returned is the top of the *page* the statement is printed on,
    not the statement's own row. Vision splits the sentence across two rows here
    -- "...and answer" / "questions 21 to 25." -- so the row that matches is the
    second, and cutting there leaves the first row in the previous question's
    page span, which shows the student a page of the next section's material
    under the question they are answering. Stimulus material always starts a
    fresh page, because it is a full page of poster or article, so the page is
    the right unit; the row is used only when a question of the current section
    also starts on that page, which would make the page cut wrong.
    """
    for index in range(start, end):
        page, line = rows[index]
        if SECTION_RE.search(line.text):
            continue
        match = RANGE_MENTION_RE.search(line.text)
        if not match:
            continue
        span = set(range(int(match.group("first")), int(match.group("last")) + 1))
        if not span or not span <= later:
            continue
        boundary = index
        while boundary > start and rows[boundary - 1][0] == page:
            boundary -= 1
        return boundary, span
    return None


def pages_of(rows: list[tuple[int, Line]], start: int, end: int) -> list[int]:
    """Every page the rows in [start, end) touch, in order.

    Furniture-only pages are dropped: this booklet prints a `BLANK PAGE` between
    the poster and the questions about it, and showing a child a blank page as
    part of a question is not neutral -- it reads as something failing to load.
    """
    pages: dict[int, bool] = {}
    for page, line in rows[start:end]:
        text = line.text.strip()
        pages[page] = pages.get(page, False) or not mcq_runs.FURNITURE_RE.search(text)
    return [page for page, has_content in pages.items() if has_content]


def find_questions(rows: list[tuple[int, Line]], manifest: dict, work: Path,
                   loose: list[tuple[int, int, int, int]],
                   section: dict, start: int, end: int) -> tuple[list, list[str]]:
    """The questions of one section, as [(row, page, number), ...].

    A slice of the paper rather than the whole of it: every index below is an
    index into `band`, so bounding the slice to one section is all that keeps a
    number read on the next section's page from being claimed by this one. That
    is also what lets `recover_positions` be reused unchanged -- it treats
    `len(rows)` as the end of the world, and here the end of the world is the end
    of the section.
    """
    band = rows[start:end]
    expected = (section["first"], section["last"])

    def in_range(number: int) -> bool:
        return expected[0] <= number <= expected[1]

    candidates: dict[int, tuple[int, int]] = {}
    for index, (page, line) in enumerate(band):
        width = manifest["pages"][page - 1]["width"]
        if line.left > width * MARKER_ZONE:
            continue
        match = QUESTION_RE.match(line.text.strip())
        if match and in_range(int(match.group("question"))):
            candidates[index] = (page, int(match.group("question")))

    margins: list[int] = []
    for page, top, left, number in loose:
        if not in_range(number):
            continue
        index = row_at(band, page, top,
                       int(manifest["pages"][page - 1]["height"] * ROW_TOLERANCE))
        if index is None:
            continue
        if index in candidates and candidates[index][1] != number:
            # The readers disagree about this row. Keep Vision's, which read the
            # number in the context of the question text rather than alone.
            continue
        candidates.setdefault(index, (page, number))
        margins.append(left)

    ordered = sorted(candidates)
    accepted = longest_increasing_run([candidates[i][1] for i in ordered])
    chosen = [(ordered[i], *candidates[ordered[i]]) for i in sorted(accepted)]
    margins.extend(band[index][1].left for index, _, _ in chosen)

    repairs: list[str] = []
    if chosen and margins:
        chosen, recovered = recover_positions(band, manifest, chosen, loose,
                                              expected, margins, anchor=0)
        repairs.extend(recovered)
    return [(start + index, page, number) for index, page, number in chosen], repairs


def index_paper(work: Path) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    paper = manifest.get("paper") or str(manifest["year"])
    rows = load_rows(work, manifest)

    sections = read_sections(rows)
    warnings: list[str] = []
    notes: list[str] = []
    if not sections:
        return {"paper": paper, "year": manifest["year"],
                "school": manifest.get("school"), "subject": "english",
                "num_pages": manifest["num_pages"],
                "booklet_a": {"start": 1, "end": manifest["num_pages"]},
                "sections": [], "questions": [],
                "stated_total_marks": None, "marks_per_question": None,
                "repairs": [], "needs_review": True,
                "warnings": ["no section header found; the booklet states no "
                             "question range anywhere this pass could read"]}

    # Tesseract, as a second reader over the whole booklet. Read once and handed
    # to every section: the two readers drop different numbers, and on this paper
    # Vision loses four of Booklet A's twenty-five (CLAUDE.md section 1.5.1).
    loose: list[tuple[int, int, int, int]] = []
    for page in range(1, manifest["num_pages"] + 1):
        words, width, _ = page_words(work, page)
        for word in words:
            if word.left > width * MARKER_ZONE:
                continue
            match = NUMBER_RE.match(word.text)
            if match:
                loose.append((page, word.top, word.left, int(match.group("question"))))

    asked = {n for section in sections
             for n in range(section["first"], section["last"] + 1)}

    # Each section runs to the next header; the last runs to the end of the paper
    # and is trimmed back to the Booklet B handover once its questions are known.
    repairs: list[str] = []
    questions: dict[int, dict] = {}
    for position, section in enumerate(sections):
        start = section["row"] + 1
        end = (sections[position + 1]["row"] if position + 1 < len(sections)
               else len(rows))
        found, section_repairs = find_questions(rows, manifest, work, loose,
                                                section, start, end)
        repairs.extend(section_repairs)

        if section["self_stimulus"] and found:
            # This section's own header row *is* its stimulus introduction --
            # St Nicholas never states a separate "for each question" line for
            # Q21-25 (STIMULUS_SECTION_RE's docstring). Reusing `context_rows`
            # / `context_for` here, the same fields `find_context` fills for a
            # section whose stimulus is announced from *inside* an earlier one,
            # means the shared post-processing loop below needs no change to
            # attach the poster and article pages to every question in it.
            section["context_for"] = list(range(section["first"], section["last"] + 1))
            section["context_rows"] = (start, found[0][0])

        # Material for a later section, printed between this section's last
        # question and the next header. It ends this section and belongs to that
        # one, so this section's questions must not run into it.
        later = asked - set(range(sections[0]["first"], section["last"] + 1))
        context = find_context(rows, found[-1][0] + 1 if found else start,
                               end, later)
        if context:
            end, span = context
            # Recorded against the section whose questions it serves, not the one
            # it happens to be printed inside. The poster sits between Q20 and
            # Q21 in the booklet and belongs entirely to Q21-25 -- filing it under
            # the section it interrupts would say the vocabulary cloze has a
            # poster attached to it, which is the opposite of what the page says.
            owner = next((s for s in sections if s["first"] in span), None)
            if owner is not None:
                owner["context_for"] = sorted(span)
                owner["context_rows"] = (end, sections[position + 1]["row"]
                                         if position + 1 < len(sections)
                                         else len(rows))

        if position == len(sections) - 1 and found:
            handover = find_handover(rows, found[-1][0])
            if handover is not None:
                end = min(end, handover)
                section["handover_row"] = handover

        section["questions"] = [number for _, _, number in found]
        section["pages"] = pages_of(rows, section["row"], end)
        for order, (row, _page, number) in enumerate(found):
            stop = found[order + 1][0] if order + 1 < len(found) else end
            options: set[int] = set()
            for _, line in rows[row:stop]:
                options.update(int(v) for v in OPTION_RE.findall(line.text))
            questions[number] = {
                "question": number,
                "section": position,
                "pages": pages_of(rows, row, stop),
                "options": sorted(options),
            }

    # Context pages attach to every question of the section they were printed for,
    # ahead of the question's own pages: the poster comes before the questions
    # about it in the booklet, and reading it first is the point.
    for section in sections:
        if "context_rows" not in section:
            continue
        start, end = section.pop("context_rows")
        pages = pages_of(rows, start, end)
        section["context_pages"] = pages
        for number in section.pop("context_for"):
            if number in questions:
                questions[number]["context_pages"] = pages

    numbers = sorted(questions)
    stated_marks = (sum(s["marks"] for s in sections)
                    if all(s["marks"] is not None for s in sections) else None)

    # Every claim the booklet makes about itself, checked against what was found.
    # Four independent statements is a far stronger position than Science's single
    # range statement (index_mcq.reconcile_structure), so nothing here has to pick
    # between contradicting claims -- a disagreement is reported, not resolved.
    for section in sections:
        label = f"Q{section['first']}-{section['last']}"
        got = section["questions"]
        if len(got) != section["count"]:
            missing = [n for n in range(section["first"], section["last"] + 1)
                       if n not in got]
            warnings.append(f"{label}: the paper states {section['count']} "
                            f"questions, {len(got)} were found"
                            + (f"; no question found for {missing}" if missing else ""))
        if section["marks_source"] == "assumed":
            notes.append(f"{label}: no mark total is printed anywhere in this "
                        f"section; assumed at 1 mark per question, which every "
                        f"other Booklet A question on every paper seen so far "
                        f"is also worth")
        if section["count"] and section["marks"] % section["count"]:
            warnings.append(f"{label}: {section['marks']} marks does not divide "
                            f"evenly by {section['count']} questions")

    overlap = [s["first"] for a, s in zip(sections, sections[1:])
               if s["first"] <= a["last"]]
    if overlap:
        warnings.append(f"sections overlap at {overlap}; the ranges the paper "
                        f"states are not consecutive")

    gaps = [n for n in range(min(asked), max(asked) + 1) if n not in asked]
    if gaps:
        warnings.append(f"the sections leave {gaps} unasked by any of them")

    # Marks per question, from the sections' own totals rather than from one
    # figure divided by everything found. A section short by one question would
    # otherwise change the value of every question in the paper.
    per_question = {s["marks"] // s["count"] for s in sections
                    if s["marks"] is not None and s["count"]
                    and not s["marks"] % s["count"]}
    marks_each = per_question.pop() if len(per_question) == 1 else None
    if marks_each is None and per_question:
        warnings.append("sections disagree about what a question is worth; "
                        "marks are recorded per section instead")

    if not numbers:
        warnings.append("no questions found")
    elif not MIN_QUESTIONS <= len(numbers) <= MAX_QUESTIONS:
        warnings.append(f"found {len(numbers)} questions, outside the plausible "
                        f"range {MIN_QUESTIONS}-{MAX_QUESTIONS}")

    # Every Booklet A question offers exactly four options. Fewer means the
    # bracketed markers did not read -- "(1)" comes back as "trim" with the
    # bracket lost, and Q17's "(1)" and "(2)" merge into "(12)" -- not that the
    # question is wrong. Nothing downstream reads this list, so it is a note
    # rather than a warning: `needs_review` drives a banner in the app, and a
    # banner that is always on for a correctly indexed paper teaches the student
    # to ignore the one that matters.
    incomplete = [n for n in numbers if len(questions[n]["options"]) != 4]
    if incomplete:
        notes.append(f"fewer than four option markers were read for {incomplete}; "
                     f"the questions are indexed, but check those pages if an "
                     f"option looks missing on screen")

    return {
        "paper": paper,
        "year": manifest["year"],
        "school": manifest.get("school"),
        "subject": "english",
        "num_pages": manifest["num_pages"],
        "booklet_a": {"start": 1, "end": max((p for q in questions.values()
                                              for p in q["pages"]
                                              + q.get("context_pages", [])),
                                             default=manifest["num_pages"])},
        "sections": [{"section": i, "first": s["first"], "last": s["last"],
                      "count": s["count"], "marks": s["marks"],
                      "marks_source": s["marks_source"],
                      "instruction": s["instruction"], "pages": s["pages"],
                      "context_pages": s.get("context_pages", []),
                      "questions": s["questions"]}
                     for i, s in enumerate(sections)],
        "expected_questions": [min(asked), max(asked)],
        "stated_total_marks": stated_marks,
        "marks_per_question": marks_each,
        "marks_source": ("stated per section"
                         if all(s["marks_source"] == "stated" for s in sections)
                         else "stated per section, assumed at 1 mark/question "
                              "where none is printed"),
        "questions": [questions[n] for n in numbers],
        "repairs": repairs,
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
    parser.add_argument("--papers", nargs="*",
                        help="paper ids to index (default: everything rendered)")
    parser.add_argument("--work", type=Path, default=WORK_EN_A)
    args = parser.parse_args(argv)

    exit_code = 0
    for paper in args.papers or discover(args.work):
        work = args.work / paper
        result = index_paper(work)
        (work / "questions.json").write_text(json.dumps(result, indent=2))
        numbers = [q["question"] for q in result["questions"]]
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{paper}: {len(numbers)} questions ({span}), "
              f"{len(result['sections'])} sections, "
              f"{result['stated_total_marks']} marks, "
              f"{result['marks_per_question']} each")
        for section in result["sections"]:
            context = (f", context p{section['context_pages']}"
                       if section["context_pages"] else "")
            print(f"    Q{section['first']}-{section['last']}: "
                  f"{len(section['questions'])}/{section['count']} questions, "
                  f"{section['marks']} marks, p{section['pages']}{context}")
        for repair in result["repairs"]:
            print(f"    {repair} — check this against the scan")
        for note in result["notes"]:
            print(f"    note: {note}")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
