"""Detect Booklet A / Booklet B / answers page ranges in an unpacked paper.

Anchoring strategy, in order of how much each signal is trusted:

1. The Booklet B cover. It is the one page carrying "PASTE YOUR BARCODE LABEL HERE"
   across its top third, and its footer states "This booklet consists of N printed
   pages". Both OCR cleanly at 300 dpi on the papers checked so far.
2. Per-page paper codes. Booklet A pages footer "0009/02(A)", Booklet B pages
   "0009/2B". An independent per-page vote, used to cross-check the ranges.
3. The answer pages, headed "PSLE Yearly Science - Answers" and footed with the
   Educational Publishing House copyright line.

Booklet A is derived as "page 1 up to the page before the Booklet B cover" rather
than from its own stated page count, because that count is not a page range: 2025
states "15 printed pages and 1 blank page" for a booklet 16 pages long, while 2024
states a flat "16 printed pages". Trailing blank pages belong to the booklet and are
counted separately or not at all, so the stated figure is used only as a
cross-check, never as the anchor.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytesseract
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"

BARCODE_RE = re.compile(r"PASTE\s+YOUR\s+BARCODE", re.I)
PRINTED_PAGES_RE = re.compile(
    r"consists?\s+of\s+(\d{1,2})\s+printed\s+pages?"
    r"(?:\s+and\s+(\d{1,2})\s+blank\s+pages?)?", re.I)
PAPER_CODE_A_RE = re.compile(r"0009\s*/\s*0?2\s*\(\s*A\s*\)", re.I)
PAPER_CODE_B_RE = re.compile(r"0009\s*/\s*0?2\s*\(?\s*B\s*\)?", re.I)
ANSWERS_RE = re.compile(r"PSLE\s+YEARLY\s+SCIENCE|Educational\s+Publishing\s+House", re.I)
# A real blank page carries "BLANK PAGE" as a heading on its own line. Matching the
# flattened page text instead would also catch the cover's "...and 1 blank page."
BLANK_PAGE_RE = re.compile(r"^\W*BLANK\s+PAGE\W*$", re.I | re.M)
GOTO_B_RE = re.compile(r"Go\s+on\s+to\s+Booklet\s+B", re.I)


def ocr_page(work: Path, number: int, refresh: bool = False) -> str:
    """OCR one page, caching the result -- a full paper is ~70s of tesseract."""
    cache = work / "ocr" / f"page-{number:03d}.txt"
    if cache.exists() and not refresh:
        return cache.read_text()
    cache.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(work / "pages" / f"page-{number:03d}.png") as img:
        text = pytesseract.image_to_string(img)
    cache.write_text(text)
    return text


def page_signals(text: str) -> dict:
    flat = re.sub(r"\s+", " ", text)
    printed = PRINTED_PAGES_RE.search(flat)
    # BLANK_PAGE_RE is line-anchored, so it runs against the raw text, not `flat`.
    return {
        "barcode_cover": bool(BARCODE_RE.search(flat)),
        "printed_pages": int(printed.group(1)) if printed else None,
        "blank_pages": int(printed.group(2)) if printed and printed.group(2) else 0,
        "code_a": bool(PAPER_CODE_A_RE.search(flat)),
        "code_b": bool(PAPER_CODE_B_RE.search(flat)),
        "answers": bool(ANSWERS_RE.search(flat)),
        "blank_page": bool(BLANK_PAGE_RE.search(text)),
        "goto_booklet_b": bool(GOTO_B_RE.search(flat)),
    }


def _code_vote(signals: list[dict], lo: int, hi: int) -> tuple[int, int]:
    """Count (A, B) paper-code votes over the 1-indexed inclusive page range."""
    votes = Counter()
    for n in range(lo, hi + 1):
        s = signals[n - 1]
        # A pages are "(A)"; B pages are "2B". Check A first -- "0009/02(A)" would
        # otherwise also satisfy the looser B pattern.
        if s["code_a"]:
            votes["a"] += 1
        elif s["code_b"]:
            votes["b"] += 1
    return votes["a"], votes["b"]


def detect(work: Path, refresh: bool = False) -> dict:
    manifest = json.loads((work / "manifest.json").read_text())
    num_pages = manifest["num_pages"]
    signals = [page_signals(ocr_page(work, n, refresh)) for n in range(1, num_pages + 1)]

    warnings: list[str] = []

    # --- anchor 1: the Booklet B cover -------------------------------------
    covers = [n for n in range(1, num_pages + 1) if signals[n - 1]["barcode_cover"]]
    # Page 1 is the Booklet A cover and carries the same barcode box; the Booklet B
    # cover is the next one.
    b_cover = next((n for n in covers if n > 1), None)
    if b_cover is None:
        # Fall back to the first page where the paper code flips from A to B.
        b_cover = next((n for n in range(2, num_pages + 1)
                        if signals[n - 1]["code_b"] and not signals[n - 1]["code_a"]), None)
        if b_cover is None:
            raise ValueError(f"{work.name}: could not locate the Booklet B cover")
        warnings.append("Booklet B cover found via paper code, not the barcode label")

    # --- anchor 2: how long Booklet B is -----------------------------------
    b_printed = signals[b_cover - 1]["printed_pages"]
    first_answer = next((n for n in range(b_cover + 1, num_pages + 1)
                         if signals[n - 1]["answers"]), None)
    if b_printed is not None:
        b_end = b_cover + b_printed - 1
    elif first_answer is not None:
        b_end = first_answer - 1
        warnings.append("Booklet B page count unreadable; ended it at the first answer page")
    else:
        b_end = num_pages
        warnings.append("Booklet B page count unreadable and no answer pages found; "
                        "ran Booklet B to the end of the paper")

    a_start, a_end = 1, b_cover - 1
    answers = (b_end + 1, num_pages) if b_end < num_pages else None

    # --- cross-checks -------------------------------------------------------
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            warnings.append(f"{name}: {detail}")

    a_votes_a, a_votes_b = _code_vote(signals, a_start, a_end)
    check("booklet_a_paper_codes", a_votes_a > a_votes_b,
          f"pages {a_start}-{a_end} voted A={a_votes_a} B={a_votes_b}")

    b_votes_a, b_votes_b = _code_vote(signals, b_cover, b_end)
    check("booklet_b_paper_codes", b_votes_b > b_votes_a,
          f"pages {b_cover}-{b_end} voted A={b_votes_a} B={b_votes_b}")

    a_printed = signals[0]["printed_pages"]
    if a_printed is not None:
        # A trailing blank page is inside the booklet but counted separately in the
        # footer ("15 printed pages and 1 blank page" == 16 physical pages).
        a_blank = signals[0]["blank_pages"]
        stated = a_printed + a_blank
        blank_note = f" + {a_blank} blank" if a_blank else ""
        check("booklet_a_stated_length", stated == (a_end - a_start + 1),
              f"cover states {a_printed} printed{blank_note} = {stated} pages, "
              f"derived range is {a_end - a_start + 1}")
    else:
        checks.append({"check": "booklet_a_stated_length", "ok": None,
                       "detail": "cover page count unreadable (expected; not an anchor)"})

    if first_answer is not None:
        check("answers_follow_booklet_b", first_answer == b_end + 1,
              f"first answer page is {first_answer}, Booklet B ends at {b_end}")
    else:
        check("answers_found", False, "no answer pages detected")

    goto = [n for n in range(1, num_pages + 1) if signals[n - 1]["goto_booklet_b"]]
    if goto:
        check("goto_booklet_b_marker", max(goto) < b_cover,
              f"'Go on to Booklet B' on page(s) {goto}, cover at {b_cover}")

    hard_failures = sum(1 for c in checks if c["ok"] is False)
    confidence = "high" if hard_failures == 0 else "medium" if hard_failures == 1 else "low"

    return {
        "year": manifest["year"],
        "num_pages": num_pages,
        "booklet_a": {"start": a_start, "end": a_end},
        "booklet_b": {"start": b_cover, "end": b_end, "cover": b_cover,
                      "stated_printed_pages": b_printed},
        "answers": {"start": answers[0], "end": answers[1]} if answers else None,
        "blank_pages": [n for n in range(1, num_pages + 1) if signals[n - 1]["blank_page"]],
        "confidence": confidence,
        "checks": checks,
        "warnings": warnings,
        "needs_human_review": confidence != "high",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--work", type=Path, default=WORK_DIR)
    parser.add_argument("--refresh-ocr", action="store_true")
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.name) for p in args.work.iterdir()
                                 if p.is_dir() and p.name.isdigit())
    if not years:
        print(f"nothing unpacked under {args.work}; run unpack.py first", file=sys.stderr)
        return 1

    exit_code = 0
    for year in years:
        work = args.work / str(year)
        result = detect(work, refresh=args.refresh_ocr)
        (work / "boundaries.json").write_text(json.dumps(result, indent=2))

        a, b, ans = result["booklet_a"], result["booklet_b"], result["answers"]
        ans_txt = f"{ans['start']}-{ans['end']}" if ans else "none"
        print(f"{year}: A {a['start']}-{a['end']}  "
              f"B {b['start']}-{b['end']}  answers {ans_txt}  "
              f"[{result['confidence']}]")
        for c in result["checks"]:
            mark = {True: "ok  ", False: "FAIL", None: "skip"}[c["ok"]]
            print(f"    {mark} {c['check']}: {c['detail']}")
        if result["needs_human_review"]:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
