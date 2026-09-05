"""Read the English Booklet A answer key, which is printed as a ruled grid.

Neither of the two shapes the project already reads. Science's key is prose --
`1. (3)` followed by an `Explanation:` block (CLAUDE.md 1.6.1) -- and Chinese's is
a single column of `Q1 (2)`. This one is four small tables side by side:

    +-----------------------+  +-------------+  +---------------+  +-------------+
    |       Grammar         |  |    Vocab    |  |  Vocab Cloze  |  | Visual Text |
    | 1. | 2 |  6. | 4      |  | 11. |   1   |  |   16. |   2   |  |  21. |  2   |
    | 2. | 4 |  7. | 2      |  | 12. |   3   |  |   17. |   3   |  |  22. |  2   |

Read as *text* it is hopeless: Vision returns a page-scale line like
"1. 2 6. 11. 16. 2 21. 2" -- the question numbers largely intact and half the
answers gone. That is CLAUDE.md 10.4's situation, where two Science schools
printed a grid and a person had to read it. The difference here is that this grid
is **ruled**, and ruled lines are geometry rather than glyphs: the tables, their
columns and their rows can be found exactly, and then each answer is one isolated
character in a known box rather than a digit somewhere on a page.

So the reading is per cell, and the safety comes from three places:

* **The geometry is confirmed, not assumed.** A row is only read as an answer when
  its question-number cell reads the number the sequence expects. That is what
  catches the failure that matters -- a column or row out by one, which would mark
  a whole section wrong while looking perfectly well-formed.
* **A digit is accepted only on agreement.** Each cell is read six ways (two
  binarisation thresholds x two tesseract page-segmentation modes, plus Vision at
  both), and a value is taken only when at least two readings agree and no reading
  offers a *different* option in 1-4. A cell that cannot meet that is refused.
* **What is refused goes to a person**, via review/en-mcq-key.json, on exactly
  the terms CLAUDE.md 10.4 sets: the file can fill a gap but can never quietly
  overrule the scan, and a disagreement fails the extraction outright.

This matters more than anything else in the English pipeline, for section 1.6.1's
reason: there is no partial credit to soften a wrong key. The child is simply told
they were wrong when they were right.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps

import en_corpus
import en_key_text
from ocr_vision import recognise

REPO = Path(__file__).resolve().parent.parent
WORK_EN_A = REPO / "work-en-a"
WORK_EN_ANS = REPO / "work-en-ans"
VERIFIED_KEY = REPO / "review" / "en-mcq-key.json"

VALID_OPTIONS = {1, 2, 3, 4}

# Ink threshold. Well below the paper (240+) and well above the print (~30), and
# high enough to keep a rule that the scan has faded: at 170 the Grammar table's
# own row rules read as broken on this paper and the table lost every row.
INK = 190
# A rule is a *continuous* dark run, not merely a dark column. Five stacked "4"s
# share an x and would otherwise read as a column divider; the digits' strokes are
# broken between rows and a printed rule is not.
RULE_COVERAGE = 0.9
# A horizontal rule spans a table, and a page holds several tables side by side,
# so it is measured against a fraction of the page rather than of any one table.
PAGE_RULE_WIDTH = 0.10
# Two adjacent vertical rules bound a cell when a horizontal rule runs between
# them, and bound the gap between two tables when none does. The gaps between
# these tables are *narrower* than the cells inside them -- 50px against 85-267 --
# so nothing about the spacing can tell the two apart; only the rule can.
CELL_COVERAGE = 0.85

# The section a run of tables belongs to. Read to bound Booklet A's tables and,
# more importantly, to stop before Booklet B's, whose numbering continues from
# Booklet A's and would otherwise be read as more of the same paper.
BOOKLET_RE = re.compile(r"^\s*BOOKLET\s+(?P<booklet>[AB])\b", re.I)

# A question-number cell: "16." or "16". An answer cell: one digit.
CELL_NUMBER_RE = re.compile(r"^(?P<number>\d{1,3})\s*[.)]?$")


@dataclass
class Table:
    """One ruled table: its column boundaries and its row boundaries, in pixels."""
    columns: list[tuple[int, int]]
    rows: list[tuple[int, int]]
    header: tuple[int, int]


def _longest_run(vector) -> int:
    best = current = 0
    for value in vector:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def _group(indexes: list[int], join: int = 3) -> list[tuple[int, int]]:
    """Consecutive indexes into (start, end) spans. A rule is 2-3 pixels wide."""
    spans: list[list[int]] = []
    for index in indexes:
        if spans and index - spans[-1][-1] <= join:
            spans[-1].append(index)
        else:
            spans.append([index])
    return [(span[0], span[-1]) for span in spans]


def find_tables(ink, top: int, bottom: int) -> list[Table]:
    """Every ruled table in the horizontal band [top, bottom) of a page.

    Two passes, because the two kinds of rule do not span the same thing. The row
    rules run the full width of a table, so they are found first and bound it
    vertically. The *column* rules run only through the data rows -- the header
    cell spans the whole table, so nothing divides it -- which is why they are
    looked for inside the data region rather than over the table's full height.
    """
    height, width = ink.shape
    band = ink[top:bottom]
    row_rules = [(start + top, end + top) for start, end in
                 _group([i for i, row in enumerate(band)
                         if _longest_run(row) > width * PAGE_RULE_WIDTH])]
    if len(row_rules) < 3:
        return []

    # The data region: below the header separator, down to the last row rule.
    data = ink[row_rules[1][1]:row_rules[-1][0] + 1]
    if not data.size:
        return []
    column_rules = _group([x for x in range(width)
                           if _longest_run(data[:, x]) > data.shape[0] * RULE_COVERAGE])

    tables: list[Table] = []
    current: list[tuple[int, int]] = []
    for left, right in zip(column_rules, column_rules[1:]):
        x0, x1 = left[1] + 1, right[0]
        joined = max((ink[start:end + 1, x0:x1].any(axis=0).mean() if x1 > x0 else 0)
                     for start, end in row_rules)
        if joined > CELL_COVERAGE:
            current.append((x0, x1))
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)

    return [Table(columns=columns,
                  header=(row_rules[0][1], row_rules[1][0]),
                  rows=[(a[1], b[0]) for a, b in zip(row_rules[1:], row_rules[2:])])
            for columns in tables]


def _crop(image: Image.Image, box: tuple[int, int, int, int],
          threshold: int, scale: int = 6) -> Image.Image | None:
    """One cell, binarised and trimmed to its ink with a clean white margin.

    Trimming matters more than it looks. Cropping to the rules and padding by a
    fixed few pixels clipped the top of Q5's "3" on this paper -- the digit sits a
    little high in its cell -- and a clipped glyph is not read by either engine.
    """
    cell = image.crop(box).point(lambda v: 0 if v < threshold else 255).convert("L")
    array = np.array(cell)
    ys, xs = np.where(array < 128)
    if not len(xs):
        return None
    cell = cell.crop((max(0, xs.min() - 2), max(0, ys.min() - 2),
                      min(cell.width, xs.max() + 3), min(cell.height, ys.max() + 3)))
    cell = ImageOps.expand(cell, border=8, fill=255)
    return cell.resize((cell.width * scale, cell.height * scale), Image.LANCZOS)


def read_cell(image: Image.Image, box: tuple[int, int, int, int],
              scratch: Path) -> list[str]:
    """Every reading of one cell: two thresholds x two tesseract modes, plus Vision.

    Deliberately more than two attempts. Vision is the weaker reader on an
    isolated glyph -- it returns nothing at all for roughly a third of these cells,
    having no surrounding words to work from -- so demanding one reading from each
    engine would refuse cells that four consistent readings agree about. What the
    attempts are for is disagreement: they are combined by requiring agreement and
    *no contradiction*, so a reading that is confidently wrong shows up as a
    conflict rather than being averaged away.
    """
    readings: list[str] = []
    for threshold in (150, INK):
        cell = _crop(image, box, threshold)
        if cell is None:
            continue
        for psm in (7, 10):
            readings.append(pytesseract.image_to_string(
                cell, config=f"--psm {psm} "
                             f"-c tessedit_char_whitelist=0123456789.").strip())
        cell.save(scratch)
        readings.append("".join(line.text for line in recognise(scratch)).strip())
    return [reading for reading in readings if reading]


def _digits(readings: list[str]) -> list[int]:
    """The readings that are a bare option digit, as ints."""
    out = []
    for reading in readings:
        text = reading.strip().rstrip(".)")
        if text.isdigit() and int(text) in VALID_OPTIONS:
            out.append(int(text))
    return out


def _numbers(readings: list[str]) -> list[int]:
    out = []
    for reading in readings:
        match = CELL_NUMBER_RE.match(reading.strip())
        if match:
            out.append(int(match.group("number")))
    return out


def agree(values: list[int]) -> int | None:
    """One value, if at least two readings back it and none contradicts it."""
    if not values:
        return None
    unique = set(values)
    if len(unique) != 1:
        return None
    value = unique.pop()
    return value if values.count(value) >= 2 else None


def booklet_bands(page_image: Path) -> list[tuple[str, int, int]]:
    """(booklet, top, bottom) for each BOOKLET heading printed on a page.

    Booklet B's key sits under Booklet A's on the same sheet and its numbering
    carries straight on from it, so a reader that does not stop at the heading
    reads 50 more answers as though they were Booklet A's.
    """
    lines = recognise(page_image)
    marks = [(match.group("booklet").upper(), line.top, line.bottom)
             for line in lines
             for match in [BOOKLET_RE.match(line.text)] if match]
    if not marks:
        return []
    with Image.open(page_image) as image:
        height = image.height
    bands = []
    for position, (booklet, _top, bottom) in enumerate(marks):
        end = marks[position + 1][1] if position + 1 < len(marks) else height
        bands.append((booklet, bottom, end))
    return bands


def read_grid(page_image: Path, expected: set[int],
              scratch: Path) -> tuple[dict[int, int], list[str], list[str]]:
    """Answers read from the Booklet A grids on one page of the key.

    Returns (answers, section names, problems). A row is read only when its
    question-number cell reads a number this booklet actually asks: the number
    confirms the geometry, and without it a table read one column across would
    produce a full, plausible and entirely wrong key.
    """
    with Image.open(page_image) as source:
        grey = source.convert("L")
        ink = np.array(grey) < INK
        found: dict[int, int] = {}
        conflicts: dict[int, set[int]] = {}
        sections: list[str] = []
        problems: list[str] = []

        for booklet, top, bottom in booklet_bands(page_image):
            if booklet != "A":
                continue
            for table in find_tables(ink, top, bottom):
                name = _read_text(grey, (table.columns[0][0], table.header[0],
                                         table.columns[-1][1], table.header[1]),
                                  scratch)
                if name:
                    sections.append(name)
                # Columns alternate question, answer. An odd count means the table
                # was segmented wrongly and nothing in it can be trusted.
                if len(table.columns) % 2:
                    problems.append(f"a table on {page_image.name} has "
                                    f"{len(table.columns)} columns; they should "
                                    f"pair as question and answer")
                    continue
                for row_top, row_bottom in table.rows:
                    for left, right in zip(table.columns[::2], table.columns[1::2]):
                        number = agree(_numbers(read_cell(
                            grey, (left[0], row_top, left[1], row_bottom), scratch)))
                        if number is None or number not in expected:
                            continue
                        answer = agree(_digits(read_cell(
                            grey, (right[0], row_top, right[1], row_bottom),
                            scratch)))
                        if answer is None:
                            continue
                        if number in found and found[number] != answer:
                            conflicts.setdefault(number, {found[number]}).add(answer)
                        found[number] = answer

    for number, values in sorted(conflicts.items()):
        found.pop(number, None)
        problems.append(f"Q{number}: the key was read twice and gave "
                        f"{sorted(values)}; it is not counted either way")
    return found, sections, problems


def _read_text(grey: Image.Image, box: tuple[int, int, int, int],
               scratch: Path) -> str:
    """A header cell, read as words rather than as a digit."""
    cell = _crop(grey, box, INK, scale=3)
    if cell is None:
        return ""
    cell.save(scratch)
    return " ".join(line.text for line in recognise(scratch)).strip()


def verified_key(paper: str) -> dict[int, int]:
    """A key read off the scan by a person and recorded in the repo.

    The same mechanism, and the same terms, as review/prelim-mcq-key.json
    (CLAUDE.md 10.4): it fills what the scan could not establish and is checked
    against everything the scan did, so it can never quietly overrule the page.
    """
    if not VERIFIED_KEY.exists():
        return {}
    entry = json.loads(VERIFIED_KEY.read_text()).get(paper, {})
    return {int(q): int(a) for q, a in entry.get("answers", {}).items()
            if int(a) in VALID_OPTIONS}


def booklet_questions(paper: str) -> list[int]:
    path = WORK_EN_A / paper / "questions.json"
    if not path.exists():
        raise FileNotFoundError(f"{paper}: run build/en_index.py first ({path})")
    return [q["question"] for q in json.loads(path.read_text())["questions"]]


def _read_from_grid(paper: str, expected: set[int]
                    ) -> tuple[dict[int, int], list[str], list[str], str]:
    """The existing path: a ruled grid of isolated digits, read off the scan."""
    pages = sorted((WORK_EN_ANS / paper / "pages").glob("page-*.png"))
    if not pages:
        raise FileNotFoundError(f"{paper}: run build/en_unpack.py first")

    scratch = WORK_EN_ANS / paper / "cell.png"
    found: dict[int, int] = {}
    sections: list[str] = []
    problems: list[str] = []
    for page in pages:
        answers, names, page_problems = read_grid(page, expected, scratch)
        found.update(answers)
        sections.extend(names)
        problems.extend(page_problems)
    scratch.unlink(missing_ok=True)
    return found, sections, problems, "ruled grid on the scan"


def _read_from_text(paper: str, expected: set[int]
                    ) -> tuple[dict[int, int], list[str], list[str], str]:
    """The key read straight from a typed PDF's own text layer.

    Two of the three schools ingested alongside Nanyang printed their key as a
    typed document rather than a scan (`en_key_text.has_native_text`), which
    makes the text layer a better source than any image ever could be --
    CLAUDE.md 1.1's argument for Science's genuine text-layer papers, with the
    OCR-garbling risk removed entirely because there is no OCR here.
    """
    pdf = en_corpus.part_path(paper, "Answers")
    pairs = en_key_text.read_key(pdf)
    found: dict[int, int] = {}
    problems: list[str] = []
    for number in sorted(expected):
        value = pairs.get(number)
        if value is None:
            continue
        if value.isdigit() and int(value) in VALID_OPTIONS:
            found[number] = int(value)
        else:
            problems.append(f"Q{number}: the key's text layer reads {value!r}, "
                            f"not a single option digit 1-4")
    return found, [], problems, "PDF text layer (typed, not scanned)"


def extract(paper: str, school: str | None = None) -> dict:
    """The Booklet A key for one paper, checked against the booklet's questions.

    Run after en_index.py for the reason CLAUDE.md 1.6.1 and 7.7 both give: a key
    that is short at the *end* leaves no gap in its own sequence for anyone to
    notice, so only the booklet's own question count reveals it.
    """
    wanted = booklet_questions(paper)
    expected = set(wanted)

    ans_pdf = en_corpus.part_path(paper, "Answers")
    if ans_pdf.exists() and en_key_text.has_native_text(ans_pdf):
        found, sections, problems, source = _read_from_text(paper, expected)
    else:
        found, sections, problems, source = _read_from_grid(paper, expected)

    verified = verified_key(paper)
    if verified:
        disagreed = sorted(q for q, a in found.items()
                           if q in verified and verified[q] != a)
        if disagreed:
            # Refuse. One of the two readings is wrong and there is nothing here
            # that says which, so nothing is marked against either.
            problems.append(
                f"review/en-mcq-key.json disagrees with the scan on "
                f"{['Q%d' % q for q in disagreed]}: recorded "
                f"{[verified[q] for q in disagreed]} against "
                f"{[found[q] for q in disagreed]} read off the page")
            found = {}
        else:
            filled = sorted(set(verified) - set(found))
            found = {**found, **verified}
            source = (f"{source}, confirmed by review/en-mcq-key.json"
                      + (f" (which supplied {['Q%d' % q for q in filled]})"
                         if filled else ""))

    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    warnings = list(problems)
    if missing:
        warnings.append(f"no answer read for {missing}; read them off "
                        f"work-en-ans/{paper}/pages/ and add them to "
                        f"review/en-mcq-key.json")
    if extra:
        warnings.append(f"the key answers {extra}, which Booklet A does not ask")

    return {
        "paper": paper,
        "school": school,
        "subject": "english",
        "source": f"{school or paper} answer key",
        "read_from": source,
        # A school's own key, not a marking scheme -- the same caveat CLAUDE.md
        # 1.6 records for EPH's suggested answers.
        "authoritative": False,
        "sections": sections,
        "num_questions": len(found),
        "booklet_questions": len(expected),
        "answers": [{"question": q, "answer": found[q]} for q in sorted(found)],
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*")
    args = parser.parse_args(argv)

    registry = {p["paper"]: p for p in en_corpus.load_registry()}
    papers = args.papers or sorted(
        path.name for path in WORK_EN_ANS.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()) \
        if WORK_EN_ANS.exists() else []
    if not papers:
        print("nothing rendered; run build/en_unpack.py first", file=sys.stderr)
        return 1

    exit_code = 0
    for paper in papers:
        result = extract(paper, (registry.get(paper) or {}).get("school"))
        out = WORK_EN_ANS / paper / "mcq-answers.json"
        out.write_text(json.dumps(result, indent=2))
        print(f"{paper}: {result['num_questions']}/{result['booklet_questions']} "
              f"answers [{result['read_from']}]")
        if result["sections"]:
            print(f"    sections: {', '.join(result['sections'])}")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
