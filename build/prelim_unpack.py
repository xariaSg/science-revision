"""Render each ingested prelim's three PDFs to page images.

The destinations are the ones the PSLE pipeline already uses, keyed on the paper id
instead of the year:

    work-a/<paper>/pages/     Booklet A, the MCQ question pages
    work-b/<paper>/pages/     Booklet B, the open-ended question pages
    work-ans/<paper>/pages/   the school's suggested answers

work-ans is a separate root from the two question roots for the reason CLAUDE.md
section 7.1 gives for Chinese: no route reads it, so there is no URL that reaches
the answers. Booklet B gets a boundaries.json covering the whole file, because the
source *is* Booklet B and there is nothing to detect.

Two things differ from the PSLE papers and both are handled here rather than
downstream:

* **The answer PDFs often carry a real text layer.** Seven of the fourteen were
  typed rather than scanned, so their key can be read exactly instead of OCRed.
  The manifest records the per-page character count, and the extractor prefers it.
* **Every page carries an `www.sgexam.com` watermark** in the text layer of the
  question papers, and nowhere else. It is the *only* text on those pages, so a
  page whose character count is that watermark alone has no usable text layer at
  all -- counting it as one would send the extractor down a path with no content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

import prelims
from unpack import DEFAULT_DPI, unpack, write_booklet_b_boundaries

REPO = Path(__file__).resolve().parent.parent
WORK_A = REPO / "work-a"
WORK_B = REPO / "work-b"
WORK_ANS = REPO / "work-ans"

# The scan host's watermark, stamped on every page of every question paper and on
# some answer papers. Text-layer character counts are measured with it removed.
WATERMARK_RE = re.compile(r"www\.sgexam\.com", re.I)

# Where each part is rendered, and under which filename stem. The stems differ
# because the OCR cache is keyed on them, and two directories of "page-001.png"
# would otherwise collide in one cache (CLAUDE.md section 7.1).
TARGETS = {
    "MCQ": (WORK_A, "page"),
    "OEQ": (WORK_B, "page"),
    "Answers": (WORK_ANS, "answer"),
}


def text_layer_chars(src: Path) -> int:
    """Characters of real text in a PDF, discounting the watermark.

    A question paper comes back as ~500 characters of pure watermark, which reads
    as "has a text layer" to any count that does not strip it first.
    """
    with fitz.open(src) as doc:
        return sum(len(WATERMARK_RE.sub("", page.get_text()).strip()) for page in doc)


def rename_pages(out_dir: Path, stem: str) -> None:
    """Rename page-NNN.png to <stem>-NNN.png where the stem is not "page"."""
    if stem == "page":
        return
    pages = out_dir / "pages"
    for path in sorted(pages.glob("page-*.png")):
        path.rename(pages / f"{stem}-{path.name.split('-', 1)[1]}")


def unpack_paper(paper: dict, dpi: int = DEFAULT_DPI,
                 overwrite: bool = False) -> dict:
    out: dict[str, dict] = {}
    for part, (root, stem) in TARGETS.items():
        src = prelims.part_path(paper["paper"], part)
        if not src.exists():
            raise FileNotFoundError(f"{paper['paper']}: {part} not ingested ({src})")
        out_dir = root / paper["paper"]
        manifest = unpack(src, paper["paper"], out_dir, dpi=dpi,
                          overwrite=overwrite, year=paper["year"])
        rename_pages(out_dir, stem)
        # The count unpack() recorded includes the watermark; replace it with the
        # count that says whether there is anything worth reading.
        manifest["text_layer_chars"] = text_layer_chars(src)
        manifest["school"] = paper["school"]
        manifest["part"] = part
        if stem != "page":
            for page in manifest["pages"]:
                page["image"] = page["image"].replace("pages/page-", f"pages/{stem}-")
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        if part == "OEQ":
            write_booklet_b_boundaries(out_dir, manifest)
        out[part] = manifest
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*",
                        help="paper ids to unpack (default: all in the registry)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    registry = prelims.load_registry()
    if not registry:
        print("nothing ingested; run build/prelims.py first", file=sys.stderr)
        return 1
    wanted = args.papers or [p["paper"] for p in registry]
    known = {p["paper"]: p for p in registry}
    missing = [p for p in wanted if p not in known]
    if missing:
        print(f"not in the registry: {missing}", file=sys.stderr)
        return 1

    typed: list[str] = []
    for paper_id in wanted:
        paper = known[paper_id]
        parts = unpack_paper(paper, dpi=args.dpi, overwrite=args.overwrite)
        counts = " ".join(f"{part}={parts[part]['num_pages']:2d}pp" for part in TARGETS)
        chars = parts["Answers"]["text_layer_chars"]
        note = f"  [answers text layer: {chars:,} chars]" if chars else ""
        print(f"{paper['school']:16s} {counts}{note}")
        if chars:
            typed.append(paper["school"])

    print(f"\n{len(wanted)} papers rendered @ {args.dpi} dpi")
    if typed:
        print(f"{len(typed)} answer papers were typed, not scanned, and can be read "
              f"exactly rather than OCRed: {', '.join(typed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
