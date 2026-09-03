"""The 2025 school prelim corpus: what a paper is called, and where its parts are.

The PSLE corpus is one compilation per year, so a paper's identity there is its
year and nothing else needed saying. The prelims break that: fourteen schools sat
their own paper in the same year, so "2025" no longer names a paper. Identity
becomes a string id -- `2025-prelim-rosyth` -- and the PSLE papers keep theirs
unchanged as `2025`, `2024`, ... so nothing already built has to move.

That string is what the work directories, the rubric files, the routes and the
attempt log all key on from here. `year` survives beside it as the calendar year,
because the syllabus era is a property of the year (CLAUDE.md section 5) and
fifteen 2025 papers share it.

The source is three directories -- MCQ, OEQ, Answers -- which is already the shape
the Science pipeline reads (papers/MCQ-Booklet-A and friends), so the split that
cn_split.py has to derive for Chinese is simply given here. What is *not* given is
consistent naming: thirteen files are "2025-Prelim Exam-<school>.pdf" and one is
"2025-Prelim-ACS Junior.pdf", so the school is parsed rather than assumed, and a
school missing any of its three parts is reported rather than half-built.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers"
# Mirrors the PSLE layout one level down, so the two corpora never share a
# directory and a glob written for one cannot pick up the other.
PRELIM_DIR = PAPERS_DIR / "prelims"

DEFAULT_SOURCE = Path(
    "/Users/Prats/Library/CloudStorage/OneDrive-Personal/Arya PSLE/Science/2025-prelims")

# The three parts, and the directory each is copied into. The names match the PSLE
# split directories so the same mental model covers both corpora.
PARTS = {
    "MCQ": "MCQ-Booklet-A",
    "OEQ": "OEQ-Booklet-B",
    "Answers": "Answers",
}

PRELIM_YEAR = 2025

# "2025-Prelim Exam-Ai Tong.pdf", and ACS Junior's "2025-Prelim-ACS Junior.pdf".
# The "Exam" is optional because exactly one file omits it; requiring it drops that
# school silently, which is the failure mode this whole module is arranged against.
SOURCE_RE = re.compile(r"^(?P<year>\d{4})-Prelim(?:\s+Exam)?-(?P<school>.+)\.pdf$",
                       re.IGNORECASE)


def slugify(school: str) -> str:
    """"MGS Paya Lebar" -> "mgs-paya-lebar". Directory- and URL-safe."""
    slug = re.sub(r"[^a-z0-9]+", "-", school.lower()).strip("-")
    if not slug:
        raise ValueError(f"school name slugifies to nothing: {school!r}")
    return slug


def paper_id(school: str, year: int = PRELIM_YEAR) -> str:
    return f"{year}-prelim-{slugify(school)}"


@dataclass
class Prelim:
    paper: str          # "2025-prelim-rosyth"
    school: str         # "Rosyth"
    year: int
    parts: dict[str, str]   # part name -> path, repo-relative where possible


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def discover(source: Path = DEFAULT_SOURCE) -> tuple[list[Prelim], list[str]]:
    """Find every school with all three parts present.

    Returns (complete papers, problems). A school missing a part is *not* returned
    as a partial paper: the answer key is what makes Booklet A markable and the
    question paper is what makes it practisable, so a half-present school is a
    problem to report, never a paper to build.
    """
    found: dict[str, dict[str, Path]] = {}
    problems: list[str] = []

    for part in PARTS:
        directory = source / part
        if not directory.is_dir():
            problems.append(f"missing source directory: {directory}")
            continue
        for path in sorted(directory.iterdir()):
            if path.name.startswith("."):
                continue
            match = SOURCE_RE.match(path.name)
            if not match:
                if path.suffix.lower() == ".pdf":
                    problems.append(f"{part}/{path.name}: name not understood")
                continue
            school = match.group("school").strip()
            found.setdefault(school, {})[part] = path

    papers: list[Prelim] = []
    for school in sorted(found):
        parts = found[school]
        missing = [p for p in PARTS if p not in parts]
        if missing:
            problems.append(f"{school}: no {', '.join(missing)} — skipped")
            continue
        papers.append(Prelim(
            paper=paper_id(school),
            school=school,
            year=PRELIM_YEAR,
            parts={part: _repo_relative(parts[part]) for part in PARTS},
        ))
    return papers, problems


REGISTRY = PRELIM_DIR / "registry.json"


def load_registry(path: Path = REGISTRY) -> list[dict]:
    """The ingested corpus, or an empty list before anything is ingested.

    Read by the indexers and by the app, so that the display name a school is
    shown under comes from one place rather than from re-parsing filenames that
    have already proved inconsistent.
    """
    if not path.exists():
        return []
    return json.loads(path.read_text())["papers"]


def ingest(source: Path = DEFAULT_SOURCE, dest: Path = PRELIM_DIR,
           force: bool = False, dry_run: bool = False) -> tuple[list[Prelim], list[str]]:
    """Copy each school's three PDFs into papers/prelims/ under its paper id.

    Copied rather than referenced: the source sits in a cloud-synced folder whose
    files can be evicted to placeholders, and a corpus that stops building because
    OneDrive reclaimed space is a corpus that cannot be rebuilt. papers/ is
    gitignored (CLAUDE.md section 2.1), so this stays local either way.
    """
    papers, problems = discover(source)
    if dry_run:
        return papers, problems

    for paper in papers:
        for part, directory in PARTS.items():
            target = dest / directory / f"{paper.paper}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not force:
                continue
            src = Path(paper.parts[part])
            if not src.is_absolute():
                src = REPO / src
            shutil.copy2(src, target)

    dest.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(
        {"year": PRELIM_YEAR, "source": str(source),
         "papers": [asdict(p) for p in papers]}, indent=2))
    return papers, problems


def part_path(paper: str, part: str, dest: Path = PRELIM_DIR) -> Path:
    return dest / PARTS[part] / f"{paper}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=PRELIM_DIR)
    parser.add_argument("--force", action="store_true",
                        help="re-copy files that are already present")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be ingested and copy nothing")
    args = parser.parse_args(argv)

    papers, problems = ingest(args.source, args.dest, args.force, args.dry_run)
    for paper in papers:
        print(f"{paper.paper:32s} {paper.school}")
    print(f"\n{len(papers)} papers"
          f"{' (dry run, nothing copied)' if args.dry_run else ''}")
    for problem in problems:
        print(f"  PROBLEM: {problem}", file=sys.stderr)
    return 1 if problems or not papers else 0


if __name__ == "__main__":
    raise SystemExit(main())
