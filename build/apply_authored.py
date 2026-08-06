"""Merge authored chains from build/authored/<year>.py into rubrics/<year>.json.

Keeping the chains as source rather than editing the generated JSON means
re-scaffolding never loses them, and a diff shows what changed in the rubric rather
than in a wall of regenerated fields.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AUTHORED_DIR = Path(__file__).resolve().parent / "authored"
RUBRIC_DIR = REPO / "rubrics"

MERGE_FIELDS = ("chains", "chains_required", "mark_model", "topics", "traps",
                "context_gate")


def load_authored(year: int) -> dict:
    path = AUTHORED_DIR / f"{year}.py"
    if not path.exists():
        return {}
    spec = importlib.util.spec_from_file_location(f"authored_{year}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "CHAINS", {})


def apply(year: int, rubric_dir: Path = RUBRIC_DIR) -> tuple[int, list[str]]:
    target = rubric_dir / f"{year}.json"
    data = json.loads(target.read_text())
    authored = load_authored(year)

    applied = 0
    unmatched = list(authored)
    for rubric in data["rubrics"]:
        key = (rubric["question"], rubric["part"])
        entry = authored.get(key)
        if entry is None:
            continue
        unmatched.remove(key)
        for field in MERGE_FIELDS:
            if field in entry:
                rubric[field] = entry[field]
        rubric.setdefault("mark_model", "per_keypoint")
        applied += 1

    target.write_text(json.dumps(data, indent=2))
    return applied, [f"Q{q}({p})" for q, p in unmatched]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="*", type=int)
    parser.add_argument("--rubrics", type=Path, default=RUBRIC_DIR)
    args = parser.parse_args(argv)

    years = args.years or sorted(int(p.stem) for p in AUTHORED_DIR.glob("*.py")
                                 if p.stem.isdigit())
    exit_code = 0
    for year in years:
        applied, unmatched = apply(year, args.rubrics)
        print(f"{year}: applied {applied} authored rubric(s)")
        if unmatched:
            print(f"    WARN authored but no matching rubric: {', '.join(unmatched)}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
