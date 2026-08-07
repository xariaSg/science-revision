"""Render a PSLE Chinese Paper 2 and its answer key to page images.

Chinese differs from Science in one structural way that shapes everything
downstream: Paper 2 is a single booklet, not two. There is no Booklet A/B split
to detect, so the question paper needs no boundary search -- the whole file is
the paper. The answer key is a separate file and is unpacked to its own
directory, so the API can serve question pages without the answers ever sitting
in a servable path (CLAUDE.md section 2.1).

Both files are pure scans with no text layer -- unlike Science, where five papers
shipped a usable one. The Chinese papers' embedded text, where present at all, is
a Latin-only OCR pass that renders every Chinese character as garbage
("011-411,4*-=---"), so it is never read. macOS Vision with zh-Hans is the only
source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers" / "chinese"
WORK_DIR = REPO / "work-cn"

DEFAULT_DPI = 300

PAPER_RE = re.compile(r"^(?P<year>\d{4})\s+PSLE\s+Chinese\s+Language(?:\.PDF)?\.pdf$",
                      re.IGNORECASE)

# The question paper and the key, kept apart on disk for the whole pipeline.
PAPER = "Paper2"
ANSWER = "Answer"


@dataclass
class Page:
    page_number: int
    image: str
    width: int
    height: int


def discover(kind: str, papers_dir: Path = PAPERS_DIR) -> dict[int, Path]:
    """Map year -> path. Extensions are mixed case across the corpus."""
    found: dict[int, Path] = {}
    root = papers_dir / kind
    if not root.exists():
        return found
    for path in sorted(root.iterdir()):
        match = PAPER_RE.match(path.name)
        if match:
            found[int(match.group("year"))] = path
    return found


def render(pdf: Path, out_dir: Path, dpi: int = DEFAULT_DPI,
           stem: str = "page") -> list[Page]:
    """Render every page. The stem differs between the paper and the key because
    the OCR cache is keyed on the image's filename, and two directories of
    page-001.png would otherwise share one cache entry."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    pages: list[Page] = []
    for index in range(doc.page_count):
        number = index + 1
        image = out_dir / f"{stem}-{number:03d}.png"
        pixmap = doc[index].get_pixmap(dpi=dpi)
        pixmap.save(image)
        pages.append(Page(number, image.name, pixmap.width, pixmap.height))
    return pages


def unpack_year(year: int, dpi: int = DEFAULT_DPI,
                work_dir: Path = WORK_DIR) -> dict:
    papers = discover(PAPER)
    answers = discover(ANSWER)
    if year not in papers:
        raise SystemExit(f"no Chinese Paper 2 for {year} in {PAPERS_DIR / PAPER}")
    if year not in answers:
        raise SystemExit(f"no Chinese answer key for {year} in {PAPERS_DIR / ANSWER}")

    target = work_dir / str(year)
    paper_pages = render(papers[year], target / "pages", dpi)
    answer_pages = render(answers[year], target / "answer-pages", dpi, stem="answer")

    manifest = {
        "year": year,
        "subject": "chinese",
        "dpi": dpi,
        "paper": {
            "source": str(papers[year].relative_to(REPO)),
            "num_pages": len(paper_pages),
            "pages": [asdict(p) for p in paper_pages],
        },
        "answers": {
            "source": str(answers[year].relative_to(REPO)),
            "num_pages": len(answer_pages),
            "pages": [asdict(p) for p in answer_pages],
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int,
                        help="years to unpack (default: all found)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = parser.parse_args(argv)

    years = args.years or sorted(discover(PAPER))
    if not years:
        print(f"no Chinese papers found in {PAPERS_DIR / PAPER}", file=sys.stderr)
        return 1
    for year in years:
        manifest = unpack_year(year, args.dpi)
        print(f"{year}: {manifest['paper']['num_pages']} paper pages, "
              f"{manifest['answers']['num_pages']} answer pages @ {args.dpi} dpi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
