"""Finding a dense run of numbered MCQs on a scanned page.

Shared by the two Booklet A indexers, because the problem is the same in both and
the way round it was hard-won. Both readers drop question numbers, and they drop
different ones (CLAUDE.md section 1.5.1): Vision loses 2025's "10" and "11"
entirely while tesseract reads both, and tesseract reads 2025 Q19's "19" as "49".
Neither alone indexes a paper completely, so what is here is the union of the two
plus three recovery tiers -- position, the option block, and the paper's own
first question.

Nothing here reads a *range*: the caller supplies one, having read it off the
paper. That is the whole reason this is reusable. Science's Booklet A states one
range for the whole booklet and English's states one per section, so the two
indexers disagree about what a paper's shape is -- but they agree completely
about what a question looks like once the band it sits in is known.

`rows` is [(page, Line), ...] in reading order and may be a *slice* of a paper:
every index below is an index into whatever list was passed, so handing one
section's rows in bounds the search to that section with nothing else to say.
"""

from __future__ import annotations

import re
from pathlib import Path

from ocr_vision import Line, page_lines
from extract_answers import drop_artefacts, merge_rows

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
# Fraction of page width within which a question number sits. There is no single
# right value: the left margin is not a constant across schools. St Nicholas
# prints its question numbers at 0.22 of the page width, further in than 2022
# prints its *options* (0.10), so a zone tight enough to exclude one paper's
# options loses another paper's questions entirely -- at 0.22 St Nicholas indexed
# 12 questions of 28 and the missing sixteen left no gap in the sequence to
# notice. It is set wide and left to be a coarse sieve, because what actually
# separates a question number from an option is not the indent: an option reads
# as "(1)" and QUESTION_RE will not match a leading bracket, and anything that
# slips through still has to survive both the stated range and the increasing-run
# filter below. Narrowing this afterwards to the margin a paper turned out to use
# was tried and reverted -- it dropped six correctly-read numbers on 2022 and
# moved Q28 onto the wrong page.
MARKER_ZONE = 0.32
# How far apart a number and the row it belongs to may sit vertically, as a
# fraction of page height. The two readers box the same row slightly differently.
ROW_TOLERANCE = 0.012
# How far a positionally recovered number may sit from where this paper puts its
# question numbers, in page-width fractions. Calibrated per paper, not assumed.
MARKER_DRIFT = 0.05


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


def row_at(rows: list[tuple[int, Line]], page: int, top: int,
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


def after_option_block(rows: list[tuple[int, Line]], before: int,
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


def first_question_start(rows: list[tuple[int, Line]], anchor: int,
                          after: int) -> int | None:
    """Where question 1 begins, given that the front matter ends at `anchor`.

    The first question is the one case the tiers below cannot reach: they place a
    question between its two neighbours, and question 1 has only one. The anchor
    is its left-hand bound -- nothing before the paper's own statement of its shape
    is a question -- which is enough to place it without reading its number.

    Four papers need this, and they need it because the number is genuinely not
    there to read: Ai Tong, Nanyang and Raffles Girls all lose the "1." and leave
    the stem starting at the body indent, with nothing to its left.

    The page matters more than the row: a question is recorded as the pages it
    spans, so an extra row of instruction text swept in from the same page changes
    nothing, while starting on the wrong page shows the student the wrong scan.
    So when question 1's options are overleaf of the front matter -- Raffles Girls
    states its range on the cover and starts the questions on page 2 -- it owns
    that page from the top, the same rule `after_option_block` applies to every
    other question that begins overleaf.
    """
    start = anchor + 1
    while start < after and (not rows[start][1].text.strip()
                             or FURNITURE_RE.search(rows[start][1].text.strip())):
        start += 1
    if start >= after:
        return None

    seen: set[int] = set()
    for index in range(start, after):
        seen.update(int(value) for value in OPTION_RE.findall(rows[index][1].text))
        if seen >= {1, 2, 3, 4}:
            if rows[index][0] != rows[start][0]:
                page = rows[index][0]
                first = index
                while first > start and rows[first - 1][0] == page:
                    first -= 1
                return first
            break
    return start


def recover_positions(rows: list[tuple[int, Line]], manifest: dict,
                       chosen: list[tuple[int, int, int]],
                       loose: list[tuple[int, int, int, int]],
                       expected: tuple[int, int],
                       margins: list[int],
                       anchor: int = 0,
                       overrides: dict[int, int] | None = None
                       ) -> tuple[list[tuple[int, int, int]], list[str]]:
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
    as a gap for a human rather than guessed at. `overrides` is that human's
    recourse when even both tiers agree on nothing: a question number mapped to
    the page it starts on, read from review/mcq-positions.json. 2026 Red Swastika's
    Q7 is the case it exists for -- Q6's own fourth option is a picture with no
    digit for OCR to read, so the option-block tier runs on into Q7's own options
    before noticing and lands on Q8's own row instead, which is rejected as out of
    bounds. A verified override always wins over either tier, the same way a
    verified answer key always wins over what OCR reads.
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
            index = row_at(rows, page, top,
                            int(manifest["pages"][page - 1]["height"] * ROW_TOLERANCE))
            if index is not None and before < index < after:
                found.add(index)
        return found.pop() if len(found) == 1 else None

    recovered: list[str] = []
    for run in gap_runs():
        # The neighbours bound the band, and where a run reaches the first or last
        # question of the paper the bound is the front matter or the end of the
        # paper. Without this the two questions most exposed to a dropped number --
        # the ones with only one neighbour -- were the two that could never be
        # recovered: four papers lose Q1 and Henry Park loses Q28.
        before = placed.get(run[0] - 1, anchor if run[0] == expected[0] else None)
        after = placed.get(run[-1] + 1,
                           len(rows) if run[-1] == expected[1] else None)
        if before is None or after is None:
            continue
        if len(run) == 1 and overrides and run[0] in overrides:
            page = overrides[run[0]]
            index = next((i for i in range(before + 1, after)
                         if rows[i][0] == page), None)
            if index is not None:
                placed[run[0]] = index
                recovered.append(f"Q{run[0]}: placed on p{page} from a "
                                 f"human-verified position "
                                 f"(review/mcq-positions.json)")
                continue
        if run[0] == expected[0]:
            index = first_question_start(rows, before, after)
            if index is not None:
                placed[run[0]] = index
                recovered.append(f"Q{run[0]}: placed on p{rows[index][0]} as the "
                                 f"first question after the front matter")
                if len(run) == 1:
                    continue
                run = run[1:]
                before = index
        if len(run) == 1:
            index = by_position(run[0], before, after)
            if index is not None:
                placed[run[0]] = index
                between = (f"between Q{run[0] - 1} and Q{run[0] + 1}"
                           if run[0] < expected[1] else f"after Q{run[0] - 1}")
                recovered.append(f"Q{run[0]}: placed on p{rows[index][0]} from its "
                                 f"position {between}")
                continue

        # Walk the band one option block at a time. A run of two -- 2018 loses both
        # Q5 and Q6 -- is placed only if *every* question in it lands, so a partial
        # reading cannot shift the rest of the paper by one.
        cursor, found = before, []
        for number in run:
            index = after_option_block(rows, cursor, after)
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
