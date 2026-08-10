"""Split a PSLE Chinese compilation into Paper 2 and its answer key.

Each EPH compilation holds four things -- Paper 1 (作文), Paper 2, Paper 3 (听力,
with its transcript printed) and the answers to all three. Only Paper 2 and its
answers are wanted. This was a manual step outside the repo until eight years'
worth of hand-split files turned out to disagree with each other: 2017's Paper 2
held two pages (Booklet A's cover and Booklet B's last page), 2018's began at
Booklet B with Booklet A missing entirely, and 2016's ran to 28. A split that is
wrong in that way is not visibly wrong downstream -- it just indexes fewer
questions -- so it is done here instead, from the paper's own footers.

The anchor is the per-page paper code, printed in the footer of every content
page and read cleanly by an English-only OCR pass even though the body is
Chinese:

    0005/1        Paper 1
    0005/2(A)     Paper 2, Booklet A   -- Q1-Q25, answered on the OAS
    0005/2(B)     Paper 2, Booklet B   -- Q26-Q40, written in the booklet
    0005/3        Paper 3

Answers carry no code at all, which is what identifies them: they are the pages
after the last coded one. Covers and blank pages carry no code either, so runs
are filled forward rather than being required to be contiguous in the OCR.

Two eras, both handled without a per-year table:

* 2012-2016 -- Booklet B is 8 pages, Paper 3 is 20 (it prints a longer
  transcript).
* 2017-2020 -- Booklet B is 12 pages, Paper 3 is 12.

Booklet A is 12 pages in every year of the corpus, but that is an observation,
not an assumption: nothing here hardcodes it.

Each booklet cover states its own length ("This booklet consists of 8 printed
pages", "...9 printed pages and 3 blank pages") and that is used as a
cross-check. Unlike Science's Booklet A cover, which counts trailing blanks
inconsistently and cannot be trusted as a range (CLAUDE.md section 1.3), these
agree with the footer runs on every year -- but the footers still decide, and a
disagreement is reported rather than silently resolved.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ocr_vision import page_lines  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers" / "chinese"
COMPILATION = PAPERS_DIR / "Compilation"
WORK_DIR = REPO / "work-cn"

# The footer code is Latin and digits, so the cheap English pass reads it. Only
# the code is wanted here; the Chinese body is read later, at full resolution.
RECON_DPI = 150

COMPILATION_RE = re.compile(
    r"^(?P<year>\d{4})\s+PSLE\s+Chinese\s+Language\.(?:pdf|PDF)$")

# "0005/2(A)/2017", "0005/2(B)", "0005/1". The subject code is read rather than
# assumed -- it is 0005 across this corpus, but nothing depends on that.
#
# The booklet letter is matched against Cyrillic and Greek lookalikes as well as
# Latin: 2016 p23's footer comes back as "0005/2(В)/2016" with a Cyrillic Ve,
# which a plain [AB] misses, dropping the page's booklet and splitting the run in
# two. Safe for the same reason as the CONFUSABLE map in cn_index.py -- it only
# ever decides between A and B on a page already known to be Paper 2, and is
# never used to discover a code that was not read.
BOOKLET_LETTERS = "ABАВΑΒ"
CODE = re.compile(
    rf"\d{{4}}\s*/\s*(?P<paper>[123])\s*(?:\(\s*(?P<booklet>[{BOOKLET_LETTERS}])\s*\))?")
LATIN_BOOKLET = {"А": "A", "Α": "A", "В": "B", "Β": "B"}
# The cover of each booklet, which is a far better anchor than its own footer
# code: 2013 p17's code OCRs as "000512 (B)" with the slash gone, but every cover
# in the corpus names itself in clean Latin.
COVER = re.compile(r"CHINESE\s+PAPER\s+2\b", re.IGNORECASE)
COVER_BOOKLET = re.compile(rf"BOOKLET\s*\(?\s*([{BOOKLET_LETTERS}])\s*\)?", re.IGNORECASE)
BLANK_PAGE = re.compile(r"^\s*BLANK\s+PAGE\s*$", re.IGNORECASE | re.MULTILINE)
# "This booklet consists of 9 printed pages and 3 blank pages."
CONSISTS = re.compile(
    r"consists\s+of\s+(\d+)\s+printed\s+pages?(?:\s+and\s+(\d+)\s+blank\s+pages?)?",
    re.IGNORECASE)

PAPER2_A = "2A"
PAPER2_B = "2B"
ANSWERS = "answers"


@dataclass
class Split:
    year: int
    booklet_a: list[int]
    booklet_b: list[int]
    answers: list[int]
    notes: list[str]
    problems: list[str]

    @property
    def paper2(self) -> list[int]:
        return self.booklet_a + self.booklet_b


def discover(source: Path = COMPILATION) -> dict[int, Path]:
    found: dict[int, Path] = {}
    if not source.exists():
        return found
    for path in sorted(source.iterdir()):
        if m := COMPILATION_RE.match(path.name):
            found[int(m.group("year"))] = path
    return found


def _render_recon(pdf: Path, year: int, scratch: Path) -> list[Path]:
    """Render the whole compilation once, for the footer read."""
    out = scratch / str(year) / "pages"
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    images = [out / f"page-{i + 1:03d}.png" for i in range(doc.page_count)]
    for i, image in enumerate(images):
        if not image.exists():
            doc[i].get_pixmap(dpi=RECON_DPI).save(image)
    return images


@dataclass
class PageInfo:
    code: str | None            # "1", "2A", "2B", "3" -- from the footer
    cover: str | None           # "A"/"B" if this page is a Paper 2 booklet cover
    stated: tuple[int, int] | None   # (printed, blank) from a cover's own count
    blank: bool


def _label_pages(images: list[Path]) -> list[PageInfo]:
    """Read each page's footer code, whether it is a cover, and its own count."""
    info: list[PageInfo] = []
    for image in images:
        text = "\n".join(line.text for line in page_lines(image))

        code = None
        # A page can mention another paper's code in passing; the footer is the
        # last one on the page, so the last match wins.
        for m in CODE.finditer(text):
            paper, booklet = m.group("paper"), m.group("booklet")
            booklet = LATIN_BOOKLET.get(booklet, booklet) if booklet else None
            code = f"{paper}{booklet}" if booklet else paper

        cover = None
        if COVER.search(text) and (m := COVER_BOOKLET.search(text)):
            cover = LATIN_BOOKLET.get(m.group(1).upper(), m.group(1).upper())

        stated = None
        if c := CONSISTS.search(text):
            stated = (int(c.group(1)), int(c.group(2) or 0))

        info.append(PageInfo(code, cover, stated,
                             blank=bool(BLANK_PAGE.search(text))))
    return info


