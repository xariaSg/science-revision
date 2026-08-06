"""Render every page of a paper as one labelled grid so detected boundaries can be
eyeballed in a single image.

Each thumbnail is bordered by the section it was assigned to. The point is that a
wrong boundary is obvious at a glance -- a question page sitting in the answers
block, or an answer page sitting in Booklet B, shows up as a colour that breaks the
run, without anyone reading a JSON file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"

THUMB_WIDTH = 220
COLUMNS = 9
PAD = 10
LABEL_H = 22
BORDER = 4

SECTION_COLOURS = {
    "A": (52, 120, 205),        # blue
    "B": (34, 150, 83),         # green  -- the booklet that matters
    "answers": (214, 130, 24),  # amber
    "blank": (150, 150, 150),   # grey
    "?": (200, 40, 40),         # red -- assigned to no section
}


def _font(size: int = 14) -> ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def section_of(page: int, bounds: dict) -> str:
    if page in bounds.get("blank_pages", []):
        return "blank"
    a, b, ans = bounds["booklet_a"], bounds["booklet_b"], bounds["answers"]
    if a["start"] <= page <= a["end"]:
        return "A"
    if b["start"] <= page <= b["end"]:
        return "B"
    if ans and ans["start"] <= page <= ans["end"]:
        return "answers"
    return "?"


def build(work: Path, columns: int = COLUMNS, thumb_width: int = THUMB_WIDTH) -> Path:
    manifest = json.loads((work / "manifest.json").read_text())
    bounds = json.loads((work / "boundaries.json").read_text())
    num_pages = manifest["num_pages"]

    with Image.open(work / "pages" / "page-001.png") as first:
        aspect = first.height / first.width
    thumb_height = int(thumb_width * aspect)

    cell_w = thumb_width + 2 * BORDER
    cell_h = thumb_height + 2 * BORDER + LABEL_H
    rows = -(-num_pages // columns)

    header_h = 46
    sheet = Image.new(
        "RGB",
        (columns * (cell_w + PAD) + PAD, header_h + rows * (cell_h + PAD) + PAD),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    label_font, head_font = _font(13), _font(18)

    ans = bounds["answers"]
    ans_txt = f"{ans['start']}-{ans['end']}" if ans else "none"
    draw.text(
        (PAD, 10),
        f"{bounds['year']}   A {bounds['booklet_a']['start']}-{bounds['booklet_a']['end']}   "
        f"B {bounds['booklet_b']['start']}-{bounds['booklet_b']['end']}   "
        f"answers {ans_txt}   confidence: {bounds['confidence']}",
        fill="black", font=head_font,
    )

    for index in range(num_pages):
        page = index + 1
        col, row = index % columns, index // columns
        x = PAD + col * (cell_w + PAD)
        y = header_h + row * (cell_h + PAD)

        section = section_of(page, bounds)
        colour = SECTION_COLOURS[section]

        draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], fill=colour)
        with Image.open(work / "pages" / f"page-{page:03d}.png") as img:
            thumb = img.convert("RGB").resize((thumb_width, thumb_height), Image.LANCZOS)
        sheet.paste(thumb, (x + BORDER, y + BORDER))

        draw.text((x + BORDER + 2, y + BORDER + thumb_height + 4),
                  f"p{page}  {section}", fill="white", font=label_font)

    out = work / "contact-sheet.png"
    sheet.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_DIR)
    parser.add_argument("--columns", type=int, default=COLUMNS)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    if not years:
        print(f"nothing unpacked under {args.work}; run unpack.py first", file=sys.stderr)
        return 1

    for year in years:
        work = args.work / str(year)
        if not (work / "boundaries.json").exists():
            print(f"{year}: no boundaries.json; run detect_boundaries.py first",
                  file=sys.stderr)
            return 1
        print(f"{year}: {build(work, args.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
