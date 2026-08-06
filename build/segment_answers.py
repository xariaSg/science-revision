"""Segment the answer pages into per-question, per-sub-part regions.

Booklet B answers do not occupy whole pages. They begin partway down a column,
under a "Booklet B" header, on a page whose other half still holds Booklet A's MCQ
answers -- so a page range is not enough to locate them. This cuts the answer pages
into regions keyed to question and sub-part, and crops each one.

Three properties of the EPH answer layout carry the work:

* Two columns split near mid-page, left read before right (2024 p31 runs 21-26 in
  the left column, 27-30 in the right).
* Indentation encodes role. Within a column, question numbers sit at the left edge,
  sub-part labels one indent in, body text further right again.
* A "Booklet B" header marks where Booklet B's answers start.

This works on word boxes rather than tesseract's blocks, because tesseract merges
lines across the gutter: one block on 2024 p31 reads "Chemical potential energy in
the 29. (a) Roots absorb water..." -- the tail of a left-column line fused to the
head of a right-column one. Blocks cannot be trusted; individual word x-positions
can.

The OCR text captured here is a *draft* for review only. It carries real errors
("predotors", "Explanation:" clipped to "ion:") and must not feed rubric generation
directly -- that is the vision pass in extract.py. What this step is responsible for
is the segmentation and the keying.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytesseract
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"

MIN_CONF = 30
# Fraction of a column's width within which a leading token is treated as a marker
# rather than as body text.
MARKER_ZONE = 0.30
CROP_PAD = 12

# Question numbers terminate in "." (or "," -- OCR reads 2024's "21." as "21,").
# A colon is deliberately NOT accepted: 2025's Q37 answer is a procedure written as
# "Step 1:", "Step 2:" ..., and accepting ":" turned those into questions 1-6.
QUESTION_RE = re.compile(r"^(\d{1,2})\s*[.,]$")
HAS_LETTER_RE = re.compile(r"[^\W\d_]")
QUESTION_RANGE_RE = re.compile(r"For\s+questions?\s+(\d{1,2})\s+to\s+(\d{1,2})", re.I)
# Sub-parts are letters (a)-(h) and romans (i)-(v). Digits are excluded on purpose:
# "(1)" ... "(4)" are Booklet A's MCQ answer values and sit in the body zone.
# "@" is here because tesseract reads "(a)" as "@)" often enough to matter; it is
# recorded as low-confidence so review can catch a wrong guess.
SUBPART_RE = re.compile(r"^\(?\s*(@|i{1,3}|iv|v|[a-h])\s*[.)]$", re.I)
ROMAN_PARTS = {"i", "ii", "iii", "iv", "v"}
BOOKLET_HDR_RE = re.compile(r"^Booklet$", re.I)

# The dotted rule between the two columns OCRs as isolated punctuation, and lands
# to the LEFT of the question numbers -- on 2024 p34 the line holding "39." starts
# with a ":" at x=1256. Dropping these before anything else looks at a line's first
# token is what keeps the column's left edge and the marker tests honest.
SEPARATOR_RE = re.compile(r"^[^\w]{1,2}$")
# How many leading tokens may precede a question number on its line. Covers a stray
# speck the separator filter misses (2024 p33: "7 36. (a) 50 mm").
MARKER_LOOKAHEAD = 3
# Narrowest vertical whitespace accepted as the inter-column gutter, in pixels at
# 300 dpi. 2025 p34's real gutter is only ~20px.
MIN_GUTTER = 4
# Page margins, as a fraction of page height. Everything outside is furniture -- the
# "PSLE Yearly Science - Answers" running header, the EPH copyright footer, and the
# printed page number -- never answer content. Body text reaches y/H = 0.92.
MARGIN_TOP, MARGIN_BOTTOM = 0.055, 0.94


@dataclass
class Word:
    text: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class Region:
    """One contiguous run of a sub-part's answer, inside a single column."""
    page: int
    column: int
    top: int
    bottom: int
    left: int
    right: int
    lines: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"page": self.page, "column": self.column,
                "bbox": [self.left, self.top, self.right, self.bottom]}


def page_words(work: Path, page: int) -> tuple[list[Word], int, int]:
    with Image.open(work / "pages" / f"page-{page:03d}.png") as img:
        width, height = img.size
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < MIN_CONF:
            continue
        left, top = data["left"][i], data["top"][i]
        words.append(Word(text.strip(), left, top,
                          left + data["width"][i], top + data["height"][i]))
    return words, width, height


