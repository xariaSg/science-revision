"""Extract the Booklet A answer key: question number -> the one correct option.

Booklet A is multiple choice, so unlike Booklet B there is nothing to judge -- the
whole rubric is a digit. That makes the extraction both easier and less forgiving:
a misread digit is not a vague mark, it is the child being told they are wrong when
they were right. Everything here is built around making a wrong digit impossible to
ship silently rather than around reading as many as possible.

The answers share the pages Booklet B's answers are read from (work-ans/), two
columns, left read fully before right, so the geometry helpers in extract_answers
are reused unchanged. What differs is the marker and the era:

    2015-2025   "2015" / "Booklet A" headers, "1. (3)", "Explanation:" block
    2012-2014   "2012 Booklet A" on one line, "1. ( 2)", bullet-point explanations

The archives are multi-year compilations, so reading stops at the next year's
heading or at Booklet B, whichever comes first.

Two repairs, both safe only because MCQ numbering is strictly consecutive:

* A dropped number whose option digit survived ("( 2) To drink the nectar...", 2012
  Q1) is assigned the number the sequence demands.
* A marker Vision dropped whole (2020 Q3) is re-read from a crop of the gap it left
  behind, and accepted only when two independent readers agree on the digit *and*
  on the question number the sequence predicts. See `reread_marker`.

A key that is short at the *end* is the one gap the sequence cannot reveal -- 2021
loses Q28 and the numbering still looks complete. Only Booklet A's own question
count exposes it, so `build/index_mcq.py` must have run first.

Anything still missing after all that is reported, never guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ocr_vision import Line, page_lines, recognise
from extract_answers import drop_artefacts, split_columns

REPO = Path(__file__).resolve().parent.parent
WORK_ANSWERS = REPO / "work-ans"
# The Booklet A question inventory. Read for the paper's own question count, which
# is the only way to know that the key is short at the *end* -- a missing last
# answer leaves no gap in the sequence to notice.
WORK_QUESTIONS = REPO / "work-a"

# "1. (3)", "1. ( 2)", "12.(4)" — the separator and the inner spacing both vary with
# the scan. The option is a single digit 1-4; nothing else is a valid MCQ answer.
MARKER_RE = re.compile(r"^(?P<question>\d{1,3})\s*[.,:;)]?\s*"
                       r"[(\[{|]\s*(?P<option>[1-4])\s*[)\]}|]")
# The same line with the number missing. Only ever read where the sequence says a
# number belongs, and only at the head of a column entry — "option (4) cannot be
# concluded" is explanation prose and must not be mistaken for an answer.
BARE_OPTION_RE = re.compile(r"^[(\[{|]\s*(?P<option>[1-4])\s*[)\]}|]\s*")

# "Booklet A" alone (2015-2025) or with its year attached (2012-2014).
BOOKLET_RE = re.compile(r"^\s*(?:(?P<year>20[0-2]\d)\s+)?Booklet\s+(?P<label>[AB])\b",
                        re.I)
# A bare year heads the next paper in the compilation.
YEAR_RE = re.compile(r"^\s*(?P<year>20[0-2]\d)\s*$")
EXPLANATION_RE = re.compile(r"^\s*Explanation\s*:\s*(?P<rest>.*)$", re.I)
FURNITURE_RE = re.compile(
    r"PSLE\s+Yearly\s+Science|Educational\s+Publishing\s+House|"
    r"ANSWERS\s+TO\s+PSLE|^\s*\d{1,3}\s*$", re.I)
LEADING_NOISE_RE = re.compile(r"^[^\w(\[{|]+")

# Booklet A has carried 28 questions in every paper here, but the count is read from
# the paper rather than assumed. These bound what a *plausible* count is, so a stray
# "56" parsed as a question number cannot extend the run.
MIN_QUESTIONS, MAX_QUESTIONS = 15, 45

# Re-read of a dropped marker: how much to grow the crop around the gap, and how far
# to upscale it. Vision reads these small glyphs on a magnified crop that it skips
# at page scale.
CROP_PAD = 12
CROP_SCALE = 3
# The confirming crop of a single marker row: how far left of the bracketed option
# the question number sits, and the slack around the row itself.
MARKER_LEAD = 200
ROW_PAD = 18
# How far a column strip may reach past the page midpoint to keep a marker whole.
COLUMN_SLACK = 60


@dataclass
class Entry:
    question: int
    option: int
    lines: list[str] = field(default_factory=list)
    source: str = "ocr"
    # Where the marker sat, kept so a later gap can be cropped out of the page.
    page: int = 0
    left: int = 0
    top: int = 0
    bottom: int = 0
    column: int = 0
    # The foot of the marker's own row. `bottom` grows as explanation lines are
    # attached, which is exactly what a gap crop must not follow: when a marker is
    # dropped its explanation is absorbed here, so `bottom` runs past the line the
    # crop is looking for while this stays put.
    marker_bottom: int = 0

    def as_dict(self) -> dict:
        entry = {"question": self.question, "answer": self.option,
                 "explanation": " ".join(self.lines).strip()}
        if self.source != "ocr":
            # Surfaced so review starts with the entries least likely to be right.
            entry["answer_source"] = self.source
        return entry


@dataclass
class Candidate:
    """A line that looks like a marker, before it is known to be one."""
    index: int          # position in reading order across the whole section
    question: int | None
    option: int
    page: int
    column: int
    line: Line
    # Whatever the marker shares its row with. Usually nothing -- the marker is a
    # line to itself -- but the 2012-2014 papers run the first line of the
    # explanation straight on from it, and dropping the row wholesale lost that
    # line ("To drink the nectar found deep inside" from 2012 Q1).
    rest: str = ""


def choose_run(candidates: list[Candidate]) -> set[int]:
    """Pick the real markers: the longest run that increases in reading order.

    Requiring each number to be the previous plus one is what the Booklet B
    inventory does, but it cannot be used here. A single dropped marker ends the
    run and every answer after it is thrown away — which cost 2020 twenty-six of
    its twenty-eight answers.

    Real markers count upwards in reading order and noise does not, so the longest
    strictly increasing subsequence recovers the run *and* tolerates the dropouts,
    leaving them as gaps for the re-read pass. Returns the accepted indices.
    """
    numbered = [c for c in candidates if c.question is not None]
    if not numbered:
        return set()
    # O(n^2) is ample: a paper yields a few dozen candidates.
    best_length = [1] * len(numbered)
    previous = [-1] * len(numbered)
    for i, candidate in enumerate(numbered):
        for j in range(i):
            if numbered[j].question < candidate.question \
                    and best_length[j] + 1 > best_length[i]:
                best_length[i] = best_length[j] + 1
                previous[i] = j
    end = max(range(len(numbered)), key=lambda i: best_length[i])
    chosen: set[int] = set()
    while end != -1:
        chosen.add(numbered[end].index)
        end = previous[end]
    return chosen


def _read_lines(work: Path, page: int, width: int) -> list[Line]:
    image = work / "pages" / f"page-{page:03d}.png"
    if not image.exists():
        return []
    return split_columns(drop_artefacts(page_lines(image)), width)


# A marker whose number came back with letters in it. Only ever tested against the
# one number the sequence predicts (see `is_number`), never used to discover one.
# Unanchored so it can also be searched for mid-string: a single-row crop picks up
# debris from the dotted rule beside it ("oe 2 21. (1)"), and the marker is then
# not at the start of what tesseract returns.
LOOSE_MARKER_RE = re.compile(r"(?P<question>[\dA-Za-z|]{1,3})\s*[.,:;)]?\s*"
                             r"[(\[{|]\s*(?P<option>[1-4])\s*[)\]}|]")
# Glyphs these scans confuse with digits: 2020's smudged "10." comes back from
# Vision as "1D.", and the answer under it is lost to a letter.
CONFUSABLE = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "l": "1",
                            "I": "1", "i": "1", "|": "1", "Z": "2", "z": "2",
                            "S": "5", "s": "5", "G": "6", "T": "7", "B": "8",
                            "g": "9", "q": "9"})


def is_number(token: str, expected: int) -> bool:
    """Whether a marker's number token reads as `expected` once un-confused.

    Safe only because it answers a yes/no question about a number already fixed by
    the sequence. Used to *find* numbers it would invent them freely.
    """
    cleaned = token.translate(CONFUSABLE)
    return cleaned.isdigit() and int(cleaned) == expected


def reread_marker(image: Path, box: tuple[int, int, int, int],
                  expected: int) -> tuple[int, int, int] | None:
    """Re-read one dropped marker from the band it should be in.

    Returns the option and the top and bottom of the marker's own row in page
    coordinates, or None. The geometry matters as much as the digit: it is what
    lets the explanation lines below the marker be taken off the question above
    and given back to this one.

    Vision drops the occasional marker at page scale -- 2020's "3. (1)" is printed
    perfectly legibly and simply is not returned. An OCR dropout, not a geometry
    bug (CLAUDE.md section 1.5.1), so it is re-read rather than inferred.

    Two readers, because one is not enough to bet a mark on. Vision, on a magnified
    crop of the band, finds *where* the marker is -- it recovers the "(1)" even
    when it still cannot see the "3.". Tesseract then reads that one row in
    isolation with --psm 7, which is where it is strongest, and its reading is
    accepted only if it agrees with Vision on the option digit *and* reports the
    question number the sequence predicted.

    That double confirmation is the point. The band is an inference about where a
    marker sat; without it, a crop that ran past its neighbour would hand back the
    wrong answer under a plausible-looking number, and a child would be told they
    were wrong when they were right.
    """
    from PIL import Image
    import pytesseract

    left, top, right, bottom = box
    with Image.open(image) as page:
        crop = page.crop((max(0, left - CROP_PAD), max(0, top - CROP_PAD),
                          min(page.width, right + CROP_PAD),
                          min(page.height, bottom + CROP_PAD)))
        scaled = crop.resize((crop.width * CROP_SCALE, crop.height * CROP_SCALE))
        scratch = image.parent / f".reread-{image.stem}.png"
        scaled.save(scratch)
        try:
            lines = recognise(scratch)
        finally:
            scratch.unlink(missing_ok=True)

        x0, y0 = max(0, left - CROP_PAD), max(0, top - CROP_PAD)

        def to_page(line: Line) -> tuple[int, int]:
            return (y0 + line.top // CROP_SCALE, y0 + line.bottom // CROP_SCALE)

        # A whole marker, read outright, whether or not its number survived intact.
        for line in lines:
            match = LOOSE_MARKER_RE.match(LEADING_NOISE_RE.sub("", line.text.strip()))
            if match and is_number(match.group("question"), expected):
                return (int(match.group("option")), *to_page(line))

        # Otherwise the option alone, and only when there is exactly one in the
        # band -- two would mean the band spans more than the single missing
        # marker, and picking between them would be a guess.
        bare = [(line, m) for line, m in
                ((l, BARE_OPTION_RE.match(LEADING_NOISE_RE.sub("", l.text.strip())))
                 for l in lines) if m]
        if len(bare) != 1:
            return None
        line, match = bare[0]
        option = int(match.group("option"))

        # Back to page coordinates, then out to the left far enough to take in the
        # question number beside the bracket -- but never past the column edge. The
        # neighbouring column and the dotted rule between them both read as leading
        # junk that hides the marker from --psm 7 (2018 Q21 came back "ind 21 (1").
        row = (max(left, x0 + line.left // CROP_SCALE - MARKER_LEAD),
               max(0, y0 + line.top // CROP_SCALE - ROW_PAD),
               min(right, x0 + line.right // CROP_SCALE + ROW_PAD),
               min(page.height, y0 + line.bottom // CROP_SCALE + ROW_PAD))
        tight = page.crop(row)
        tight = tight.resize((tight.width * CROP_SCALE, tight.height * CROP_SCALE))

    text = pytesseract.image_to_string(tight, config="--psm 7").strip()
    # Both readers must land on the same option, under the number the sequence
    # predicts. That agreement is the whole safeguard: a wrong digit here marks a
    # right answer wrong, which is worse than leaving the gap for a human.
    confirmed = any(is_number(m.group("question"), expected)
                    and int(m.group("option")) == option
                    for m in LOOSE_MARKER_RE.finditer(text))
    return (option, *to_page(line)) if confirmed else None


def _repair_gaps(work: Path, manifest: dict, entries: dict[int, Entry],
                 expected_last: int) -> list[str]:
    """Re-read the markers missing from the run, one crop each.

    The crop is the band between the previous answer's marker and the next one's,
    in the same column — which is exactly where a dropped marker sat.
    """
    repairs: list[str] = []
    for number in range(1, expected_last + 1):
        if number in entries:
            continue
        before = entries.get(number - 1)
        after = entries.get(number + 1)
        # The previous answer must be present, or there is no band to crop with any
        # confidence about what is inside it. The following one may be absent only
        # for the paper's last question, where the booklet supplies the count that
        # the sequence itself cannot (2021 loses Q28, leaving no gap to notice).
        if not before or (after is None and number != expected_last):
            continue
        for page, box in _gap_bands(manifest, before, after):
            if box[3] - box[1] < 10:
                continue
            found = reread_marker(work / "pages" / f"page-{page:03d}.png",
                                  box, number)
            if found is None:
                continue
            option, marker_top, marker_bottom = found
            entries[number] = Entry(number, option, source="reread", page=page,
                                    column=before.column, left=box[0],
                                    top=marker_top, bottom=marker_bottom,
                                    marker_bottom=marker_bottom)
            repairs.append(f"Q{number}: re-read ({option}) from the gap on p{page}")
            break
    return repairs


def _gap_bands(manifest: dict, before: Entry,
               after: Entry | None) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Where a marker missing between two answers could be, best guess first.

    Within one column it is the strip between them. Across a column or page break
    it is one of two places -- the foot of the column the previous answer ends in,
    or the head of the column the next one starts. With no answer after it at all,
    it is whatever follows the previous one to the end of the section. All are
    tried; the caller's two-reader confirmation decides whether any holds it.
    """
    def column(page: int, index: int, anchor: Entry) -> tuple[int, int]:
        """The column's x range, widened to take in the anchoring marker.

        The page midpoint is only an approximation of the gutter: the 2016 scan sits
        far enough left that the right column's markers begin *before* it, and a
        strip cut at the midpoint sliced the "1" off 2016's "17. (3)" -- leaving a
        band that held the marker but could not show it.
        """
        half = manifest["pages"][page - 1]["width"] // 2
        left = min(index * half, anchor.left - COLUMN_SLACK)
        return max(0, left), (index + 1) * half

    height = manifest["pages"][before.page - 1]["height"]
    left, right = column(before.page, before.column, before)
    # From the foot of the previous marker's own row: below it so that marker is
    # not itself a candidate, but above where its absorbed explanation ends.
    if after is not None and before.page == after.page \
            and before.column == after.column:
        return [(before.page, (left, before.marker_bottom, right, after.top))]

    bands = [(before.page, (left, before.marker_bottom, right, height))]
    if after is not None:
        left, right = column(after.page, after.column, after)
        bands.append((after.page, (left, 0, right, after.top)))
    elif before.column == 0:
        # Nothing after it: the next place to look is the other column of the same
        # page. Beyond that the section has ended, so there is nowhere else.
        half = manifest["pages"][before.page - 1]["width"] // 2
        bands.append((before.page, (half, 0, half * 2, height)))
    return bands


