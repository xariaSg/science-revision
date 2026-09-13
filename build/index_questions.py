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

import corpus
from detect_boundaries import ocr_page
from index_mcq import longest_increasing_run
from ocr_vision import page_lines as vision_lines
from segment_answers import (MARGIN_BOTTOM, MARGIN_TOP, expected_question_range,
                             group_lines, page_words)

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"

# Question numbers sit in the left margin, sub-part labels one indent in. Both are
# well inside this fraction of the page width; body text starts beyond it.
MARKER_ZONE = 0.25
# How many leading tokens may precede a sub-part label ("34 = (a) Name the...").
MARKER_LOOKAHEAD = 3
# How far past the start of its own line a sub-part label may sit, as a fraction
# of page width. Measured from the line rather than from the page edge, because
# the left margin is not a constant: St Nicholas sets Booklet B at 547px where
# 2024 sets it at 300, so its "29, (a) State all the conditions..." puts the (a)
# beyond an absolute cut-off that every PSLE paper clears easily. Its whole
# booklet indexed as thirteen questions with one part between them.
SUBPART_REACH = 0.10

# The trailing separator is optional: the full papers OCR the number bare ("37"),
# while the Booklet B extracts render it with a stop ("37."). Requiring bare digits
# silently dropped every question in the extracts. The consecutive-number rule below
# is what keeps this loose pattern from matching body text.
# The 2026 prelims print the first sub-part with no space at all -- "31(a) Name 2
# systems..." -- which tesseract hands back as one word, "31(a)". Without the
# trailing group here that token matches nothing, silently dropping the question:
# Red Swastika's Q31 and Q32 vanished this way with no gap in the sequence to
# notice, because nothing downstream of a dropped *first* question has a
# neighbour to recover it from.
QUESTION_RE = re.compile(r"^(\d{1,2})\s*[.,]?(\([a-h]\))?$", re.I)
SUBPART_RE = re.compile(r"^\(?\s*(i{1,3}|iv|v|[a-h])\s*\)$", re.I)
ROMAN_PARTS = {"i", "ii", "iii", "iv", "v"}
MARKS_RE = re.compile(r"\[\s*(\d)\s*]")
# Red Swastika writes the allocation into the sentence -- "...state one
# characteristic that helped you to classify each animal. (2m)" -- instead of
# right-aligning it in square brackets. It is the same fact and the only form that
# paper prints, so a reader that knows only brackets scores its whole Booklet B at
# nought marks, which is what happened.
INLINE_MARKS_RE = re.compile(r"\(\s*(\d)\s*m\s*\)", re.I)
# A mark allocation the main pass could not read. Tesseract mangles these small
# right-margin tokens badly -- 2024 Q29(a)'s "[2]" comes back as "{?]" -- so a token
# that merely looks bracket-shaped is worth a second, narrower look.
# The interior must not be a letter, or this also matches sub-part labels like "(a)".
MARK_CANDIDATE_RE = re.compile(r"^[\[{(<|][^a-z]{0,3}[]})>|]$", re.I)
# Fraction of page width beyond which a token is in the right margin where marks sit.
RIGHT_MARGIN = 0.80
MARK_PAD = 14
MIN_MARKS, MAX_MARKS = 1, 3
# Booklet B states its own total on its first page. The PSLE papers print it as
# "(44 marks)"; the school prelims print it eight ways between them -- "Section B:
# 44 marks", "SECTION B: 44 Marks", "Section B [44 marks]", "Section B (44 marks)",
# and bare on a cover line. Preferring the form that names the section is what
# keeps a cover listing *both* booklets' totals from handing back Booklet A's.
SECTION_TOTAL_RE = re.compile(r"(?:section|booklet)\s*B\b[^\n]{0,40}?(\d{2})\s*marks",
                              re.I)
BRACKETED_TOTAL_RE = re.compile(r"[(\[]\s*(\d{2})\s+marks\s*[)\]]", re.I)
TOTAL_MARKS_RE = re.compile(r"\b(\d{2})\s+marks\b", re.I)

