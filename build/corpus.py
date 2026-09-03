"""Paper ids, shared by the two Science corpora.

A paper used to be named by its year, because the PSLE corpus has exactly one
paper per year. The school prelims broke that -- fourteen papers sat in 2025 -- so
a paper is named by a string id instead:

    2024                    the 2024 PSLE paper
    2025-prelim-rosyth      Rosyth's 2025 prelim

The PSLE ids are unchanged, which is the point: nothing already built moves, and
`str(year)` is still a valid id. What this module exists to stop is every build
script inventing its own answer to "which directories under work-a/ are papers?"
-- the old answer, `name.isdigit()`, silently skips every prelim.
"""

from __future__ import annotations

import re
from pathlib import Path

# "2025-prelim-rosyth" -> year 2025. Kept here rather than in prelims.py because
# reading an id is a corpus-wide concern; producing one is the prelims' business.
PRELIM_RE = re.compile(r"^(?P<year>\d{4})-prelim-(?P<school>[a-z0-9-]+)$")


def is_prelim(paper: str) -> bool:
    return bool(PRELIM_RE.match(paper))


def year_of(paper: str) -> int | None:
    """The calendar year a paper was sat, or None if the id does not encode one.

    The syllabus era is a property of the year (CLAUDE.md section 5), and the
    prelims share 2025 with the PSLE paper, so the year survives alongside the id
    rather than being replaced by it.
    """
    if paper.isdigit():
        return int(paper)
    match = PRELIM_RE.match(paper)
    return int(match.group("year")) if match else None


def sort_key(paper: str) -> tuple:
    """Order papers year by year, with a year's prelims after its PSLE paper.

    A plain string sort puts "2025-prelim-ai-tong" before "2025" is even reached
    on some comparisons and interleaves the schools with later years on others;
    the picker and every build report want the same stable order.
    """
    year = year_of(paper)
    return (year if year is not None else 9999, 0 if paper.isdigit() else 1, paper)


def discover(root: Path, marker: str = "questions.json") -> list[str]:
    """Every paper id under a work root, in corpus order.

    `marker` is the file that makes a directory a built paper -- "questions.json"
    once indexed, "manifest.json" once merely rendered.
    """
    if not root.exists():
        return []
    found = [path.name for path in root.iterdir()
             if path.is_dir() and (path / marker).exists()]
    return sorted(found, key=sort_key)
