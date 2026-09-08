"""The Chinese prelim corpus: what a paper is called, and where its parts are.

Fourteen schools' PSLE-style Paper 2 exist for Science and English already
(CLAUDE.md sections 10 and 11); this is the same idea for Chinese. The source
is two directories -- "Paper 2" and "Answers" -- which is the shape
`build/prelims.py` reads for the Science prelims and the shape `cn_split.py`
has to *derive* for the PSLE Chinese corpus (CLAUDE.md section 7.1): already
split, so none of that boundary detection applies here. There is no MCQ/OEQ
split to make either -- Chinese Paper 2 is sat as one booklet, exactly as the
PSLE corpus is (CLAUDE.md section 7.1) -- so this module has two parts where
`prelims.py` has three.

A paper id follows the same convention as the other two prelim corpora
(`build/corpus.py`): `2026-prelim-<school>`. The filenames carry no spaces at
all -- "2026_RedSwastika.pdf", "2026_StNicholas.pdf.pdf" -- unlike the Science
prelims' "2025-Prelim Exam-Red Swastika.pdf", so the school-name word boundary
has to be read off the capitalisation instead of split on spaces, and the
stray doubled ".pdf.pdf" extension (two schools in the Answers folder) is
absorbed the same way `prelims.py`'s regex absorbs it for Science.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers"
# One level down, mirroring papers/prelims/ and papers/english/, so a glob
# written for one corpus cannot pick up another's files (build/corpus.py).
CN_PRELIM_DIR = PAPERS_DIR / "chinese-prelims"

DEFAULT_SOURCE = Path(
    "/Users/Prats/Library/CloudStorage/OneDrive-Personal/Arya PSLE/Chinese/2026-prelims")

# The source folder name varies by convention even within one corpus family
# (build/prelims.py's Answers/"Answer Key" split) -- tried in order, first
# match wins.
PART_ALIASES: dict[str, list[str]] = {
    "Paper2": ["Paper 2", "Paper2"],
    "Answers": ["Answers", "Answer", "Answer Key"],
}
# The two parts, and the directory each is copied into.
PARTS = {"Paper2": "Paper2", "Answers": "Answers"}

SOURCE_YEAR_RE = re.compile(r"(?P<year>\d{4})-prelims$")

# "2026_ACSJ.pdf", "2026_StNicholas.pdf.pdf". Same shape build/prelims.py reads
# for the Science prelims -- year, a separator, the school, one or more
# ".pdf"s -- because this source folder was filed by the same convention.
SOURCE_RE = re.compile(
    r"^(?P<year>\d{4})[-_](?:Prelim(?:\s+Exam)?-)?(?P<school>.+?)(?:\.pdf)+$",
    re.IGNORECASE)

# Splits "RedSwastika" -> "Red-Swastika" before lowercasing. These filenames
# have no spaces anywhere ("2026_RedSwastika.pdf"), unlike the Science
# prelims' "Red Swastika.pdf", so the word boundary has to be read off the
# capitalisation rather than assumed away.
CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def slugify(school: str) -> str:
    """"RedSwastika" -> "red-swastika". Directory- and URL-safe."""
    spaced = CAMEL_BOUNDARY.sub("-", school)
    slug = re.sub(r"[^a-z0-9]+", "-", spaced.lower()).strip("-")
    if not slug:
        raise ValueError(f"school name slugifies to nothing: {school!r}")
    return slug


def paper_id(school: str, year: int) -> str:
    return f"{year}-prelim-{slugify(school)}"


@dataclass
class Prelim:
    paper: str          # "2026-prelim-red-swastika"
    school: str          # "RedSwastika", as printed in the source filename
    year: int
    parts: dict[str, str]   # part name -> path, repo-relative where possible


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path.resolve())


def _infer_year(source: Path) -> int:
    match = SOURCE_YEAR_RE.search(source.name)
    if not match:
        raise ValueError(
            f"cannot infer a year from {source.name!r}; pass --year explicitly")
    return int(match.group("year"))


def _find_part_dir(source: Path, part: str) -> Path | None:
    for alias in PART_ALIASES[part]:
        directory = source / alias
        if directory.is_dir():
            return directory
    return None


def discover(source: Path = DEFAULT_SOURCE,
             year: int | None = None) -> tuple[list[Prelim], list[str]]:
    """Find every school with both parts present.

    A school missing a part is not returned as a partial paper -- the answer
    key is what makes the paper markable and the question paper is what makes
    it practisable, so a half-present school is a problem to report, never a
    paper to build.
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
            paper=paper_id(school, year),
            school=school,
            year=year,
            parts={part: _repo_relative(parts[part]) for part in PARTS},
        ))
    return papers, problems


REGISTRY = CN_PRELIM_DIR / "registry.json"


def load_registry(path: Path = REGISTRY) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())["papers"]


def ingest(source: Path = DEFAULT_SOURCE, dest: Path = CN_PRELIM_DIR,
           force: bool = False, dry_run: bool = False,
           year: int | None = None) -> tuple[list[Prelim], list[str]]:
    """Copy each school's two PDFs into papers/chinese-prelims/ under its id.

    Copied rather than referenced, for the reason CLAUDE.md section 10.2
    gives: the source is a OneDrive folder, and cloud sync can evict a file to
    a placeholder.
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
    sources = existing.get("sources", [])
    sources = [s for s in sources if s.get("source") != str(source)]
    sources.append({"year": year if year is not None else _infer_year(source),
                     "source": str(source)})
    REGISTRY.write_text(json.dumps(
        {"sources": sources,
         "papers": [by_id[k] for k in sorted(by_id)]}, indent=2))
    return papers, problems


def part_path(paper: str, part: str, dest: Path = CN_PRELIM_DIR) -> Path:
    return dest / PARTS[part] / f"{paper}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=CN_PRELIM_DIR)
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
