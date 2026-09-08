"""Index a Chinese prelim Paper 2 -- a thin wrapper over `cn_index.py`.

Sampled across all ten schools before writing a line of new parsing code: every
one replicates the 2021-2025 PSLE Chinese Paper 2 format almost verbatim -- the
same five sections (语文应用/短文填空/阅读理解一/完成对话/阅读理解二), the same
MCQ/written range wording ("从第1题到第25题...电脑作答卷", "从第26题到第40题
...写在作答簿"), the same A组/B组 split. `cn_index.py`'s parser never hardcodes
40 questions or 90 marks anywhere -- it reads the paper's own section and group
headers and checks what it found against what they state (CLAUDE.md section
7.3) -- so it generalises to a differently-authored paper in the same format
with nothing to change beyond the identifier.

That identifier is the one real difference: `cn_index.index_paper(year, ...)`
takes an int and writes `work-cn/<year>/questions.json`. Passed a string paper
id instead it works unchanged -- `str(year)` on a string is the string -- so
this module calls it directly rather than duplicating it, and only relabels
the output afterwards: `questions.json["paper"]` held a constant "2" (which
booklet) that nothing downstream reads (checked before reusing it), so it is
repurposed to hold the paper id, and `"year"`/`"school"` are filled from the
registry rather than from the identifier string itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cn_index
import cn_prelims

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"


def index_paper_id(paper_id: str, registry_entry: dict,
                    work_dir: Path = WORK_DIR) -> dict:
    result = cn_index.index_paper(paper_id, work_dir)
    result["paper"] = paper_id
    result["year"] = registry_entry["year"]
    result["school"] = registry_entry["school"]
    problems = cn_index.validate(result)
    result["problems"] = problems
    result["needs_review"] = bool(problems)
    (work_dir / paper_id / "questions.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("papers", nargs="*",
                        help="paper ids to index (default: all in the registry)")
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
    for paper_id in wanted:
        paper = index_paper_id(paper_id, known[paper_id])
        counts: dict[str, int] = {}
        for q in paper["questions"]:
            counts[q["response_mode"]] = counts.get(q["response_mode"], 0) + 1
        modes = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        total = sum(q["marks"] or 0 for q in paper["questions"])
        print(f"{paper_id} ({paper['school']}): {len(paper['questions'])} "
              f"questions, {total} marks ({modes})")
        for line in paper["repairs"]:
            print(f"   repair: {line}")
        for line in paper["warnings"]:
            print(f"   warning: {line}")
        for line in paper["problems"]:
            print(f"   ! {line}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
