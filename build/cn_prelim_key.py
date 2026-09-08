"""Extract the answer key for a Chinese prelim Paper 2.

Two sources, read by a person rather than by OCR, and for two different
reasons:

* **The MCQ grid** (Q1-Q32) is `review/cn-prelim-mcq-key.json`. Every one of
  the ten schools' grids is a scanned table, nine of the ten crossed by a
  heavy watermark, and no single geometry reader was worth tuning against ten
  different table shapes for a one-off corpus -- so the grid was read by eye
  against the rendered page instead (CLAUDE.md section 1.6.1: there is no
  partial credit to soften a wrong digit here). That file is authoritative for
  these ten papers; this module only cross-checks it against what the paper
  itself asks -- every "choose" question must have an entry, and every entry
  must be a valid option for the question it answers.

* **The written model answers** (Q33-Q40) are `review/cn-prelim-written-answers.json`,
  transcribed by eye for the same reason the PSLE and English keys' own
  hand-read cells are (review/prelim-mcq-key.json, review/en-mcq-key.json):
  these pages mix print, boxed tables and handwritten marking notes that the
  shared OCR pass does not read reliably enough to show a child unreviewed.

Every written question is self-marked -- none of these ten keys prints inline
mark markers in a form safe to auto-parse across all ten (CLAUDE.md section
10.5's "chains are not authored" applies here exactly as it does to the
Science prelims), so `build_rubrics()` scaffolds every one with
`auto_marked: false` and the model answer text for the student to compare
against.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cn_prelims

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"
MCQ_KEY = REPO / "review" / "cn-prelim-mcq-key.json"
WRITTEN_ANSWERS = REPO / "review" / "cn-prelim-written-answers.json"

BANK_SECTION = "完成对话"
DEFAULT_OPTIONS = 4
MAX_BANK_OPTIONS = 8


def load_mcq_key(paper: str) -> dict[int, int]:
    data = json.loads(MCQ_KEY.read_text())
    entry = data.get(paper)
    if entry is None:
        return {}
    return {int(q): int(a) for q, a in entry["answers"].items()}


def load_written_answers(paper: str) -> dict[int, str]:
    data = json.loads(WRITTEN_ANSWERS.read_text())
    entry = data.get(paper, {})
    return {int(q): text for q, text in entry.items()}


def build_key(paper: str, school: str, work_dir: Path = WORK_DIR) -> dict:
    questions_path = work_dir / paper / "questions.json"
    if not questions_path.exists():
        raise SystemExit(f"no question index for {paper}; run build/cn_prelim_index.py")
    paper_data = json.loads(questions_path.read_text())

    mcq = load_mcq_key(paper)
    written = load_written_answers(paper)
    problems: list[str] = []
    entries = []

    for q in paper_data["questions"]:
        number = q["question"]
        if q["response_mode"] == "choose":
            option = mcq.get(number)
            # 完成对话's answer bank runs up to eight entries, and indexing's
            # own count of it is the one thing this whole corpus could not
            # read reliably (CLAUDE.md: two schools' banks split across lines
            # in a way BANK_ENTRY cannot join, so it fell back to assuming
            # four). The hand-verified key is the trustworthy side of that
            # disagreement, so a bank question is checked against the bank's
            # real range rather than against indexing's possibly-undercounted
            # `options` -- validating against the weaker source would flag a
            # correct answer as if the key itself were wrong.
            valid_max = MAX_BANK_OPTIONS if q["section"] == BANK_SECTION \
                else (q["options"] or DEFAULT_OPTIONS)
            if option is None:
                problems.append(f"Q{number}: no MCQ key entry")
            elif not 1 <= option <= valid_max:
                problems.append(
                    f"Q{number}: key option ({option}) is outside 1-{valid_max}")
            entries.append({"question": number, "option": option,
                            "model_answer": None})
        else:
            model_answer = written.get(number)
            if model_answer is None:
                problems.append(f"Q{number}: no written model answer")
            entries.append({"question": number, "option": None,
                            "model_answer": model_answer})

    return {
        "paper": paper, "school": school,
        "source": f"{school} suggested answers",
        "authoritative": False,
        "read_from": "review/cn-prelim-mcq-key.json (MCQ, by eye) + "
                     "review/cn-prelim-written-answers.json (written, by eye)",
        "entries": entries,
        "problems": problems,
        "needs_review": bool(problems),
    }


def build_rubrics(paper: str, school: str, work_dir: Path = WORK_DIR) -> dict:
    """Scaffold every written question as self-marked -- CLAUDE.md section 10.5:
    the chains are not authored, so the student practises against the original
    scan and self-marks against the school's model answer."""
    questions_path = work_dir / paper / "questions.json"
    paper_data = json.loads(questions_path.read_text())
    written = load_written_answers(paper)

    rubrics = []
    for q in paper_data["questions"]:
        if q["response_mode"] == "choose":
            continue
        rubrics.append({
            "question": q["question"],
            "marks": q["marks"],
            "model_answer": written.get(q["question"]),
            "keypoints": [],
            "free_response": False,
            "mark_scheme": None,
            "auto_marked": False,
            "source": f"{school} suggested answers",
            "authoritative": False,
        })
    return {"paper": paper, "school": school, "rubrics": rubrics}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("papers", nargs="*",
                        help="paper ids to key (default: all in the registry)")
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

    failed = False
    for paper in wanted:
        school = known[paper]["school"]
        key = build_key(paper, school)
        rubrics = build_rubrics(paper, school)
        (WORK_DIR / paper / "key.json").write_text(
            json.dumps(key, indent=1, ensure_ascii=False))
        (WORK_DIR / paper / "rubrics.json").write_text(
            json.dumps(rubrics, indent=1, ensure_ascii=False))

        chosen = [e for e in key["entries"] if e["option"] is not None]
        written = [e for e in key["entries"] if e["model_answer"] is not None]
        print(f"{paper} ({school}): {len(chosen)} chosen, {len(written)} written")
        for line in key["problems"]:
            print(f"   ! {line}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
