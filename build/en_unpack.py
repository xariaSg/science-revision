"""Render each ingested English paper's three PDFs to page images.

    work-en-a/<paper>/pages/     Booklet A, the MCQ question pages
    work-en-b/<paper>/pages/     Booklet B, the written pages
    work-en-ans/<paper>/pages/   the school's answer key

Three roots rather than one for the reason CLAUDE.md section 7.1 gives for
Chinese and section 9 makes a build-time rule: no route reads `work-en-ans`, so
there is no URL that reaches the key. Keeping the answers in a directory of their
own means a later routing mistake cannot expose them, because they are not under
anything a route can reach.

Separate from Science's `work-a` / `work-b` / `work-ans` for a different reason:
`papers.discover(WORK_A)` is how the app finds Science's papers, and an English
paper rendered into that root would appear inside the Science subject with a
Science answer key looked up for it. The subjects share a paper *id* convention
(`2026-prelim-nanyang`) and nothing else.

Booklet A carries a `www.sgexam.com` watermark in its text layer and nothing
else, exactly as the Science prelims do (CLAUDE.md section 10.2), so the same
discount is applied before deciding whether a part has a text layer worth
reading. On this corpus none of the three does -- one Booklet A page comes back
with a partial Latin-only OCR layer whose words are visibly mangled
("dieȨ .ȩ.Ȫȫrtl}!"), which is the same trap the Chinese compilations set -- so
Vision is the only source.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import en_corpus
from prelim_unpack import text_layer_chars
from unpack import DEFAULT_DPI, unpack

REPO = Path(__file__).resolve().parent.parent
WORK_EN_A = REPO / "work-en-a"
WORK_EN_B = REPO / "work-en-b"
WORK_EN_ANS = REPO / "work-en-ans"

# Each part's root. The filename stem stays "page" in all three because the OCR
# cache is written beside the pages -- <root>/<paper>/ocr-vision/<stem>.json --
# and the roots already differ, so two pages of the same name cannot share one
# cache entry the way they would inside a single paper directory.
TARGETS = {
    "A": WORK_EN_A,
    "B": WORK_EN_B,
    "Answers": WORK_EN_ANS,
}


def unpack_paper(paper: dict, dpi: int = DEFAULT_DPI,
                 overwrite: bool = False) -> dict:
    out: dict[str, dict] = {}
    for part, root in TARGETS.items():
        src = en_corpus.part_path(paper["paper"], part)
        if not src.exists():
            raise FileNotFoundError(f"{paper['paper']}: {part} not ingested ({src})")
        out_dir = root / paper["paper"]
        manifest = unpack(src, paper["paper"], out_dir, dpi=dpi,
                          overwrite=overwrite, year=paper["year"])
        manifest["text_layer_chars"] = text_layer_chars(src)
        manifest["school"] = paper["school"]
        manifest["subject"] = "english"
        manifest["part"] = part
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        out[part] = manifest
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*",
                        help="paper ids to unpack (default: all in the registry)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    registry = en_corpus.load_registry()
    if not registry:
        print("nothing ingested; run build/en_corpus.py first", file=sys.stderr)
        return 1
    known = {p["paper"]: p for p in registry}
    wanted = args.papers or list(known)
    missing = [p for p in wanted if p not in known]
    if missing:
        print(f"not in the registry: {missing}", file=sys.stderr)
        return 1

    for paper_id in wanted:
        paper = known[paper_id]
        parts = unpack_paper(paper, dpi=args.dpi, overwrite=args.overwrite)
        counts = " ".join(f"{part}={parts[part]['num_pages']:2d}pp"
                          for part in TARGETS)
        chars = sum(parts[part]["text_layer_chars"] for part in TARGETS)
        note = f"  [text layer: {chars:,} chars — check before trusting]" if chars else ""
        print(f"{paper['school']:16s} {counts}{note}")

    print(f"\n{len(wanted)} papers rendered @ {args.dpi} dpi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