def _first(pages: list[PageInfo], predicate) -> int | None:
    """1-based page number of the first page satisfying predicate."""
    for number, page in enumerate(pages, start=1):
        if predicate(page):
            return number
    return None


def plan(year: int, pdf: Path, scratch: Path) -> Split:
    images = _render_recon(pdf, year, scratch)
    info = _label_pages(images)

    notes: list[str] = []
    problems: list[str] = []

    a_cover = _first(info, lambda p: p.cover == "A")
    b_cover = _first(info, lambda p: p.cover == "B")

    if a_cover is not None and b_cover is not None:
        # 2012-2020: two physical booklets, A (Q1-Q25, OAS) and B (Q26-Q40,
        # written in the booklet), each with its own cover and paper code.
        if b_cover <= a_cover:
            problems.append(
                f"Booklet B's cover (p{b_cover}) precedes A's (p{a_cover})")
            return Split(year, [], [], [], notes, problems)
        # Paper 3 opens where Paper 2 closes. Its cover carries no booklet, so it
        # is found by the footer code -- which reads cleanly on every year,
        # because only the A/B letter was ever the fragile part.
        paper3 = _first(info[b_cover:], lambda p: p.code == "3")
        if paper3 is None:
            problems.append("no Paper 3 page found after Booklet B's cover")
            return Split(year, [], [], [], notes, problems)
        paper3 += b_cover                  # back to a 1-based page number
        booklet_a = list(range(a_cover, b_cover))
        booklet_b = list(range(b_cover, paper3))
    elif a_cover is None and b_cover is None:
        # 2021-2025: one booklet, footer code "0005/2" with no letter. Take the
        # span between the first and last page carrying it, rather than the pages
        # that happen to have been read -- an interior page whose footer failed
        # would otherwise punch a hole in the paper.
        coded2 = [n for n, p in enumerate(info, start=1) if p.code == "2"]
        if not coded2:
            problems.append("no Paper 2 pages found (no 0005/2 footer, no cover)")
            return Split(year, [], [], [], notes, problems)
        booklet_a = list(range(min(coded2), max(coded2) + 1))
        booklet_b = []
    else:
        missing = "B" if b_cover is None else "A"
        problems.append(f"found one Paper 2 booklet cover but not {missing}'s")
        return Split(year, [], [], [], notes, problems)

    # The answers carry no code at all; they are what follows the last coded
    # page. A trailing BLANK PAGE closes Paper 3 on 2016 and carries no code
    # either, so it would otherwise open the answer range.
    coded = [n for n, p in enumerate(info, start=1) if p.code is not None]
    start = max(coded) + 1 if coded else len(info) + 1
    while start <= len(info) and info[start - 1].blank:
        start += 1
    answers = list(range(start, len(info) + 1))
    if not answers:
        problems.append("no answer pages found after the last coded page")

    booklets = (("A", booklet_a), ("B", booklet_b)) if booklet_b else \
               (("2", booklet_a),)
    for letter, pages in booklets:
        stated = info[pages[0] - 1].stated
        if stated is None:
            notes.append(f"Booklet {letter}: cover states no length")
            continue
        printed, blank = stated
        # The cover counts itself among the printed pages, exactly as Science's
        # does (CLAUDE.md section 1.3): "9 printed pages and 3 blank pages" is a
        # 12-page booklet, cover included.
        total = printed + blank
        if total != len(pages):
            problems.append(
                f"Booklet {letter}: cover states {printed} printed + {blank} "
                f"blank (= {total}), pages give {len(pages)}")
        else:
            notes.append(f"Booklet {letter}: {len(pages)} pages, cover agrees")

    return Split(year, booklet_a, booklet_b, answers, notes, problems)


