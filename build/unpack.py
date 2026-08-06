"""Render a PSLE paper PDF to page images in a working directory.

The papers are scanned PDFs: one full-page raster per page at 200-300 DPI. A few
(2020, 2023) split a page across many image XObjects, so we render the composed
page rather than pulling embedded images out. Rendering at a fixed DPI also gives
every paper the same coordinate space, which segmentation depends on.

Five papers (2015, 2017, 2018, 2019 and partly 2023) carry an OCR text layer from
whoever produced the scan. That is a better source than re-OCRing, so the manifest
records per-page character counts and unpack reports which papers have one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # PyMuPDF

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers"
WORK_DIR = REPO / "work"

DEFAULT_DPI = 300

# "2024 PSLE Science.pdf" / "2015 PSLE Science.PDF"
PAPER_RE = re.compile(r"^(?P<year>\d{4})\s+PSLE\s+Science\.pdf$", re.IGNORECASE)


@dataclass
class Page:
    page_number: int
    image: str
    width: int
    height: int
    text_chars: int


def discover_papers(papers_dir: Path = PAPERS_DIR) -> dict[int, Path]:
    """Map year -> path. Extensions are mixed case, so match case-insensitively."""
    found: dict[int, Path] = {}
    for path in sorted(papers_dir.iterdir()):
        m = PAPER_RE.match(path.name)
        if not m:
            continue
        year = int(m.group("year"))
        if year in found:
            raise ValueError(f"two papers claim year {year}: {found[year]} and {path}")
        found[year] = path
    return found


def unpack(src: Path, year: int, out_dir: Path, dpi: int = DEFAULT_DPI,
           overwrite: bool = False) -> dict:
    """Render every page of `src` to PNG under `out_dir`, and write a manifest."""
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(src)
    if doc.page_count == 0:
        raise ValueError(f"{src.name} has no pages")

    pages: list[Page] = []
    for index, page in enumerate(doc):
        number = index + 1
        rel = f"pages/page-{number:03d}.png"
        target = out_dir / rel
        if overwrite or not target.exists():
            pix = page.get_pixmap(dpi=dpi)
            pix.save(target)
            width, height = pix.width, pix.height
        else:
            # Trust an existing render; read its size back rather than redoing the work.
            with fitz.open(target) as existing:
                rect = existing[0].rect
                width, height = int(rect.width), int(rect.height)
        pages.append(Page(number, rel, width, height, len(page.get_text().strip())))

    manifest = {
        "year": year,
        "source": str(src.relative_to(REPO)),
        "dpi": dpi,
        "num_pages": doc.page_count,
        "text_layer_chars": sum(p.text_chars for p in pages),
        "pages": [asdict(p) for p in pages],
    }
    doc.close()

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int,
                        help="years to unpack (default: all found)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--out", type=Path, default=WORK_DIR)
    parser.add_argument("--overwrite", action="store_true",
                        help="re-render pages that already exist")
    args = parser.parse_args(argv)

    papers = discover_papers()
    if not papers:
        print(f"no papers found in {PAPERS_DIR}", file=sys.stderr)
        return 1

    years = args.years or sorted(papers)
    missing = [y for y in years if y not in papers]
    if missing:
        print(f"no paper for year(s): {missing}. have: {sorted(papers)}", file=sys.stderr)
        return 1

    with_text: list[int] = []
    for year in years:
        manifest = unpack(papers[year], year, args.out / str(year),
                          dpi=args.dpi, overwrite=args.overwrite)
        chars = manifest["text_layer_chars"]
        note = f"  [text layer: {chars:,} chars]" if chars else ""
        print(f"{year}: {manifest['num_pages']} pages @ {args.dpi} dpi "
              f"-> {args.out / str(year)}{note}")
        if chars:
            with_text.append(year)

    if with_text:
        print(f"\nNOTE: {with_text} ship an embedded text layer. Prefer it over OCR "
              f"where it is clean — check it before re-OCRing those papers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