def _section_index(section: list[tuple[int, Line]], manifest: dict,
                   entry: Entry) -> int | None:
    """Where a recovered marker belongs in the section's reading order.

    The first line on its own page and column that sits at or below the row the
    marker was found on -- which is the first line of its explanation, and where
    the question above it must stop.
    """
    for index, (page, line) in enumerate(section):
        if page != entry.page:
            continue
        width = manifest["pages"][page - 1]["width"]
        if (0 if line.cx < width / 2 else 1) != entry.column:
            continue
        if line.top >= entry.marker_bottom:
            return index
    return None


def read_section(work: Path, manifest: dict) -> tuple[list[tuple[int, Line]], str | None]:
    """The Booklet A answer lines of this paper's own year, in reading order.

    The archives are multi-year compilations, so this both finds the section and
    ends it — at Booklet B, or at the next year's heading, whichever comes first.
    """
    year = manifest["year"]
    body: list[tuple[int, Line]] = []
    in_booklet_a = False
    started = False
    stopped_at: str | None = None

    for page in range(1, manifest["num_pages"] + 1):
        if stopped_at:
            break
        width = manifest["pages"][page - 1]["width"]
        for line in _read_lines(work, page, width):
            text = line.text.strip()
            if not text or FURNITURE_RE.search(text):
                continue

            header = BOOKLET_RE.match(text)
            if header:
                stated = header.group("year")
                if stated and int(stated) != year:
                    if started:
                        stopped_at = f"page {page} ({stated} answers begin)"
                        break
                    continue
                if header.group("label").upper() == "A":
                    in_booklet_a, started = True, True
                else:
                    # Booklet B's answers follow; this paper's key is complete.
                    in_booklet_a = False
                    if started:
                        stopped_at = f"page {page} (Booklet B begins)"
                        break
                continue

            foreign = YEAR_RE.match(text)
            if foreign and int(foreign.group("year")) != year and started:
                stopped_at = f"page {page} ({foreign.group('year')} answers begin)"
                break

            if in_booklet_a:
                body.append((page, line))
    return body, stopped_at