def write_split(split: Split, pdf: Path, papers_dir: Path = PAPERS_DIR) -> dict:
    """Write Paper 2 (both booklets, in order) and the answers as separate PDFs."""
    source = fitz.open(pdf)
    name = f"{split.year} PSLE Chinese Language.pdf"
    written = {}
    for kind, pages in (("Paper2", split.paper2), ("Answer", split.answers)):
        out_dir = papers_dir / kind
        out_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        for page in pages:
            doc.insert_pdf(source, from_page=page - 1, to_page=page - 1)
        doc.save(out_dir / name)
        doc.close()
        written[kind] = len(pages)
    source.close()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int)
    parser.add_argument("--source", type=Path, default=COMPILATION)
    parser.add_argument("--scratch", type=Path,
                        default=WORK_DIR / ".compilation-recon")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the split without writing PDFs")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing Paper2/Answer pair")
    args = parser.parse_args(argv)

    found = discover(args.source)
    if not found:
        print(f"no compilations in {args.source}", file=sys.stderr)
        return 1
    years = args.years or sorted(found)

    failed = False
    for year in years:
        if year not in found:
            print(f"{year}: no compilation", file=sys.stderr)
            failed = True
            continue
        split = plan(year, found[year], args.scratch)
        a, b, ans = split.booklet_a, split.booklet_b, split.answers
        span = lambda p: f"p{p[0]}-{p[-1]}" if p else "none"  # noqa: E731
        print(f"{year}: Booklet A {span(a)} ({len(a)}p), "
              f"Booklet B {span(b)} ({len(b)}p), answers {span(ans)} ({len(ans)}p)")
        for note in split.notes:
            print(f"   {note}")
        for problem in split.problems:
            print(f"   ! {problem}")
            failed = True
        if split.problems or args.dry_run:
            continue
        # 2021-2025 were split by hand before this script existed and are already
        # built. Their splits agree with this one on every page that carries
        # content -- the only differences are a trailing BLANK PAGE and a couple
        # of Paper 1 answer pages -- so there is nothing to gain by redoing them
        # and a working build to lose. Overwriting takes an explicit --force.
        existing = PAPERS_DIR / "Paper2" / f"{year} PSLE Chinese Language.pdf"
        if existing.exists() and not args.force:
            print("   already split; leaving it alone (--force to overwrite)")
            continue
        written = write_split(split, found[year])
        print(f"   wrote Paper2 {written['Paper2']}p, Answer {written['Answer']}p")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