def find_gutter(words: list[Word], width: int, height: int) -> int:
    """Find the vertical whitespace band separating the two columns.

    Takes the empty band whose centre is nearest the page centre. Neither "widest"
    nor "first" works: each column is itself split into a narrow label sub-column
    (question numbers, sub-part labels) and a wider body sub-column, so a page has
    several empty bands. On 2025 p34 the widest is [1330..1377] -- the right
    column's own label/body gap, which puts that column's "40." in the left column.
    The first is whatever gap follows a short left column. Only the true gutter is
    reliably near the middle of a two-column page.

    Callers must strip separator specks first; the dotted rule between columns sits
    inside the real gutter and will otherwise hide it.
    """
    lo, hi = int(width * 0.35), int(width * 0.65)
    coverage = [0] * (hi - lo)
    for w in words:
        for x in range(max(lo, w.left), min(hi, w.right)):
            coverage[x - lo] += 1

    centre = width // 2
    bands: list[int] = []
    run_start = None
    for index, ink in enumerate(coverage + [1]):
        if ink == 0:
            if run_start is None:
                run_start = index
        else:
            if run_start is not None and index - run_start >= MIN_GUTTER:
                bands.append(lo + (run_start + index) // 2)
            run_start = None
    if not bands:
        return centre
    return min(bands, key=lambda x: abs(x - centre))


def group_lines(words: list[Word]) -> list[list[Word]]:
    """Cluster words into lines by vertical overlap, then sort each line by x."""
    if not words:
        return []
    heights = sorted(w.bottom - w.top for w in words)
    tol = max(8, heights[len(heights) // 2] * 0.6)
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: w.cy):
        if lines and abs(w.cy - lines[-1][0].cy) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w.left) for line in lines]


def _column_left(words: list[Word]) -> int:
    """Left edge of a column, ignoring stray specks from the dotted separator."""
    xs = sorted(w.left for w in words)
    return xs[max(0, int(len(xs) * 0.02))]


def scan_column(work: Path, page: int, column: int, words: list[Word],
                out: dict) -> None:
    """Walk one column top-to-bottom, splitting it at question and sub-part markers.

    `out` accumulates across columns and pages, because a sub-part's answer runs on
    past a column break and must keep collecting into the region it started in.
    """
    if not words:
        return
    col_left = _column_left(words)
    col_right = max(w.right for w in words)
    marker_limit = col_left + (col_right - col_left) * MARKER_ZONE

    for line in group_lines(words):
        head = line[0]

        if head.left <= marker_limit and BOOKLET_HDR_RE.match(head.text) and len(line) > 1:
            label = line[1].text.strip().upper().rstrip(".:")
            if label in {"A", "B"}:
                out["current_booklet"] = label
                if label == "B":
                    out["booklet_b_start"] = {"page": page, "column": column,
                                              "y": head.top}
                out["region"] = None
                continue

        consumed = 0
        for index, token in enumerate(line[:MARKER_LOOKAHEAD]):
            if token.left > marker_limit:
                break
            qmatch = QUESTION_RE.match(token.text)
            if not qmatch and HAS_LETTER_RE.search(token.text):
                # Only specks may precede a question number. Stopping at the first
                # real word keeps "Step 2:" style body text from being read as one.
                break
            if qmatch:
                out["question"] = int(qmatch.group(1))
                out["part"] = None
                out["subpart"] = None
                out["region"] = None
                consumed = index + 1
                break

        # Sub-part labels may sit on the question number's line ("30. (a)") or open
        # their own. Letters set the part; romans nest inside the current part, so
        # 29(b)(ii) stays distinct from 29(b).
        while consumed < len(line) and out["question"] is not None:
            token = line[consumed]
            match = SUBPART_RE.match(token.text) if token.left <= marker_limit else None
            if not match:
                break
            label = match.group(1).lower()
            if label == "@":
                label = "a"
                out["low_confidence"].add((out["question"], "a"))
            if label in ROMAN_PARTS:
                out["subpart"] = label
            else:
                out["part"] = label
                out["subpart"] = None
            out["region"] = None
            consumed += 1

        if out["question"] is None or out["current_booklet"] != "B":
            continue

        body = line[consumed:]
        if not body and out["region"] is None:
            # A bare marker line; the region opens on the next line of text.
            continue

        part = out["part"]
        if out["subpart"]:
            part = f"{part}({out['subpart']})" if part else f"({out['subpart']})"
        key = (out["question"], part)
        if out["region"] is None:
            region = Region(page=page, column=column, top=head.top,
                            bottom=head.bottom, left=col_left, right=col_right)
            out["regions"].setdefault(key, []).append(region)
            out["sequence"].append(key)
            out["region"] = region
        region = out["region"]
        region.bottom = max(region.bottom, max(w.bottom for w in line))
        if body:
            region.lines.append(" ".join(w.text for w in body))


