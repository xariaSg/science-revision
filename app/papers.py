"""Which Science papers exist, what to call them, and what order to show them in.

A paper used to be a year. Fourteen schools sat their own prelim in 2025, so it is
now a string id -- `2024` for the PSLE paper, `2025-prelim-rosyth` for Rosyth's --
and the PSLE ids are unchanged, so every URL that worked before still works.

Two things follow that the rest of the app should not have to think about:

* **A paper needs a name a child recognises.** "2025-prelim-mgs-paya-lebar" is an
  id, not a label, and the slug cannot be turned back into "MGS Paya Lebar" by
  capitalising it. The school's real name is written into the paper's own index at
  build time, so it is read from there rather than reconstructed or kept in a
  second list that could drift.

* **Fifteen papers now share a year**, so the picker groups them. Grouping is by
  what the paper *is* -- the PSLE paper for a year, or a school's prelim for that
  year -- because that is the distinction the student is choosing between.

Deliberately independent of `papers/`: that directory holds the source PDFs, is
gitignored, and is not necessarily in the container. Everything here comes from
the built work roots, which the app already depends on.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PRELIM_RE = re.compile(r"^(?P<year>\d{4})-prelim-(?P<school>[a-z0-9-]+)$")


def is_prelim(paper: str) -> bool:
    return bool(PRELIM_RE.match(str(paper)))


def year_of(paper: str) -> int | None:
    """The calendar year a paper was sat, or None if its id does not encode one.

    Kept alongside the id rather than replaced by it: the syllabus era is a
    property of the year (CLAUDE.md section 5), and a prelim shares its year with
    the PSLE paper that follows it.
    """
    paper = str(paper)
    if paper.isdigit():
        return int(paper)
    match = PRELIM_RE.match(paper)
    return int(match.group("year")) if match else None


def sort_key(paper: str) -> tuple:
    """Year by year, with a year's prelims after its PSLE paper.

    A plain string sort interleaves "2025-prelim-ai-tong" with later years, and
    the picker, the chart and every build report want one stable order.
    """
    year = year_of(paper)
    return (year if year is not None else 9999,
            0 if str(paper).isdigit() else 1, str(paper))


def discover(root: Path, marker: str = "questions.json") -> list[str]:
    """Every built paper under a work root, in corpus order."""
    if not root.exists():
        return []
    return sorted((path.name for path in root.iterdir()
                   if path.is_dir() and (path / marker).exists()),
                  key=sort_key)


@lru_cache(maxsize=1)
def _schools() -> dict[str, str]:
    """paper id -> the school's own name, read from whichever index carries it.

    Booklet A and Booklet B are indexed separately and either may be the one
    built, so both roots are consulted. The id is the fallback, which means a
    paper is always nameable even before anything records a school for it.
    """
    found: dict[str, str] = {}
    for root in (REPO / "work-a", REPO / "work-b", REPO / "work"):
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            index = path / "questions.json"
            if not index.is_dir() and index.exists():
                try:
                    school = json.loads(index.read_text()).get("school")
                except (OSError, ValueError):
                    continue
                if school:
                    found.setdefault(path.name, school)
    return found


def label(paper: str) -> str:
    """What to print on a button, a chart bar or a heading.

    A PSLE paper is its year, which is what it has always been called. A prelim
    is its school: within the "2025 Prelims" group the year is already said by
    the group, and repeating it in every label crowds out the only word that
    distinguishes one paper from the next.
    """
    paper = str(paper)
    return _schools().get(paper) or paper


def group(paper: str) -> str:
    """The heading a paper is listed under."""
    year = year_of(paper)
    if is_prelim(paper):
        return f"{year} Prelims"
    return "PSLE papers"


def describe(paper: str) -> dict:
    """The identity fields every API response carries for a paper."""
    paper = str(paper)
    return {"paper": paper, "label": label(paper), "year": year_of(paper),
            "group": group(paper), "prelim": is_prelim(paper)}


def grouped(papers: list[str]) -> list[dict]:
    """Papers arranged for the picker: PSLE first, then each year's prelims.

    Within the PSLE group the newest year is the interesting one and is listed
    first; within a prelim group the schools are alphabetical, because no school
    is more recent than another and any other order would look arbitrary.
    """
    buckets: dict[str, list[str]] = {}
    for paper in papers:
        buckets.setdefault(group(paper), []).append(paper)

    out = []
    for name, members in buckets.items():
        prelim = is_prelim(members[0])
        ordered = (sorted(members, key=label) if prelim
                   else sorted(members, key=sort_key, reverse=True))
        out.append({"group": name, "prelim": prelim,
                    "papers": [describe(p) for p in ordered]})
    # PSLE first, then prelim groups newest year first.
    out.sort(key=lambda g: (g["prelim"], -(year_of(g["papers"][0]["paper"]) or 0)))
    return out
