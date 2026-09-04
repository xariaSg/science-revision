"""Read the English Booklet B answer key: a letter, a word or a sentence per question.

Booklet A's key and Booklet B's are printed on the same sheet and read nothing
alike, which is why this is a separate module from `build/en_key.py` rather than
a branch inside it.

Booklet A's is a grid of *isolated digits*, which Vision barely reads at page
scale, so that module finds the ruled cells and reads each one on its own. Booklet
B's answers are words -- "commemorate", "undoubtedly", `Lisa asked Ben, "Did you
manage..."` -- and Vision reads words very well: at page scale it returns all 35
of the cloze and editing answers cleanly. What it needs is not a better reader but
the right *geometry*, and the geometry here is columns:

    26.  F (had)          36.  had            46.  Instead
         G (have)         37.  commemorate    47.  groups
    27.  E (each)         38.  with           48.  whether

Three tables side by side, so a page-scale line ordering interleaves them. The
question numbers are read as tokens with an x, they cluster into columns, and each
answer is the text to the right of its number and above the next one -- the same
column discipline `segment_answers.py` applies to Science's two-column answer
pages (CLAUDE.md 1.6).

Rule detection is deliberately *not* used here even though the tables are ruled.
Booklet B's grid has shaded number cells and a heavy diagonal watermark across it,
which break the rules into segments; the reader that finds Booklet A's cells
exactly finds nothing at all in this half of the same page.

**One answer is dropped at page scale and recovered from a band re-read.** Q64's
model answer runs under a solid black watermark blob and Vision returns nothing
for the row; re-read as its own crop at 2x it comes back complete. That is the
technique CLAUDE.md 1.6.1 already uses for markers Vision loses on Science's
answer pages, and every recovery is reported rather than folded in silently.

Only the questions Booklet B is built to answer are read -- 26 to 65 on this
paper. The comprehension section's answers are tables and explanations, it is not
marked by this app (build/en_index_b.py), and reading a key for something nothing
uses would only invite it to be trusted later.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

import en_corpus
import en_key_text
from extract_answers import drop_artefacts, merge_rows
from ocr_vision import Line, page_lines, recognise

REPO = Path(__file__).resolve().parent.parent
WORK_EN_B = REPO / "work-en-b"
WORK_EN_ANS = REPO / "work-en-ans"

# A question number standing alone in the left cell of its row.
NUMBER_RE = re.compile(r"^(?P<number>\d{1,3})\s*[.)]?$")
# "F (had)" -- the letter to write, with the word it stands for in brackets. The
# child may reasonably type either, so both are recorded as acceptable.
LETTER_RE = re.compile(r"^\(?(?P<letter>[A-Z])\)?\s*\((?P<word>[^)]+)\)\s*$")
# How near two question numbers must be horizontally to be the same column.
COLUMN_TOLERANCE = 60
# A column needs this many numbers before it is treated as one, so a stray token
# that happens to look like a question number cannot open a column of its own.
MIN_COLUMN = 3
# How far below its last entry a column's final answer may reach, as a multiple of
# that column's own row spacing. Without it the last entry swallows the page
# number 800px further down; measured from the column rather than assumed, because
# row spacing differs between the tables and the prose.
LAST_ROW_REACH = 1.5
# Scale for the band re-read that recovers an answer Vision drops at page scale.
REREAD_SCALE = 2


def numbers_on(lines: list[Line]) -> list[tuple[int, Line]]:
    return [(int(match.group("number")), line) for line in lines
            for match in [NUMBER_RE.match(line.text.strip())] if match]


def columns_of(numbered: list[tuple[int, Line]]) -> list[list[tuple[int, Line]]]:
    """Group question numbers into the columns they are printed in, left to right.

    Ordered by where the column actually sits, not by the first number that
    happened to open it. Each column's right-hand edge is the next column's left,
    so an order that is merely nearly-sorted gives a column a bound to the left of
    its own text and it comes back empty -- which then looks like a page Vision
    failed to read rather than like a bug here.
    """
    columns: dict[int, list[tuple[int, Line]]] = {}
    for number, line in numbered:
        key = next((k for k in columns if abs(k - line.left) < COLUMN_TOLERANCE),
                   line.left)
        columns.setdefault(key, []).append((number, line))
    return sorted((sorted(entries, key=lambda entry: entry[1].top)
                   for entries in columns.values() if len(entries) >= MIN_COLUMN),
                  key=lambda entries: min(entry[1].left for entry in entries))


def read_page(image: Path, wanted: set[int]) -> tuple[dict[int, list[str]], list[int]]:
    """Answers found on one key page, and the questions whose cell came back empty.

    A column's right-hand edge is the next column's left edge, so an answer cannot
    run into the table beside it. That matters here: at page scale the three
    tables' rows interleave, and without the bound Q36's answer would collect
    Q26's as well.
    """
    lines = drop_artefacts(page_lines(image))
    # Filtered to the questions wanted *before* the columns are built. Booklet A's
    # key is printed on this same sheet in four more columns, and its Q11-15 sit
    # 55px from Booklet B's Q36-45 -- close enough to cluster with them, which
    # tangles the column each answer is bounded by. Only Booklet B's numbers can
    # define Booklet B's columns.
    columns = columns_of([(number, line) for number, line in numbers_on(lines)
                          if number in wanted])
    if not columns:
        return {}, []

    lefts = [min(entry[1].left for entry in entries) for entries in columns]
    found: dict[int, list[str]] = {}
    empty: list[tuple[int, int, int, int]] = []
    for position, entries in enumerate(columns):
        right = (lefts[position + 1] - COLUMN_TOLERANCE // 2
                 if position + 1 < len(lefts) else 10 ** 6)
        gaps = [b[1].top - a[1].top for a, b in zip(entries, entries[1:])]
        spacing = sorted(gaps)[len(gaps) // 2] if gaps else 100
        for order, (number, line) in enumerate(entries):
            top = line.top - spacing // 4
            if order + 1 < len(entries):
                bottom = entries[order + 1][1].top - spacing // 4
            else:
                # The last entry in a column has no next number to bound it
                # from below, so its reach starts as a guess -- a multiple of
                # the column's typical row gap -- and is then grown line by
                # line rather than trusted outright: a cell that wraps onto
                # more lines than any other in the column (2025 Nanyang's Q60,
                # four lines of "both/ so/ very/ .../ surprisingly" against one
                # or two everywhere else) needs more room than that guess
                # gives. Extended only while consecutive candidate lines keep
                # pace with each other, the same small-gap test `read_inline`
                # uses for a wrapped sentence, so a real break -- the page
                # footer, the table's own closing rule -- still ends it.
                bottom = line.top + int(spacing * LAST_ROW_REACH)
                cursor = line.bottom
                for other in sorted((candidate for candidate in lines
                                     if line.right < candidate.left < right
                                     and candidate.top >= top
                                     and candidate.text.strip()),
                                    key=lambda candidate: candidate.top):
                    if other.top - cursor > spacing:
                        break
                    bottom = max(bottom, other.bottom + 1)
                    cursor = other.bottom
            body = [other.text.strip() for other in lines
                    if line.right < other.left < right and top <= other.top < bottom
                    and other.text.strip()]
            if body:
                found[number] = body
            else:
                # Carried with its column's bounds, so the re-read that recovers
                # it crops the same strip of page this pass was looking at. A
                # re-read of the full page width would return the two tables
                # beside it as well, and file all three answers under this one.
                empty.append((number, line.top, bottom, right))
    return found, empty


def reread_band(image: Path, top: int, bottom: int, left: int, right: int,
                scratch: Path) -> list[str]:
    """Read one row again as its own crop, magnified.

    For the row Vision returns nothing for at page scale. CLAUDE.md 1.6.1 uses the
    same move for markers dropped on Science's answer pages, and on the same
    terms: it recovers text the page-scale pass missed, and what it recovers is
    reported so a person can check it against the scan.
    """
    with Image.open(image) as page:
        crop = page.crop((max(0, left - 20), max(0, top - 10),
                          min(page.width, right), min(page.height, bottom + 10)))
        crop = crop.resize((crop.width * REREAD_SCALE, crop.height * REREAD_SCALE),
                           Image.LANCZOS)
        crop.save(scratch)
    return [line.text.strip() for line in recognise(scratch)
            if line.text.strip() and not NUMBER_RE.match(line.text.strip())]


# "61." opening a line, with its answer on the same line rather than in a column
# of its own. Only tried against questions the column reader above already
# failed on (see `read_inline`'s docstring), so a table page's bare left-margin
# numbers -- which never carry a full stop and text on the same line -- cannot
# satisfy this by accident.
INLINE_RE = re.compile(r"^(?P<number>\d{1,3})\.\s*(?P<rest>\S.*)$")
# How far below the line before it a wrapped continuation may start, in pixels
# at 300 dpi. On the page this exists for, a wrapped second line sits 1-10px
# below the one before it; the next question starts 44px+ down and the next
# section heading further still -- comfortably separated, so one generous
# cutoff tells a wrap from either without having to recognise a heading by its
# wording (headers on this page are not reliably all-caps: "COMPREHENSION
# (20 marks)" has a lower-case "marks" inside its own parenthesis).
WRAP_GAP = 20


def read_inline(image: Path, wanted: set[int]) -> dict[int, list[str]]:
    """A question numbered inline with its own answer on the same line.

    The fallback for a page that is not a column table at all. Nanyang's 2025
    Synthesis & Transformation answers are a plain numbered list -- "61. Lily
    told her cousin that..." -- one sentence per question, sometimes wrapping
    onto a second line that carries no number of its own. `read_page`'s column
    search finds nothing here because its columns are built from left-margin
    numbers standing *alone* on their own row, which no line on this page is.

    Restricted to `wanted` questions only, and only ever consulted for ones the
    column pass did not already place: an unbounded read of "digit, full stop,
    text" would just as happily match a line number's page footer.
    """
    rows = sorted(merge_rows(drop_artefacts(page_lines(image))),
                 key=lambda line: (line.top, line.left))
    found: dict[int, list[str]] = {}
    current: int | None = None
    last_bottom: int | None = None
    for line in rows:
        text = line.text.strip()
        if not text:
            continue
        match = INLINE_RE.match(text)
        if match and int(match.group("number")) in wanted:
            current = int(match.group("number"))
            found[current] = [match.group("rest").strip()]
        elif (current is not None and last_bottom is not None
              and line.top - last_bottom <= WRAP_GAP):
            found[current].append(text)
        else:
            current = None
        last_bottom = line.bottom
    return found


def _split_options(text: str) -> list[str]:
    """"over/ around / across" -> ["over", "around", "across"].

    Nanyang's 2025 prelim is the first key in this corpus to list more than one
    acceptable word for a blank, slash-separated and sometimes wrapped across
    two physical lines ("because/ as/ since/" then "for" on the next). Splitting
    on "/" after the per-line parse rather than before leaves every other key's
    single-word lines untouched -- a line with no slash splits to itself.
    """
    return [part.strip() for part in text.split("/") if part.strip()]


def parse_answer(mode: str, body: list[str]) -> dict:
    """One key cell, turned into what a typed answer may be compared against.

    A grammar-cloze cell prints both halves of the answer -- "F (had)" -- and a
    child may reasonably type either, so both are accepted. Q26 prints two lines,
    "F (had)" and "G (have)", because either fits the blank; each line is its own
    acceptable answer rather than part of one.
    """
    text = " ".join(body).strip() if mode == "sentence" else "\n".join(body).strip()
    entry: dict = {"text": text}
    if mode == "sentence":
        return entry

    letters: list[str] = []
    words: list[str] = []
    for line in body:
        match = LETTER_RE.match(line.strip())
        if match:
            letters.append(match.group("letter"))
            words.extend(_split_options(match.group("word")))
        else:
            words.extend(_split_options(line))
    if letters:
        entry["letters"] = letters
    entry["accept"] = sorted({*letters, *words})
    return entry


def booklet_questions(paper: str) -> tuple[dict[int, str], list[dict]]:
    path = WORK_EN_B / paper / "questions.json"
    if not path.exists():
        raise FileNotFoundError(f"{paper}: run build/en_index_b.py first ({path})")
    data = json.loads(path.read_text())
    modes = {q["question"]: q["response_mode"] for q in data["questions"]}
    return modes, data["sections"]


def _read_from_images(paper: str, answerable: dict[int, str]
                      ) -> tuple[dict[int, dict], list[str], str]:
    """The existing path: words read off the scan, column by column."""
    pages = sorted((WORK_EN_ANS / paper / "pages").glob("page-*.png"))
    if not pages:
        raise FileNotFoundError(f"{paper}: run build/en_unpack.py first")

    scratch = WORK_EN_ANS / paper / "band.png"
    found: dict[int, list[str]] = {}
    repairs: list[str] = []
    for page in pages:
        answers, empty = read_page(page, set(answerable))
        found.update(answers)
        for number, top, bottom, right in empty:
            if number in found:
                continue
            body = reread_band(page, top, bottom, 0, right, scratch)
            if body:
                found[number] = body
                repairs.append(f"Q{number}: read from a {REREAD_SCALE}x re-read of "
                               f"its row on {page.name}, having come back empty at "
                               f"page scale")
    scratch.unlink(missing_ok=True)

    # A last fallback for whatever no column and no band re-read could place: a
    # page that is not a column table at all, tried only against the gaps so it
    # can never overrule what the column reader already established.
    still_missing = set(answerable) - set(found)
    if still_missing:
        for page in pages:
            inline = read_inline(page, still_missing)
            found.update(inline)
            still_missing -= set(inline)
            if not still_missing:
                break

    answers = {number: parse_answer(answerable[number], body)
               for number, body in found.items() if number in answerable}
    return answers, repairs, "columns read off the scan"


def _read_from_text(paper: str, answerable: dict[int, str]
                    ) -> tuple[dict[int, dict], list[str], str]:
    """The key read straight from a typed PDF's own text layer.

    The same source `en_key.py` prefers for Booklet A on a school that typed its
    key rather than scanning it (`en_key_text`), read the same way: each
    question's value is already one rejoined string, which `parse_answer` takes
    exactly as it takes a single-line body read off an image.
    """
    pdf = en_corpus.part_path(paper, "Answers")
    pairs = en_key_text.read_key(pdf)
    answers = {number: parse_answer(answerable[number], [value])
               for number, value in pairs.items()
               if number in answerable and value}
    return answers, [], "PDF text layer (typed, not scanned)"


def extract(paper: str, school: str | None = None) -> dict:
    """Booklet B's key, for the questions the app is built to mark.

    Run after en_index_b.py, for the reason CLAUDE.md 1.6.1 and 7.7 both give: a
    key short at the *end* leaves no gap in its own sequence to notice, so only
    the booklet's own question set reveals it.
    """
    modes, sections = booklet_questions(paper)
    answerable = {q: mode for q, mode in modes.items() if mode != "not_built"}

    ans_pdf = en_corpus.part_path(paper, "Answers")
    if ans_pdf.exists() and en_key_text.has_native_text(ans_pdf):
        answers, repairs, read_from = _read_from_text(paper, answerable)
    else:
        answers, repairs, read_from = _read_from_images(paper, answerable)

    warnings: list[str] = []
    missing = sorted(set(answerable) - set(answers))
    if missing:
        warnings.append(f"no answer read for {missing}")
    # A one-token answer that came back as a sentence, or the reverse, means the
    # column bound is wrong -- the failure that would otherwise mark a whole
    # section against the wrong text.
    wordy = sorted(q for q, entry in answers.items()
                   if answerable[q] in {"letter", "word"}
                   and any(len(a.split()) > 3 for a in entry["accept"]))
    if wordy:
        warnings.append(f"the key for {wordy} reads as a phrase where a single "
                        f"word or letter was expected; check the column bounds")

    return {
        "paper": paper,
        "school": school,
        "subject": "english",
        "booklet": "B",
        "source": f"{school or paper} answer key",
        "read_from": read_from,
        "authoritative": False,
        "num_answers": len(answers),
        "booklet_questions": len(answerable),
        "sections": [{"section": s["section"], "first": s["first"],
                      "last": s["last"], "response_mode": s["response_mode"]}
                     for s in sections],
        "answers": [{"question": q, "response_mode": answerable[q], **answers[q]}
                    for q in sorted(answers)],
        "repairs": repairs,
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*")
    args = parser.parse_args(argv)

    registry = {p["paper"]: p for p in en_corpus.load_registry()}
    papers = args.papers or (sorted(
        path.name for path in WORK_EN_ANS.iterdir()
        if path.is_dir() and (path / "manifest.json").exists())
        if WORK_EN_ANS.exists() else [])
    if not papers:
        print("nothing rendered; run build/en_unpack.py first", file=sys.stderr)
        return 1

    exit_code = 0
    for paper in papers:
        result = extract(paper, (registry.get(paper) or {}).get("school"))
        (WORK_EN_ANS / paper / "answers.json").write_text(json.dumps(result, indent=2))
        print(f"{paper}: {result['num_answers']}/{result['booklet_questions']} "
              f"answers")
        for repair in result["repairs"]:
            print(f"    {repair} — check this against the scan")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