def expected_question_range(work: Path, bounds: dict) -> tuple[int, int] | None:
    """Read "For questions 29 to 40..." off Booklet B's instruction page.

    Booklet B states the range it covers, which turns "did we get every answer?"
    into a checkable question instead of an assumption.
    """
    booklet_b = bounds["booklet_b"]
    for page in range(booklet_b["start"], min(booklet_b["start"] + 3,
                                              booklet_b["end"] + 1)):
        cached = work / "ocr" / f"page-{page:03d}.txt"
        if not cached.exists():
            continue
        match = QUESTION_RANGE_RE.search(re.sub(r"\s+", " ", cached.read_text()))
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def segment(work: Path) -> dict:
    bounds = json.loads((work / "boundaries.json").read_text())
    answers = bounds["answers"]
    if not answers:
        raise ValueError(f"{work.name}: boundaries.json has no answers range")
    expected = expected_question_range(work, bounds)

    out: dict = {"question": None, "part": None, "subpart": None, "region": None,
                 "current_booklet": None, "booklet_b_start": None, "regions": {},
                 "low_confidence": set(), "sequence": []}
    page_sizes: dict[int, tuple[int, int]] = {}

    for page in range(answers["start"], answers["end"] + 1):
        words, width, height = page_words(work, page)
        page_sizes[page] = (width, height)
        # Drop the dotted inter-column rule and the page furniture before anything
        # measures geometry: a single token left in the gutter fills the whitespace
        # band and hides it, and 2025 p34 centres its page number "13" at
        # x[1205..1263] -- inside a gutter that is otherwise clear.
        words = [w for w in words
                 if not SEPARATOR_RE.match(w.text)
                 and MARGIN_TOP * height <= w.cy <= MARGIN_BOTTOM * height]
        gutter = find_gutter(words, width, height)
        # Reading order is left column then right column.
        for column, subset in enumerate(
                ([w for w in words if w.cx < gutter],
                 [w for w in words if w.cx >= gutter])):
            out["region"] = None  # a column break always ends the open region
            scan_column(work, page, column, subset, out)

    warnings: list[str] = []
    if out["booklet_b_start"] is None:
        warnings.append("no 'Booklet B' header found in the answer pages")

    questions: dict[int, dict] = {}
    for (question, part), regions in sorted(out["regions"].items(),
                                            key=lambda kv: (kv[0][0], kv[0][1] or "")):
        entry = questions.setdefault(question, {"question": question, "parts": []})
        text = " ".join(l for r in regions for l in r.lines)
        entry["parts"].append({
            "part": part,
            "regions": [r.as_dict() for r in regions],
            "ocr_draft": re.sub(r"\s+", " ", text).strip(),
            "low_confidence_label": (question, part) in out["low_confidence"],
        })

    numbers = sorted(questions)
    if not numbers:
        warnings.append("no Booklet B answers segmented at all")
    elif expected:
        missing = [n for n in range(expected[0], expected[1] + 1) if n not in questions]
        if missing:
            warnings.append(f"Booklet B covers Q{expected[0]}-Q{expected[1]} but no "
                            f"answer was segmented for {missing}")
        stray = [n for n in numbers if not expected[0] <= n <= expected[1]]
        if stray:
            warnings.append(f"segmented answers outside Q{expected[0]}-Q{expected[1]}: "
                            f"{stray} (likely body text misread as a question number)")
    else:
        warnings.append("could not read Booklet B's question range; coverage unchecked")
        gaps = [n for n in range(numbers[0], numbers[-1] + 1) if n not in questions]
        if gaps:
            warnings.append(f"no answer segmented for question(s) {gaps}")

    for question in questions.values():
        if any(p["part"] is None for p in question["parts"]) and len(question["parts"]) > 1:
            warnings.append(f"Q{question['question']}: text found before any "
                            f"sub-part label")

    # If OCR drops a question number, that question's sub-parts are absorbed by the
    # previous question and nothing else notices -- the answers end up keyed to the
    # wrong question, which is the worst failure this pipeline can produce. It shows
    # up as part labels running backwards: 30(a), 30(b), then 30(a) again.
    seen_order: dict[int, list[str]] = {}
    for question, part in out["sequence"]:
        seen_order.setdefault(question, [])
        if part is not None and part not in seen_order[question]:
            seen_order[question].append(part)
    for question, parts in seen_order.items():
        if parts != sorted(parts):
            warnings.append(
                f"Q{question}: sub-part labels are out of order {parts} -- a question "
                f"number was probably missed and its answers merged into Q{question}")

    return {
        "year": bounds["year"],
        "answers_pages": [answers["start"], answers["end"]],
        "expected_questions": list(expected) if expected else None,
        "booklet_b_start": out["booklet_b_start"],
        "needs_review": bool(warnings),
        "questions": [questions[n] for n in numbers],
        "page_sizes": {str(k): v for k, v in page_sizes.items()},
        "warnings": warnings,
        "source": "EPH suggested answer",
        "ocr_draft_only": True,
    }


