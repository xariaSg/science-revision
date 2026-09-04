"""The English corpus: what a paper is called, and where its three parts are.

Named `en_corpus` rather than `english` because `app/english.py` exists: the two
never share a path when the app runs, but the tests put `build/` and `app/` on
one, and two modules called `english` then shadow each other silently. The `en_`
prefix is what the rest of this pipeline uses anyway.

English Paper 2 arrives already split -- Booklet A, Booklet B and the answer key
as three separate PDFs -- which is the shape `build/prelims.py` reads for the
Science prelims and the shape `build/cn_split.py` has to *derive* for Chinese. So
this module is the ingest half only: find the triples, copy them in, record what
was found.

    2026-P6-English-Prelim-Nanyang - Paper 2 Booklet A.pdf
    2026-P6-English-Prelim-Nanyang - Paper 2 Booklet B.pdf
    2026-P6-English-Prelim-Nanyang - Answers.pdf

A paper id follows the Science prelims' convention exactly (`build/corpus.py`):
`2026-prelim-nanyang`. The two corpora never collide, because the attempt log and
every work root are keyed on the subject as well as the paper -- but the id being
the same shape means `papers.sort_key`, `papers.label` and `papers.group` all
work on English papers with nothing added.

**Only split triples are ingested.** The same source directories also hold the
whole-exam compilations -- `P6_English_Prelim_2026_Nanyang_Exam_Papers1.pdf`,
which contains Paper 1, Paper 2 and the answers in one file, and is the only form
the 2020-2025 folders have. Splitting one of those is the job `cn_split.py` does
for Chinese and it is not built here, so a compilation is reported as skipped
rather than half-ingested: a paper that is missing is visible, and a paper built
from the wrong pages is not.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "papers"
# One level down, mirroring papers/prelims/ and papers/chinese/, so a glob written
# for one corpus cannot pick up another's files.
ENGLISH_DIR = PAPERS_DIR / "english"

DEFAULT_SOURCE = Path(
    "/Users/Prats/Library/CloudStorage/OneDrive-Personal/Arya PSLE/English")

# The three parts, and the directory each is copied into. The names mirror the
# Science split directories so one mental model covers both corpora.
PARTS = {
    "A": "Booklet-A",
    "B": "Booklet-B",
    "Answers": "Answers",
}

# "2026-P6-English-Prelim-Nanyang - Paper 2 Booklet A.pdf". "Exam" is optional
# because the year folders disagree about it -- 2024 and 2025 print
# "Prelim Exam-", 2026 prints "Prelim-" -- and requiring it drops a whole year
# silently, which is the failure this module is arranged against.
SOURCE_RE = re.compile(
    r"^(?P<year>\d{4})-P6-English-Prelim(?:\s+Exam)?-(?P<school>.+?)"
    r"\s*-\s*(?P<part>Paper\s*2\s*Booklet\s*[AB]|Answers?)\.pdf$",
    re.IGNORECASE)

PART_RE = re.compile(r"Booklet\s*(?P<booklet>[AB])|Answers?", re.IGNORECASE)

# The other layout the source folders use, and the more convenient one: a
# directory per part, holding one file per school named by year and school alone.
#
#     Booklet A/2025-Nan Hua.pdf
#     Booklet B/2025-Nan Hua.pdf
#     Answer Key/2025-Nan Hua.pdf
#
# The *directory* says which part it is, so the filename identifies the paper and
# nothing more. Both layouts are read rather than one being converted into the
# other, because the source is a OneDrive folder a person adds to by hand: a
# pipeline that only accepts the shape it was written for turns a correctly filed
# paper into a paper that silently does not exist.
FOLDER_PART_RE = re.compile(
    r"^\s*(?:Paper\s*2\s*)?(?:Booklet\s*(?P<booklet>[AB])|Answers?(?:\s*Key)?)\s*$",
    re.IGNORECASE)
FOLDER_FILE_RE = re.compile(r"^(?P<year>\d{4})\s*-\s*(?P<school>.+?)\.pdf$",
                            re.IGNORECASE)
# A whole-exam compilation's own name. Matched only to *report* one that has been
# filed inside a part directory, where the directory would otherwise vouch for it:
# a compilation ingested as a Booklet A is a 40-page booklet holding Paper 1, Paper
# 2 and the answers, and it indexes to something plausible that nothing downstream
# would call wrong. Splitting one is `cn_split.py`'s job for Chinese and is not
# built here, so it is named as skipped instead.
COMPILATION_RE = re.compile(r"P6[-_\s]*English[-_\s]*Prelim", re.IGNORECASE)


def slugify(school: str) -> str:
    """"Red Swastika" -> "red-swastika". Directory- and URL-safe."""
    return re.sub(r"[^a-z0-9]+", "-", school.lower()).strip("-")


def part_of(text: str) -> str | None:
    match = PART_RE.search(text)
    if not match:
        return None
    booklet = match.group("booklet")
    return booklet.upper() if booklet else "Answers"


def classify(path: Path) -> tuple[int, str, str] | None:
    """(year, school, part) for one source file, or None if it is not one.

    A file may state its own part -- "…-Nanyang - Paper 2 Booklet A.pdf" -- or the
    directory it sits in may state it, in which case the filename carries the year
    and the school and nothing else. The filename is tried first: a name that
    states a part means it, whatever directory it has been filed under.
    """
    match = SOURCE_RE.match(path.name)
    if match:
        part = part_of(match.group("part"))
        if part is None:                                    # pragma: no cover
            return None
        return int(match.group("year")), match.group("school").strip(), part

    folder = FOLDER_PART_RE.match(path.parent.name)
    named = FOLDER_FILE_RE.match(path.name)
    if folder is None or named is None:
        return None
    booklet = folder.group("booklet")
    part = booklet.upper() if booklet else "Answers"
    return int(named.group("year")), named.group("school").strip(), part


def paper_id(year: int, school: str) -> str:
    return f"{year}-prelim-{slugify(school)}"


def part_path(paper: str, part: str) -> Path:
    return ENGLISH_DIR / PARTS[part] / f"{paper}.pdf"


def discover(source: Path = DEFAULT_SOURCE) -> tuple[list[dict], list[str]]:
    """Every complete triple under `source`, and a note for everything skipped.

    Searched recursively because the year folders are named inconsistently --
    "2026 - prelims", "2025- prelims", "2023- prelims" -- and parsing those names
    would be a second thing to get wrong when the files already state their year.
    """
    found: dict[str, dict] = {}
    skipped: list[str] = []
    if not source.exists():
        return [], [f"source directory does not exist: {source}"]

    for path in sorted(source.rglob("*.pdf")):
        if (FOLDER_PART_RE.match(path.parent.name)
                and COMPILATION_RE.search(path.name)
                and not SOURCE_RE.match(path.name)):
            skipped.append(f"{path.parent.name}/{path.name}: reads as a whole-exam "
                           f"compilation, which this pipeline does not split")
            continue
        classified = classify(path)
        if classified is None:
            continue
        year, school, part = classified
        paper = paper_id(year, school)
        entry = found.setdefault(paper, {"paper": paper, "school": school,
                                         "year": year, "parts": {}})
        # Two files claiming one part of one paper -- the same paper filed under
        # both layouts, say. Which one wins would come down to the sort order of
        # their names, so neither does: the part is dropped and the paper reports
        # as incomplete rather than being built from whichever came second.
        if part in entry["parts"] and entry["parts"][part] != str(path):
            skipped.append(f"{paper}: two files claim part {part} — "
                           f"{entry['parts'][part]} and {path}")
            entry["parts"][part] = None
        else:
            entry["parts"].setdefault(part, str(path))

    complete = []
    for paper, entry in sorted(found.items()):
        missing = [p for p in PARTS if not entry["parts"].get(p)]
        if missing:
            skipped.append(f"{paper}: missing {', '.join(missing)}")
            continue
        complete.append(entry)
    return complete, skipped


def ingest(papers: list[dict], dry_run: bool = False) -> list[dict]:
    """Copy each triple into papers/english/, keyed on the paper id.

    Copied rather than referenced in place for the reason CLAUDE.md section 10.2
    gives: the source is a OneDrive folder, and cloud sync can evict a file to a
    placeholder. A corpus that stops building because OneDrive reclaimed space is
    a corpus that cannot be rebuilt.
    """
    for paper in papers:
        for part, directory in PARTS.items():
            src = Path(paper["parts"][part])
            dest = ENGLISH_DIR / directory / f"{paper['paper']}.pdf"
            if dry_run:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return papers


def registry_path() -> Path:
    return ENGLISH_DIR / "registry.json"


def load_registry() -> list[dict]:
    path = registry_path()
    if not path.exists():
        return []
    return json.loads(path.read_text())["papers"]


def paper_entry(paper: str) -> dict | None:
    return next((p for p in load_registry() if p["paper"] == paper), None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be ingested without copying")
    args = parser.parse_args(argv)

    papers, skipped = discover(args.source)
    for note in skipped:
        print(f"    skipped {note}", file=sys.stderr)
    if not papers:
        print("no complete Booklet A / Booklet B / Answers triples found; the "
              "2020-2025 folders hold whole-exam compilations, which this "
              "pipeline does not split", file=sys.stderr)
        return 1

    ingest(papers, dry_run=args.dry_run)
    for paper in papers:
        print(f"{paper['paper']:28s} {paper['school']} ({paper['year']})")
    if not args.dry_run:
        registry_path().parent.mkdir(parents=True, exist_ok=True)
        registry_path().write_text(json.dumps(
            {"source": str(args.source), "papers": papers}, indent=2))
        print(f"\n{len(papers)} papers ingested into {ENGLISH_DIR}")
    else:
        print(f"\n{len(papers)} papers would be ingested (dry run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
