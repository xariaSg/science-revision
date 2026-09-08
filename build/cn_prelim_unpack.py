"""Render each ingested Chinese prelim paper's two PDFs to page images.

    work-cn/<paper>/pages/          Paper 2, the whole booklet
    work-cn/<paper>/answer-pages/   the school's answer key

Shares `work-cn` with the PSLE Chinese corpus rather than getting a root of
its own: paper ids never collide with year strings (`build/corpus.py`), and
`cn_index.py`/`cn_key.py` are year-only today, so nothing there can pick up a
prelim paper by accident the way English's `papers.discover(WORK_A)` risk
applies to Science (CLAUDE.md section 11.1). Filenames stay `page`/`answer`,
matching `cn_unpack.py`, since the OCR cache is keyed on the image name and
the two directories already differ.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import cn_prelims
from cn_unpack import render, DEFAULT_DPI

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"

PAPER = "Paper2"
ANSWER = "Answers"


def unpack_paper(paper: dict, dpi: int = DEFAULT_DPI,
                 work_dir: Path = WORK_DIR) -> dict:
    paper_id = paper["paper"]
    src_paper = cn_prelims.part_path(paper_id, PAPER)
    src_answer = cn_prelims.part_path(paper_id, ANSWER)
    if not src_paper.exists():
        raise FileNotFoundError(f"{paper_id}: {PAPER} not ingested ({src_paper})")
    if not src_answer.exists():
        raise FileNotFoundError(f"{paper_id}: {ANSWER} not ingested ({src_answer})")

    target = work_dir / paper_id
    paper_pages = render(src_paper, target / "pages", dpi)
    answer_pages = render(src_answer, target / "answer-pages", dpi, stem="answer")

    manifest = {
        "paper": paper_id,
        "school": paper["school"],
        "year": paper["year"],
        "subject": "chinese",
        "dpi": dpi,
        "paper_pdf": {
            "source": str(src_paper.relative_to(REPO)),
            "num_pages": len(paper_pages),
            "pages": [asdict(p) for p in paper_pages],
        },
        "answers": {
            "source": str(src_answer.relative_to(REPO)),
            "num_pages": len(answer_pages),
            "pages": [asdict(p) for p in answer_pages],
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("papers", nargs="*",
                        help="paper ids to unpack (default: all in the registry)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    args = parser.parse_args(argv)

    registry = cn_prelims.load_registry()
    if not registry:
        print("nothing ingested; run build/cn_prelims.py first", file=sys.stderr)
        return 1
    known = {p["paper"]: p for p in registry}
    wanted = args.papers or list(known)
    missing = [p for p in wanted if p not in known]
    if missing:
        print(f"not in the registry: {missing}", file=sys.stderr)
        return 1

    for paper_id in wanted:
        manifest = unpack_paper(known[paper_id], dpi=args.dpi)
        print(f"{paper_id:28s} {manifest['paper_pdf']['num_pages']:2d}pp paper, "
              f"{manifest['answers']['num_pages']:2d}pp answers @ {args.dpi} dpi")

    print(f"\n{len(wanted)} papers rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