def write_crops(work: Path, result: dict) -> int:
    crops_dir = work / "answers" / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    # Clear first: a re-run with different segmentation would otherwise leave crops
    # for sub-parts that no longer exist sitting next to the current ones.
    for stale in crops_dir.glob("*.png"):
        stale.unlink()
    cache: dict[int, Image.Image] = {}
    count = 0
    for question in result["questions"]:
        for part in question["parts"]:
            names = []
            for index, region in enumerate(part["regions"], start=1):
                page = region["page"]
                if page not in cache:
                    cache[page] = Image.open(
                        work / "pages" / f"page-{page:03d}.png").convert("RGB")
                img = cache[page]
                x0, y0, x1, y1 = region["bbox"]
                box = (max(0, x0 - CROP_PAD), max(0, y0 - CROP_PAD),
                       min(img.width, x1 + CROP_PAD), min(img.height, y1 + CROP_PAD))
                label = f"{question['question']}{part['part'] or ''}"
                suffix = f"-{index}" if len(part["regions"]) > 1 else ""
                name = f"Q{label}{suffix}.png"
                img.crop(box).save(crops_dir / name)
                names.append(f"crops/{name}")
                count += 1
            part["crops"] = names
    for img in cache.values():
        img.close()
    return count


def write_overlays(work: Path, result: dict) -> None:
    """Draw the detected regions back onto the answer pages for human review."""
    overlay_dir = work / "answers"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    by_page: dict[int, list[tuple[str, list[int]]]] = {}
    for question in result["questions"]:
        for part in question["parts"]:
            for region in part["regions"]:
                label = f"{question['question']}{part['part'] or ''}"
                by_page.setdefault(region["page"], []).append((label, region["bbox"]))

    for page, items in by_page.items():
        with Image.open(work / "pages" / f"page-{page:03d}.png") as src:
            img = src.convert("RGB")
        draw = ImageDraw.Draw(img)
        for label, (x0, y0, x1, y1) in items:
            draw.rectangle([x0, y0, x1, y1], outline=(200, 30, 30), width=5)
            draw.text((x0 + 8, y0 + 8), label, fill=(200, 30, 30))
        img.save(overlay_dir / f"overlay-page-{page:03d}.png")
        img.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_DIR)
    parser.add_argument("--no-crops", action="store_true")
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    if not years:
        print(f"nothing unpacked under {args.work}; run unpack.py first", file=sys.stderr)
        return 1

    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = segment(work)
        if not args.no_crops:
            write_crops(work, result)
            write_overlays(work, result)
        (work / "answers").mkdir(parents=True, exist_ok=True)
        (work / "answers" / "segments.json").write_text(json.dumps(result, indent=2))

        numbers = [q["question"] for q in result["questions"]]
        parts = sum(len(q["parts"]) for q in result["questions"])
        span = f"Q{numbers[0]}-Q{numbers[-1]}" if numbers else "none"
        print(f"{year}: {len(numbers)} questions ({span}), {parts} sub-parts")
        for question in result["questions"]:
            labels = ", ".join(p["part"] or "-" for p in question["parts"])
            print(f"    Q{question['question']:<3} [{labels}]")
        for warning in result["warnings"]:
            print(f"    WARN {warning}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
