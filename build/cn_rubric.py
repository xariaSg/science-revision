"""Turn the Chinese answer key into rubrics.

This is the step that build/rubric.py deliberately cannot do for Science. There,
a keypoint is an ordered link in a cause-and-effect chain, splitting prose on
sentence boundaries produces plausible-looking rubrics that award marks in the
wrong places, and the scaffold stays honestly empty until a human fills it in.

Here the publisher has already done it. Every award point is marked in the text
with its own value, so the split is not inference -- it is reading a delimiter:

    贝贝的两个哥哥经常吵架（1）。因为二哥经常争做老大（1），大哥也不相让（1）。
    -> "贝贝的两个哥哥经常吵架"      1 mark
       "因为二哥经常争做老大"        1 mark
       "大哥也不相让"                1 mark

Two differences from the Science rubric schema, both deliberate:

* No chains and no facet roles. Chinese comprehension answers are mostly an
  unordered set of retrievable points -- Q38's four marks are four separate
  observations about the brothers, not a chain where a gap in the middle breaks
  the link. Ordering them would invent a structure the source does not have.
* No contextual gate. The Science gate exists to catch a memorised definition
  recited at a scenario it does not fit; a comprehension answer is already tied
  to its passage, and there is no general-principle recital to guard against.

Language quality is never a keypoint. Marks for 语言 appear only on the writing
task, which is self-marked, so nothing here awards or deducts for phrasing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"

# The marker that ends a keypoint, and its value.
MARKER = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*[）)]")
# Punctuation a keypoint inherits from the sentence it was cut out of.
LEADING = "。，、；：？！,.;:?! 　"


def keypoints(model_answer: str) -> list[dict]:
    """Split a model answer at its printed mark markers."""
    out: list[dict] = []
    cursor = 0
    for index, match in enumerate(MARKER.finditer(model_answer), start=1):
        statement = model_answer[cursor:match.start()].lstrip(LEADING).strip()
        cursor = match.end()
        if statement:
            out.append({
                "kp_id": f"kp_{index}",
                "position": index,
                "marks": float(match.group(1)),
                "statement": statement,
            })
    return out


def build_rubrics(year: int, work_dir: Path = WORK_DIR) -> dict:
    root = work_dir / str(year)
    paper = json.loads((root / "questions.json").read_text())
    key = json.loads((root / "key.json").read_text())

    by_number = {e["question"]: e for e in key["entries"]
                 if e["booklet"] == "paper2"}
    rubrics = []
    problems = []

    for question in paper["questions"]:
        number = question["question"]
        entry = by_number.get(number)
        if entry is None or question["response_mode"] == "choose":
            continue

        points = keypoints(entry["model_answer"])
        awarded = round(sum(p["marks"] for p in points), 2)
        rubric = {
            "rubric_id": f"{year}_Q{number}",
            "question": number,
            "marks": question["marks"],
            "section": question["section"],
            "group": question["group"],
            "response_mode": question["response_mode"],
            "keypoints": points,
            "keypoint_marks": awarded,
            "model_answer": entry["model_answer"],
            "note": entry["note"],
            "free_response": entry["free_response"],
            "mark_scheme": entry["mark_scheme"],
            "source": key["source"],
            "authoritative": key["authoritative"],
        }

        if question["response_mode"] == "self_marked":
            rubric["auto_marked"] = False
        elif awarded != question["marks"]:
            # A rubric that awards a different total from the paper would mark a
            # correct answer short, so it is refused rather than shipped.
            rubric["auto_marked"] = False
            problems.append(f"Q{number}: keypoints total {awarded}, paper states "
                            f"{question['marks']}; not auto-marked")
        else:
            rubric["auto_marked"] = True
        rubrics.append(rubric)

    out = {
        "year": year,
        "subject": "chinese",
        "source": key["source"],
        "authoritative": key["authoritative"],
        "rubrics": rubrics,
        "problems": problems,
        "needs_review": bool(problems),
    }
    (root / "rubrics.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args(argv)

    years = args.years or sorted(
        int(p.name) for p in WORK_DIR.iterdir()
        if p.is_dir() and p.name.isdigit())
    for year in years:
        out = build_rubrics(year)
        auto = [r for r in out["rubrics"] if r["auto_marked"]]
        print(f"{year}: {len(out['rubrics'])} rubrics, {len(auto)} auto-marked, "
              f"{sum(len(r['keypoints']) for r in auto)} keypoints")
        for line in out["problems"]:
            print(f"   note: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