# Scenario anchors: the labelled entities a question is *about* ("plant E", "tube A").
# The marking gate keys on them (CLAUDE.md section 3.3), and speech-to-text needs them
# too -- unseeded, Whisper renders "plant E" as "Planty" and the anchor is gone.
ANCHOR_RE = re.compile(
    r"\b(plant|animal|bird|fish|insect|tube|beaker|container|substance|block|"
    r"set-?up|zone|bulb|magnet|cylinder|jar|box|ball|spring|liquid|material|"
    r"object|sample|card|strip|wire|circuit|solution|mixture|seed|leaf|organism|"
    r"fungus|fungi|bacteria|nest|process|region|area|part|point|tank|pot|bag|"
    r"rod|bar|sheet|surface|powder|gas|metal|cup|bottle|straw|toy|track|"
    r"pollutant|contact|switch|lamp|weight|load|string|cloth|fabric|filter)"
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
    """Booklet B's own mark total, in whichever of its forms this paper printed.

    Tried most specific first. A form that names the section is trusted over a
    bracketed number, and that over a bare one, because several prelim covers
    print Booklet A's total beside Booklet B's and the looser patterns cannot
    tell the two apart.
    """
    booklet_b = bounds["booklet_b"]
    pages = [work / "ocr" / f"page-{page:03d}.txt"
             for page in range(booklet_b["start"],
                               min(booklet_b["start"] + 3, booklet_b["end"] + 1))]
    texts = [re.sub(r"\s+", " ", path.read_text())
             for path in pages if path.exists()]
    for pattern in (SECTION_TOTAL_RE, BRACKETED_TOTAL_RE, TOTAL_MARKS_RE):
        for text in texts:
            match = pattern.search(text)
            if match:
                return int(match.group(1))
    return None


def mark_values(text: str) -> list[int]:
    """Every mark allocation on a line, in either of the forms papers print."""
    found = MARKS_RE.findall(text) + INLINE_MARKS_RE.findall(text)
    return [int(v) for v in found if MIN_MARKS <= int(v) <= MAX_MARKS]


# A question number as Vision returns it. Either form: joined to the start of the
# question's own text, or standing alone. Both occur in the same paper -- Tao Nan
# sets its numbers in the left margin a little above the stem they belong to, so
# Vision returns "31." by itself while tesseract, grouping words into rows, hands
# back the number and the stem together.
VISION_QUESTION_RE = re.compile(r"^(\d{1,2})\s*[.,)]?(?:\s+\S|$)")
# How far apart a Vision line and the tesseract line it corresponds to may sit,
# as a fraction of page height. The two readers box the same row differently.
ROW_TOLERANCE = 0.012


def vision_candidates(work: Path, page: int, lines: list[list], width: int,
                      height: int,
                      expected: tuple[int, int]) -> list[tuple[int, int, int]]:
    """Question numbers read by Vision, mapped onto tesseract's line indices.

    Booklet A needs two readers because they drop different numbers (CLAUDE.md
    section 1.5.1), and Booklet B turns out to need it for the same reason -- Tao
    Nan's "32." comes back from tesseract as "82", and its "30." not at all, which
    between them broke the consecutive run that everything downstream hangs on.

    Vision returns the number joined to the question's first line rather than as a
    standalone token, so its reading is matched to a tesseract line by position.
    The geometry stays tesseract's: it is the reader with word boxes, and sub-part
    labels and mark allocations are found by where words sit on the line.

    Confined to the range the paper states it covers, and not used at all when it
    states none. "Any line that opens with a digit" describes a great deal of a
    science paper -- readings off a scale, years, quantities -- and admitting all
    of it cost more than the dropped numbers did: on Tao Nan it displaced Q29 and
    left the booklet indexed as six questions numbered from 6.
    """
    image = work / "pages" / f"page-{page:03d}.png"
    if not image.exists():
        return []
    tolerance = height * ROW_TOLERANCE
    centres = [(sum(w.cy for w in line) / len(line), index)
               for index, line in enumerate(lines)]

    out: list[tuple[int, int, int]] = []
    for line in vision_lines(image):
        if line.left > width * MARKER_ZONE:
            continue
        match = VISION_QUESTION_RE.match(line.text.strip())
        if not match or not expected[0] <= int(match.group(1)) <= expected[1]:
            continue
        nearest = min(centres, key=lambda c: abs(c[0] - line.cy), default=None)
        if nearest and abs(nearest[0] - line.cy) <= tolerance:
            out.append((page, nearest[1], int(match.group(1))))
    return out


def fill_question_gaps(candidates: list[tuple[int, int, int]],
                       accepted: dict[tuple[int, int], int],
                       expected: tuple[int, int] | None,
                       order: list[tuple[int, int]]) -> list[str]:
    """Place questions the consecutive run skipped, from position alone.

    `choose_question_run` demands each number be the previous plus one, which is
    what keeps body text out of the run -- and it means one dropped number ends
    the run there, losing every question after it. Where the paper states its own
    range, a missing number is not in doubt; only where it starts is. So a
    candidate carrying exactly that number, sitting between the lines its two
    neighbours were placed on, settles it.

    Refuses whenever the band holds more than one candidate for the number, so an
    ambiguous stretch is left as a gap for a person rather than guessed at.
    """
    if not expected or not accepted:
        return []
    position = {key: index for index, key in enumerate(order)}
    placed = {number: position[key] for key, number in accepted.items()
              if key in position}
    notes: list[str] = []

    for number in range(expected[0], expected[1] + 1):
        if number in placed:
            continue
        before, after = placed.get(number - 1), placed.get(number + 1)
        if before is None or after is None or after <= before:
            continue
        found = {position[(page, index)]
                 for page, index, value in candidates
                 if value == number and (page, index) in position
                 and before < position[(page, index)] < after}
        if len(found) != 1:
            continue
        slot = found.pop()
        placed[number] = slot
        accepted[order[slot]] = number
        notes.append(f"Q{number}: placed on p{order[slot][0]} from its position "
                     f"between Q{number - 1} and Q{number + 1}")
    return notes


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
    if expected:
        # Inside a stated range the numbering is dense and the candidates have
        # already been held to it, so a gap is a dropped number rather than a
        # reason to stop. Demanding each be the previous plus one ends the run at
        # the first dropout and throws away every question after it -- Tao Nan
        # loses its "30." entirely and indexed as Q37-Q41, five questions of
        # thirteen, with the first eight vanishing without trace. Taking the
        # longest increasing run instead keeps them and leaves the gap visible,
        # which is what fill_question_gaps and the coverage warning then act on.
        # This is the same discipline index_mcq.py applies to Booklet A.
        in_range = [c for c in candidates if expected[0] <= c[2] <= expected[1]]
        chosen = longest_increasing_run([c[2] for c in in_range])
        if chosen:
            return {(in_range[i][0], in_range[i][1]): in_range[i][2]
                    for i in sorted(chosen)}

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
REVIEW_POSITIONS = REPO / "review" / "question-positions.json"


def verified_marks(paper: int | str) -> dict[str, int]:
    """Human-verified mark allocations for a paper, keyed "29a" / "30b(i)".

    Some allocations are simply not readable: 2024 Q29(a) is printed as a damaged
    glyph in the scan, so no OCR pass recovers it. A person reads it off the paper
    once and it is recorded here, in the repo, because work/ is regenerated.
    """
    if not REVIEW_MARKS.exists():
        return {}
    data = json.loads(REVIEW_MARKS.read_text())
    return {k: v for k, v in data.get(str(paper), {}).items() if isinstance(v, int)}


def verified_positions(paper: int | str) -> dict[int, int]:
    """Human-verified question-number -> starting-page, review/mcq-positions.json's
    precedent carried over to Booklet B (see review/question-positions.json).

    Both readers can land on the same wrong number at once (Vision overwriting a
    correct tesseract read), or on none at all (a misread that falls outside the
    stated range never becomes a candidate), and either way the question's own
    content is silently absorbed by whichever neighbour was recognised. This is
    the override of last resort once that has been confirmed by eye against the
    scan -- it always wins, unlike fill_question_gaps's candidate-based recovery.
    """
    if not REVIEW_POSITIONS.exists():
        return {}
    data = json.loads(REVIEW_POSITIONS.read_text())
    return {int(q): int(p) for q, p in data.get(str(paper), {}).items()}


def index_paper(work: Path) -> dict:
    bounds = json.loads((work / "boundaries.json").read_text())
    booklet_b = bounds["booklet_b"]
    paper = bounds.get("paper") or str(bounds["year"])

    # The PSLE papers arrive here with a page-text cache already written, as a side
    # effect of detecting their booklet boundaries. The school prelims are supplied
    # pre-split so nothing detects anything on them, and without the cache the two
    # things Booklet B states about itself -- its question range and its mark total
    # -- are read as "not stated" rather than as "not looked for". Both are silent
    # failures: the range is what makes coverage checkable, and the total is what
    # catches a missed allocation.
    for page in range(booklet_b["start"], booklet_b["end"] + 1):
        ocr_page(work, page)

    expected = expected_question_range(work, bounds)
    verified = verified_marks(paper)

    questions: dict[int, dict] = {}
    warnings: list[str] = []
    current_q: int | None = None
    current_part: str | None = None
    current_sub: str | None = None

    # Pass 1: read every page once, and collect left-margin number candidates.
    pages: dict[int, tuple[list[list], int]] = {}
    page_heights: dict[int, int] = {}
    candidates: list[tuple[int, int, int]] = []
    for page in range(booklet_b["start"], booklet_b["end"] + 1):
        words, width, height = page_words(work, page)
        words = [w for w in words
                 if MARGIN_TOP * height <= w.cy <= MARGIN_BOTTOM * height]
        if not words:
            continue
        lines = group_lines(words)
        pages[page] = (lines, width)
        page_heights[page] = height
        for index, line in enumerate(lines):
            head = line[0]
            if head.left > width * MARKER_ZONE:
                continue
            match = QUESTION_RE.match(head.text)
            if match:
                candidates.append((page, index, int(match.group(1))))

    # A second reader over the same pages. Where the two disagree about a line,
    # Vision's reading wins: it read the number in the context of the question's
    # own text, where tesseract read it alone and returned "82" for Tao Nan's 32.
    from_vision: dict[tuple[int, int], int] = {}
    if expected:
        for page, (lines, width) in pages.items():
            for entry in vision_candidates(work, page, lines, width,
                                           page_heights[page], expected):
                from_vision[(entry[0], entry[1])] = entry[2]
        # Where both readers named the same line, Vision's number wins; where only
        # one did, that one stands. Both are held to the stated range, so a value
        # outside it is dropped rather than allowed to anchor a run.
        merged = {(page, index): number for page, index, number in candidates
                  if expected[0] <= number <= expected[1]}
        merged.update(from_vision)
        candidates = sorted((page, index, number)
                            for (page, index), number in merged.items())

    # Reading order across the whole booklet, so a question can be placed by
    # where it sits between its neighbours rather than by its own digits.
    order = [(page, index) for page in sorted(pages)
             for index in range(len(pages[page][0]))]

    accepted = choose_question_run(candidates, expected)

    repairs: list[str] = []
    for number, page in verified_positions(paper).items():
        if accepted.get((page, 0)) == number:
            continue
        for key in [k for k, v in accepted.items() if v == number]:
            del accepted[key]
        accepted.pop((page, 0), None)
        accepted[(page, 0)] = number
        repairs.append(f"Q{number}: moved to p{page} by "
                       f"review/question-positions.json")
    repairs.extend(fill_question_gaps(candidates, accepted, expected, order))
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
                # "31(a)" merges the sub-part label into the same token as the
                # question number (see QUESTION_RE above), so there is no separate
                # "(a)" token left on the line for the loop below to find it in --
                # recorded here the same way that loop would record it.
                embedded = QUESTION_RE.match(head.text)
                if embedded and embedded.group(2):
                    current_part = embedded.group(2).strip("()").lower()
                    questions[number]["parts"].append(
                        {"part": current_part, "marks": None, "page": page,
                         "marks_source": None})

            if current_q is None:
                continue
            entry = questions[current_q]
            if page not in entry["pages"]:
                entry["pages"].append(page)

            subpart_limit = max(marker_limit, head.left + width * SUBPART_REACH)
            for token in line[consumed:consumed + MARKER_LOOKAHEAD]:
                if token.left > subpart_limit:
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

            values = mark_values(text)
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
        # Two arrangements of unread allocations are settled by arithmetic rather
        # than by guesswork, and both are worth taking because the alternative is
        # an answer box the student cannot score:
        #
        #   * one unread allocation -- the stated total names it outright;
        #   * as many marks missing as there are unread allocations -- every
        #     allocation is worth at least one mark, so each is exactly one.
        #
        # Ai Tong is the second case: three sub-parts unread and three marks
        # short. Anything else genuinely is underdetermined and is left alone.
        determined: list[tuple[dict, dict, int]] = []
        if len(unknown) == 1 and MIN_MARKS <= shortfall <= MAX_MARKS:
            determined = [(unknown[0][0], unknown[0][1], shortfall)]
            reason = f"the only allocation missing from the stated {stated}"
        elif unknown and shortfall == len(unknown) * MIN_MARKS:
            determined = [(entry, part, MIN_MARKS) for entry, part in unknown]
            reason = (f"{len(unknown)} allocations unread and {shortfall} marks "
                      f"short of the stated {stated}, so each is the minimum")
        if determined:
            for entry, part, marks in determined:
                part["marks"] = marks
                part["marks_source"] = "inferred_from_total"
                entry["total_marks"] += marks
                counted += marks
                warnings = [w for w in warnings if not w.startswith(
                    f"Q{entry['question']}({part['part']}):")]
                repairs.append(f"Q{entry['question']}({part['part']}): "
                               f"inferred [{marks}] — {reason}")
        else:
            warnings.append(f"marks add up to {counted} but Booklet B states {stated}; "
                            f"{shortfall} unaccounted for across "
                            f"{len(unknown)} unread allocation(s)")

    return {
        "paper": paper,
        "year": bounds["year"],
        "school": bounds.get("school"),
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
    parser.add_argument("--papers", nargs="*",
                        help="paper ids to index, e.g. 2024 2025-prelim-rosyth")
    parser.add_argument("--years", nargs="*", type=int,
                        help="deprecated alias for --papers")
    parser.add_argument("--work", type=Path, default=WORK_DIR)
    args = parser.parse_args(argv)

    papers = (args.papers or [str(y) for y in args.years or []]
              or corpus.discover(args.work, "boundaries.json"))
    exit_code = 0
    for year in papers:
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
