"""The school prelim corpus: what a paper is called, and where its parts are.

The PSLE corpus is one compilation per year, so a paper's identity there is its
year and nothing else needed saying. The prelims break that: several schools sit
their own paper in the same year, so a bare year no longer names a paper. Identity
becomes a string id -- `2025-prelim-rosyth` -- and the PSLE papers keep theirs
unchanged as `2025`, `2024`, ... so nothing already built has to move.

That string is what the work directories, the rubric files, the routes and the
attempt log all key on from here. `year` survives beside it as the calendar year,
because the syllabus era is a property of the year (CLAUDE.md section 5) and every
prelim sat in a given year shares it.

The source is three directories -- MCQ, OEQ, Answers -- which is already the shape
the Science pipeline reads (papers/MCQ-Booklet-A and friends), so the split that
cn_split.py has to derive for Chinese is simply given here. What is *not* given is
consistent naming, and it changes year to year: 2025's thirteen files are
"2025-Prelim Exam-<school>.pdf" and one is "2025-Prelim-ACS Junior.pdf"; 2026's are
"2026_<School>.pdf" with no "Prelim" word at all, and two of those arrive with a
stray double ".pdf.pdf" extension. The school is parsed rather than assumed, and a
school missing any of its three parts is reported rather than half-built.

**A second year is a second source, not a replacement.** `ingest()` merges new
papers into the existing registry keyed on paper id, so re-running it for 2026
does not erase what 2025 already built -- the opposite would silently delete a
built corpus every time a new year's papers arrived.
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

ARYA_PSLE = Path(
    "/Users/Prats/Library/CloudStorage/OneDrive-Personal/Arya PSLE/Science")
DEFAULT_SOURCE = ARYA_PSLE / "2025-prelims"

PRELIM_YEAR = 2025  # the default source's year, kept for callers that omit one

# The canonical part name (used for dest directories and part_path()) and the
# source subfolder name(s) that hold it. A list because the folder itself is
# renamed year to year -- 2025 uses "Answers", 2026 uses "Answer Key" -- and
# trying each in turn beats hardcoding either.
PART_ALIASES: dict[str, list[str]] = {
    "MCQ": ["MCQ"],
    "OEQ": ["OEQ"],
    "Answers": ["Answers", "Answer Key"],
}

# The three parts, and the directory each is copied into. The names match the PSLE
# split directories so the same mental model covers both corpora.
PARTS = {
    "MCQ": "MCQ-Booklet-A",
    "OEQ": "OEQ-Booklet-B",
    "Answers": "Answers",
}

# Matches both "2025-Prelim Exam-Ai Tong.pdf" / "2025-Prelim-ACS Junior.pdf" (the
# "Exam" is optional because exactly one 2025 file omits it) and 2026's bare
# "2026_NanHua.pdf" -- no "Prelim" word, "_" instead of "-", and sometimes a
# doubled ".pdf.pdf" suffix that "(?:\.pdf)+" absorbs rather than treating as part
# of the school name. Requiring "Prelim" drops every 2026 file silently, which is
# the exact failure mode this whole module is arranged against.
SOURCE_RE = re.compile(
    r"^(?P<year>\d{4})[-_](?:Prelim(?:\s+Exam)?-)?(?P<school>.+?)(?:\.pdf)+$",
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


# "2025-prelims" -> 2025. Lets --source alone decide the year for a folder named
# the conventional way, rather than requiring a redundant --year on every call.
SOURCE_YEAR_RE = re.compile(r"(?P<year>\d{4})-prelims$")


def _infer_year(source: Path) -> int:
    match = SOURCE_YEAR_RE.search(source.name)
    if not match:
        raise ValueError(
            f"cannot infer a year from {source.name!r}; pass --year explicitly")
    return int(match.group("year"))


def _find_part_dir(source: Path, part: str) -> Path | None:
    """The source subfolder holding `part`, trying each known alias in turn.

    The folder itself is renamed year to year -- 2025's is "Answers", 2026's is
    "Answer Key" -- so the first alias that exists on disk wins.
    """
    for alias in PART_ALIASES[part]:
        directory = source / alias
        if directory.is_dir():
            return directory
    return None


def discover(source: Path = DEFAULT_SOURCE,
             year: int | None = None) -> tuple[list[Prelim], list[str]]:
    """Find every school with all three parts present.

    Returns (complete papers, problems). A school missing a part is *not* returned
    as a partial paper: the answer key is what makes Booklet A markable and the
    question paper is what makes it practisable, so a half-present school is a
    problem to report, never a paper to build.
    """
    if year is None:
        year = _infer_year(source)

    found: dict[str, dict[str, Path]] = {}
    problems: list[str] = []

    for part in PARTS:
        directory = _find_part_dir(source, part)
        if directory is None:
            aliases = " / ".join(PART_ALIASES[part])
            problems.append(f"missing source directory: {source} / [{aliases}]")
            continue
        for path in sorted(directory.iterdir()):
            if path.name.startswith("."):
                continue
            match = SOURCE_RE.match(path.name)
            if not match:
                if path.suffix.lower() == ".pdf":
                    problems.append(f"{part}/{path.name}: name not understood")
                continue
            file_year = int(match.group("year"))
            if file_year != year:
                problems.append(
                    f"{part}/{path.name}: filename year {file_year} does not "
                    f"match source year {year} — skipped")
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
            paper=paper_id(school, year=year),
            school=school,
            year=year,
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
           force: bool = False, dry_run: bool = False,
           year: int | None = None) -> tuple[list[Prelim], list[str]]:
    """Copy each school's three PDFs into papers/prelims/ under its paper id.

    Copied rather than referenced: the source sits in a cloud-synced folder whose
    files can be evicted to placeholders, and a corpus that stops building because
    OneDrive reclaimed space is a corpus that cannot be rebuilt. papers/ is
    gitignored (CLAUDE.md section 2.1), so this stays local either way.

    **Merged into the registry, not written fresh.** A second year is a second
    source, and every prelim year built so far shares one registry.json; writing
    it fresh here would silently delete every other year's entries the moment a
    new year was ingested.
    """
    papers, problems = discover(source, year=year)
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
    existing = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
    by_id = {p["paper"]: p for p in existing.get("papers", [])}
    for paper in papers:
        by_id[paper.paper] = asdict(paper)
    # Older registries (pre-multi-source) recorded a single "year"/"source" pair
    # rather than a list; fold that one entry in rather than dropping it.
    sources = existing.get("sources")
    if sources is None:
        sources = [{"year": existing["year"], "source": existing["source"]}] \
            if "source" in existing else []
    sources = [s for s in sources if s.get("source") != str(source)]
    sources.append({"year": year if year is not None else _infer_year(source),
                     "source": str(source)})
    REGISTRY.write_text(json.dumps(
        {"sources": sources,
         "papers": [by_id[k] for k in sorted(by_id)]}, indent=2))
    return papers, problems


def part_path(paper: str, part: str, dest: Path = PRELIM_DIR) -> Path:
    return dest / PARTS[part] / f"{paper}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=PRELIM_DIR)
    parser.add_argument("--year", type=int, default=None,
                        help="calendar year sat, if it cannot be inferred from "
                             "--source's own directory name (e.g. 2026-prelims)")
    parser.add_argument("--force", action="store_true",
                        help="re-copy files that are already present")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be ingested and copy nothing")
    args = parser.parse_args(argv)

    papers, problems = ingest(args.source, args.dest, args.force, args.dry_run,
                              year=args.year)
    for paper in papers:
        print(f"{paper.paper:32s} {paper.school}")
    print(f"\n{len(papers)} papers"
          f"{' (dry run, nothing copied)' if args.dry_run else ''}")
    for problem in problems:
        print(f"  PROBLEM: {problem}", file=sys.stderr)
    return 1 if problems or not papers else 0


if __name__ == "__main__":
    raise SystemExit(main())