def paper_questions(year: int, questions_root: Path = WORK_QUESTIONS) -> int | None:
    """How many questions Booklet A itself has, read from the question inventory.

    Two independent reads of the same paper -- one from the booklet, one from the
    answer pages -- so a disagreement means at least one is wrong. It is also the
    only way to notice a key that is short at the end: a missing last answer leaves
    no gap in the numbering for anything else to catch.
    """
    path = questions_root / str(year) / "questions.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    stated = data.get("expected_questions")
    if isinstance(stated, list) and len(stated) == 2:
        return int(stated[1])
    numbers = [q["question"] for q in data.get("questions", [])]
    return max(numbers) if numbers else None


def extract(work: Path, questions_root: Path = WORK_QUESTIONS) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    year = manifest["year"]
    section, stopped_at = read_section(work, manifest)
    expected_last = paper_questions(year, questions_root)

    # Pass 1: every line that looks like a marker, kept as a candidate only.
    candidates: list[Candidate] = []
    texts: list[str] = []
    for index, (page, line) in enumerate(section):
        text = line.text.strip()
        explanation = EXPLANATION_RE.match(text)
        if explanation:
            text = explanation.group("rest").strip()
        text = LEADING_NOISE_RE.sub("", text)
        texts.append(text)
        width = manifest["pages"][page - 1]["width"]
        column = 0 if line.cx < width / 2 else 1
        match = MARKER_RE.match(text)
        if match:
            candidates.append(Candidate(index, int(match.group("question")),
                                        int(match.group("option")), page, column,
                                        line, text[match.end():].strip()))
            continue
        bare = BARE_OPTION_RE.match(text)
        if bare:
            candidates.append(Candidate(index, None, int(bare.group("option")),
                                        page, column, line,
                                        text[bare.end():].strip()))

    # Pass 2: keep the run that counts upwards; the rest is prose that happened to
    # open with a bracketed digit.
    accepted = choose_run(candidates)
    by_index = {c.index: c for c in candidates}
    warnings: list[str] = []
    entries: dict[int, Entry] = {}
    rejected: list[int] = []
    for candidate in candidates:
        if candidate.index not in accepted:
            if candidate.question is not None:
                rejected.append(candidate.question)
            continue
        number = candidate.question
        if number in entries:
            warnings.append(f"Q{number}: a second answer ({candidate.option}) was "
                            f"found; keeping ({entries[number].option})")
            continue
        entries[number] = Entry(number, candidate.option, page=candidate.page,
                                column=candidate.column, left=candidate.line.left,
                                top=candidate.line.top,
                                bottom=candidate.line.bottom,
                                marker_bottom=candidate.line.bottom)

    # The first marker, with its "1." dropped: 2012 opens on "( 2) To drink the
    # nectar...". Taken only at the head of the run, where the number it must carry
    # is not in doubt, and only from a line before Q2's own marker.
    if 1 not in entries and 2 in entries:
        limit = next(c.index for c in candidates
                     if c.index in accepted and c.question == 2)
        bare = next((c for c in candidates
                     if c.question is None and c.index < limit), None)
        if bare is not None:
            entries[1] = Entry(1, bare.option, source="renumbered", page=bare.page,
                               column=bare.column, left=bare.line.left,
                               top=bare.line.top, bottom=bare.line.bottom,
                               marker_bottom=bare.line.bottom)
            accepted.add(bare.index)

    # Pass 3: re-read the markers that were dropped. Before any explanation text is
    # attached, not after: a dropped marker's explanation would otherwise already
    # have been absorbed by the question above it, leaving the recovered answer with
    # no text of its own and the one above it with two questions' worth.
    numbers = sorted(entries)
    # The booklet's own count when it is available: it is the only thing that can
    # tell the key is short at the end. Otherwise all that is known is what was read.
    last = expected_last or (numbers[-1] if numbers else 0)
    repairs: list[str] = []
    if MIN_QUESTIONS <= last <= MAX_QUESTIONS:
        repairs = _repair_gaps(work, manifest, entries, last)
        numbers = sorted(entries)

    # Pass 4: attach the explanation lines that follow each marker. Recovered
    # markers are not in the section's reading order, so they are keyed in by the
    # first line that sits at or below the row they were found on.
    # Each entry keyed to the row it starts at. A marker that was read owns its row
    # -- the row *is* the marker -- so that row's text is not explanation. A marker
    # that was recovered was never in this reading order at all, so it is keyed to
    # the first row below it, which is already the first line of its explanation and
    # must be kept.
    starts: dict[int, tuple[Entry, bool]] = {}
    for index, candidate in by_index.items():
        if index in accepted:
            number = candidate.question if candidate.question is not None else 1
            if number in entries:
                starts[index] = (entries[number], True)
    for entry in entries.values():
        if entry.source != "reread":
            continue
        index = _section_index(section, manifest, entry)
        if index is not None:
            starts.setdefault(index, (entry, False))

    current: Entry | None = None
    for index, (page, line) in enumerate(section):
        started = starts.get(index)
        if started is not None:
            current, is_marker = started
            if is_marker:
                candidate = by_index.get(index)
                if candidate is not None and candidate.rest:
                    current.lines.append(candidate.rest)
                continue
        if current is not None and texts[index]:
            current.lines.append(texts[index])
            current.bottom = max(current.bottom, line.bottom)

    if not numbers:
        warnings.append("no Booklet A answers found")
    else:
        gaps = [n for n in range(1, last + 1) if n not in entries]
        if gaps:
            warnings.append(f"no answer read for question(s) {gaps}")
        if not MIN_QUESTIONS <= last <= MAX_QUESTIONS:
            warnings.append(f"read {last} questions, which is outside the plausible "
                            f"range {MIN_QUESTIONS}-{MAX_QUESTIONS}")
        if expected_last and numbers[-1] > expected_last:
            warnings.append(f"the key runs to Q{numbers[-1]} but Booklet A has only "
                            f"{expected_last} questions")
        if expected_last is None:
            warnings.append("no Booklet A inventory to check the key against; run "
                            "build/index_mcq.py first")

    return {
        "year": year,
        "source": "EPH suggested answer",
        "authoritative": False,
        "ocr": "macos-vision",
        "num_questions": last,
        "booklet_questions": expected_last,
        "stopped_at": stopped_at,
        "rejected_numbers": sorted(set(rejected)),
        "repairs": repairs,
        "answers": [entries[n].as_dict() for n in numbers],
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
        (work / "mcq-answers.json").write_text(json.dumps(result, indent=2))
        withexp = sum(1 for a in result["answers"] if a["explanation"])
        print(f"{year}: {len(result['answers'])} answers "
              f"(Q1-Q{result['num_questions']}), {withexp} with an explanation")
        if result["stopped_at"]:
            print(f"    stopped at {result['stopped_at']}")
        for repair in result["repairs"]:
            print(f"    {repair} — check this against the scan")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
