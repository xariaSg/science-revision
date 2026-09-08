"""Chinese Paper 2 API.

Marking is scoped to Booklet A: the paper's own OAS-answered sections, 语文应用,
短文填空 and 阅读理解一 -- the same three sections build/cn_index.py's
MCQ_SECTIONS sums to derive the "从第1题到第25题...电脑作答卷" boundary the
paper prints (CLAUDE.md section 7.5 item 0). This is a real seam already printed
on the paper: everything on this side of it is filled in on an OAS, everything
past it is written into the booklet or a separate 作答簿. 完成对话 (Q26-29) also
happens to be answered by choosing from a bank, but it is written into the
booklet rather than bubbled on the OAS, so it sits on the far side of the seam
along with the whole of 阅读理解二 -- both are permanently out of scope here.

Every question this router serves is therefore `choose`, marked against the key.
No API key, never fails. `build/cn_key.py`/`cn_rubric.py` (PSLE) and
`build/cn_prelim_key.py` (prelims) still key and rubric the whole paper --
that full-paper cross-checking is what catches a dropped question (CLAUDE.md
section 1.6.1) -- this router just never reads past the seam.

Which questions are in scope is read from each question's `section` in
questions.json, never assumed from its number: the seam lands at Q25 for
2017-2025 and the 2026 prelims, but at Q23 for 2012-2016, which numbers its
first three sections differently (CLAUDE.md section 7.3).

A paper is a string id, not a year -- ten schools sat their own 2026 prelim
(CLAUDE.md section 12), so a bare year no longer names one Chinese paper. The
PSLE ids are unchanged (`str(year)` is still a valid id), which is what keeps
every URL that worked before working, exactly as `papers.py` already does for
Science and English. `year` survives on the attempt log alongside `paper`
because the syllabus era is a property of the calendar year, but nothing here
may key a *lookup* on it: 2026-prelim-nanyang and a hypothetical 2026 PSLE
paper would share a year and collide.

Two build pipelines feed this router -- `build/cn_key.py`/`cn_rubric.py` for
the PSLE corpus, `build/cn_prelim_key.py` for the prelims -- and their
key/rubric JSON differ in a few optional fields (the PSLE key's entries carry
a `booklet` and a vocabulary-gloss `note`; the prelim key's do not, since it
never mixes in Paper 1/3 and has no gloss to show). Every read of those fields
below is `.get()`-based rather than `[...]`-indexed for that reason.

The two constraints from the Science app hold here and are worth restating,
because both are enforced by where the files sit rather than by a check:

* Only question pages are served. The answer key is unpacked to its own
  directory, `answer-pages/`, which no route reads from, so there is no URL that
  reaches it.
* The answer is always a separate, explicit request. Nothing in the question
  payload contains the correct option or the model answer, so neither can be read
  out of the page source before attempting.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import papers as paper_ids
from db import (by_paper_and_day, day_of, kinds_present, list_attempts, percent,
                save_attempt)

REPO = Path(__file__).resolve().parent.parent
WORK_CN = REPO / "work-cn"

SUBJECT = "chinese"
# The whole of Paper 2, however the year happened to bind it: 2021-2025 print one
# booklet, 2012-2020 print two (A on the OAS, B written in the booklet). Either
# way it is practised as one paper, so the column carries the paper number rather
# than Science's A/B split -- this is the DB's own booklet column, unrelated to
# the Booklet A marking scope below, which is a section boundary, not a paper one.
BOOKLET = "2"

# Booklet A: the sections the paper itself answers on an OAS rather than in the
# booklet or a 作答簿 (CLAUDE.md section 7.5 item 0). The names are constant
# across every era this corpus has (CLAUDE.md section 7.3), even though the
# question numbers the seam lands on are not -- Q25 for 2017-2025 and the 2026
# prelims, Q23 for 2012-2016 -- so the scope is read off `section`, never a
# hardcoded question range.
BOOKLET_A_SECTIONS = {"语文应用", "短文填空", "阅读理解一"}

# Every question in scope is marked the same way, so there is only one kind --
# kept as a one-element list rather than inlined so `by_paper_and_day` and
# `kinds_present` need no special-casing for Chinese's single kind.
MODE_LABELS = {"choose": "Chosen answers"}
CN_KINDS = [("choose", MODE_LABELS["choose"], "选")]

router = APIRouter(prefix="/api/chinese", tags=["chinese"])


def paper_dir(paper: str) -> Path:
    path = WORK_CN / str(paper)
    if not (path / "questions.json").exists():
        raise HTTPException(404, f"no indexed Chinese paper for {paper}")
    return path


def load_questions(paper: str) -> dict:
    return json.loads((paper_dir(paper) / "questions.json").read_text())


def load_key(paper: str) -> dict:
    path = paper_dir(paper) / "key.json"
    if not path.exists():
        raise HTTPException(
            404, f"no answer key for {paper}; run build/cn_key.py (PSLE) or "
                f"build/cn_prelim_key.py (school prelims)")
    return json.loads(path.read_text())


def indexed_papers() -> list[str]:
    return paper_ids.discover(WORK_CN)


def booklet_a_questions(paper: str) -> list[dict]:
    """The paper's Booklet A questions only -- see the module docstring."""
    return [q for q in load_questions(paper)["questions"]
            if q["section"] in BOOKLET_A_SECTIONS]


def _question(paper: str, number: int) -> dict:
    entry = next((q for q in booklet_a_questions(paper)
                  if q["question"] == number), None)
    if entry is None:
        raise HTTPException(404, f"no Q{number} in {paper}'s Booklet A")
    return entry


def _key_entry(paper: str, number: int) -> dict:
    # `booklet` is absent from a prelim key's entries -- there is no Paper 1/3 to
    # scope away in the first place (CLAUDE.md section 12.2) -- so a missing key
    # defaults to "paper2" rather than being required.
    entry = next((e for e in load_key(paper)["entries"]
                  if e.get("booklet", "paper2") == "paper2"
                  and e["question"] == number), None)
    if entry is None:
        raise HTTPException(404, f"no answer key for Q{number}")
    return entry


@router.get("/papers")
def papers() -> list[dict]:
    out = []
    for paper in indexed_papers():
        data = load_questions(paper)
        booklet_a = booklet_a_questions(paper)
        out.append({
            **paper_ids.describe(paper),
            "questions": len(booklet_a),
            "marks": sum(q["marks"] or 0 for q in booklet_a),
            "pages": data["num_pages"],
            "needs_review": data["needs_review"],
        })
    return out


def page_sizes(paper: str) -> list[dict]:
    """Rendered pixel size of every page, for the UI to reserve layout with.

    Page images are lazy-loaded -- the paper is 19MB at 300 dpi and loading it
    all up front is a slow first paint. But a lazy image occupies no height until
    it loads, so without an intrinsic size every unloaded page collapses and
    "jump to page 15" computes an offset near the top of the document. Read from
    the manifest rather than assumed uniform: these are A4 scans today, but the
    corpus is not consistent about much (CLAUDE.md section 1.1).

    The manifest's own key for this differs by pipeline -- `cn_unpack.py` (PSLE)
    calls it "paper", `cn_prelim_unpack.py` calls it "paper_pdf" so the field
    holding the paper's *id* could be named "paper" instead -- so both are tried.
    """
    manifest = paper_dir(paper) / "manifest.json"
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text())
    pages = (data.get("paper") if isinstance(data.get("paper"), dict)
            else data.get("paper_pdf", {})).get("pages", [])
    return [{"page": p["page_number"], "width": p["width"], "height": p["height"]}
            for p in pages]


@router.get("/papers/{paper}/questions")
def questions(paper: str) -> dict:
    data = load_questions(paper)
    return {
        **paper_ids.describe(paper),
        "pages": data["num_pages"],
        "page_sizes": page_sizes(paper),
        "sections": [s for s in data["sections"]
                    if s["section"] in BOOKLET_A_SECTIONS],
        # Every group so far belongs to 阅读理解二, past the Booklet A seam --
        # this comes back empty today, not hardcoded to, so a future group
        # inside Booklet A would still show up.
        "groups": [g for g in data["groups"] if g["section"] in BOOKLET_A_SECTIONS],
        "questions": [
            {"question": q["question"], "page": q["page"], "section": q["section"],
             "group": q["group"], "marks": q["marks"], "options": q["options"],
             "response_mode": q["response_mode"]}
            for q in booklet_a_questions(paper)
        ],
    }


@router.get("/papers/{paper}/pages/{page}")
def page_image(paper: str, page: int) -> FileResponse:
    data = load_questions(paper)
    if not 1 <= page <= data["num_pages"]:
        raise HTTPException(404, "page not found")
    path = paper_dir(paper) / "pages" / f"page-{page:03d}.png"
    if not path.exists():
        raise HTTPException(404, "page not found")
    return FileResponse(path, media_type="image/png")


@router.post("/papers/{paper}/answer/{question}")
def answer_choose(paper: str, question: int, payload: dict) -> dict:
    """Mark one chosen answer against the key, and log it."""
    entry = _question(paper, question)
    if entry["response_mode"] != "choose":
        raise HTTPException(400, f"Q{question} is not a chosen-answer question")

    options = entry["options"] or 4
    choice = payload.get("choice")
    if not isinstance(choice, int) or not 1 <= choice <= options:
        raise HTTPException(400, f"choose one of options 1 to {options}")

    key = _key_entry(paper, question)
    if key["option"] is None:
        raise HTTPException(409, f"the key for Q{question} could not be read")

    marks_total = entry["marks"] or 0
    correct = choice == key["option"]
    marks = marks_total if correct else 0

    save_attempt({
        "subject": SUBJECT, "paper": paper, "year": paper_ids.year_of(paper),
        "booklet": BOOKLET,
        "question": question, "part": None, "mode": "choose",
        "answer": str(choice), "marks": marks, "marks_total": marks_total,
        "graded": True,
    })
    return {
        "question": question, "choice": choice, "answer": key["option"],
        "correct": correct, "marks": marks, "marks_total": marks_total,
        # The vocabulary gloss doubles as the teaching note on the MCQ sections.
        # A prelim key has no gloss field at all (CLAUDE.md section 12.2).
        "note": key.get("note") or key.get("model_answer"),
        "source": load_key(paper)["source"],
        "authoritative": load_key(paper)["authoritative"],
    }


@router.get("/papers/{paper}/score")
def score(paper: str) -> dict:
    """Marks across Booklet A, best attempt per question."""
    slots = {q["question"]: q["marks"] or 0 for q in booklet_a_questions(paper)}

    best: dict[int, int] = {}
    for row in _attempts(paper):
        if row["marks"] is None:
            continue
        best[row["question"]] = max(best.get(row["question"], 0), int(row["marks"]))

    return {
        **paper_ids.describe(paper),
        "earned": sum(best.values()),
        "available": sum(slots.values()),
        "attempted": len(best),
        "slots": len(slots),
        "per_question": best,
    }


def _attempts(paper: str | None) -> list[dict]:
    """Every logged Chinese attempt within Booklet A, uncapped.

    Booklet A alone is up to 25 questions, so `list_attempts`' default cap of
    200 is a handful of sittings -- and it drops the oldest rows, which is
    where both the best attempt at a question and the start of a trend live.

    Filtered to Booklet A's own question numbers, not just by paper: sittings
    logged before marking was scoped here run past the seam (a 2024 paper in
    this app's own log has real answers out to Q32), and every consumer of
    this function -- score(), _progress(), paper_day_attempts() -- sums marks
    and totals in the same pass, so a row past the seam would inflate "earned"
    against an "available" that no longer counts it, or push "attempted"/
    "untouched" out of step with `slots`. Filtering once here, rather than in
    each caller, is what keeps all of them honest at once.

    Filtered by paper id rather than by year: several 2026 Chinese papers now
    share that year (CLAUDE.md section 12), so a year no longer selects one
    paper's rows the way it always used to.
    """
    wanted = [paper] if paper is not None else indexed_papers()
    in_scope = {p: {q["question"] for q in booklet_a_questions(p)} for p in wanted}
    return [row for p in wanted
            for row in list_attempts(paper=p, booklet=BOOKLET, subject=SUBJECT,
                                     limit=None)
            if row["question"] in in_scope[p]]


def _modes(papers: list[str]) -> dict[tuple[str, int], str]:
    """How each in-scope question is answered, read from the index.

    Scoped to Booklet A on purpose: a question past the seam is always
    `choose` in the index too (完成对话's bank blanks, CLAUDE.md 7.5), but it is
    out of marking scope, so it must not be counted as a `choose` attempt here
    -- any attempt logged against it (from before this scope existed) simply
    finds no mode and drops out of every rollup below, which is what "out of
    scope" should mean.

    Keyed on the paper id, not the attempt's `year` column: 2026-prelim-nanyang
    and any other 2026 Chinese paper would otherwise collide on that year and
    merge one paper's Q7 into another's (CLAUDE.md section 10.1's warning,
    which now applies here too).
    """
    return {(p, q["question"]): q["response_mode"]
            for p in papers for q in booklet_a_questions(p)}


@router.get("/papers/{paper}/attempts/{date}")
def paper_day_attempts(paper: str, date: str) -> dict:
    """What one bar on the chart is made of: every answer given to one paper on
    one day, grouped the way the bar is split.

    Science's equivalent is main.paper_day_attempts, and the same reasoning about
    the key applies -- only questions attempted that day come back, and a chosen
    answer shows its correct option at the moment it is marked, so nothing here
    was not already seen.
    """
    rows = sorted((row for row in _attempts(paper) if day_of(row) == date),
                  key=lambda row: row["id"])
    mode_of = _modes([paper])

    # A key that could not be read leaves `option` None (CLAUDE.md 7.5); the
    # answers are still worth listing, just without the option beside them.
    correct_option = {entry["question"]: entry["option"]
                      for entry in load_key(paper)["entries"]
                      if entry.get("booklet", "paper2") == "paper2"}

    groups = []
    for kind_id, name, short in CN_KINDS:
        members = [row for row in rows
                   if mode_of.get((row["paper"], row["question"])) == kind_id]
        if not members:
            continue
        earned = sum(row["marks"] or 0 for row in members)
        possible = sum(row["marks_total"] or 0 for row in members)
        groups.append({
            "id": kind_id, "name": name, "short": short,
            "kind": "choice" if kind_id == "choose" else "written",
            "earned": earned, "possible": possible,
            "percent": percent(earned, possible), "attempts": len(members),
            "rows": [_attempt_row(row, kind_id, correct_option) for row in members],
        })

    return {
        "subject": SUBJECT, **paper_ids.describe(paper), "date": date,
        "earned": sum(row["marks"] or 0 for row in rows),
        "possible": sum(row["marks_total"] or 0 for row in rows),
        "groups": groups,
    }


def _attempt_row(row: dict, kind_id: str, correct_option: dict[int, int]) -> dict:
    """One logged answer, shaped for reading rather than for re-marking."""
    marks, total = row["marks"], row["marks_total"]
    chosen = row["answer"] if kind_id == "choose" else None
    return {
        "question": row["question"],
        "part": None,
        "label": f"Q{row['question']}",
        "at": row["created_at"],
        "mode": row["mode"],
        "chose": chosen,
        "answer": None if chosen else row["answer"],
        "correct_option": correct_option.get(row["question"]) if chosen else None,
        "marks": marks,
        "marks_total": total,
        "correct": None if marks is None or not total else marks >= total,
        # A chosen answer is always graded the moment it is saved (answer_choose
        # never logs an ungraded attempt), so `marks` is only ever None here for
        # a row logged before marking was scoped to Booklet A.
        "graded": bool(row["graded"]),
        "awaiting": marks is None,
    }


@router.get("/papers/{paper}/progress")
def paper_progress(paper: str) -> dict:
    """Progress on one Chinese paper."""
    return _progress(paper)


@router.get("/progress")
def progress_all() -> dict:
    """Progress across every Chinese paper."""
    return _progress(None)


def _progress(paper: str | None) -> dict:
    """Chinese progress: the chart, plus where in Booklet A the marks are lost.

    Deliberately not the Science report with the names changed. There are no
    chains to break, no facets to miss and no contextual gate to fail
    (CLAUDE.md 7.6), so the weak-area rollup is by section, over Booklet A's
    three -- which is the unit a Chinese teacher would name anyway. The mode
    rollup alongside it only ever has one entry now that marking is scoped to
    Booklet A (`choose` throughout), but it is kept rather than special-cased
    away, matching CN_KINDS above.
    """
    from collections import defaultdict

    wanted = [paper] if paper is not None else indexed_papers()
    rows = _attempts(paper)

    # Which section each question belongs to, across the papers in view. A
    # property of the paper, so it is read from the index rather than logged
    # with the attempt -- as is the response mode, for a sharper reason (_modes).
    section_of: dict[tuple[str, int], str] = {}
    slots = 0
    for p in wanted:
        for q in booklet_a_questions(p):
            section_of[(p, q["question"])] = q["section"]
            slots += 1
    mode_of = _modes(wanted)

    section_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    mode_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    best: dict[tuple[str, int], dict] = {}
    # A chosen answer is never logged unmarked (answer_choose always grades it),
    # so this only ever picks up rows from before marking was scoped to Booklet
    # A. Counted by question rather than by row -- three tries at one question
    # is one thing to go back to.
    awaiting: set[tuple[str, int]] = set()

    for row in rows:
        key = (row["paper"], row["question"])
        if row["marks"] is None:
            awaiting.add(key)
            continue
        if key not in best or row["marks"] > best[key]["marks"]:
            best[key] = row

    awaiting -= best.keys()

    # Best attempt only, for the same reason Science uses it: the report should say
    # what she can do now, not hold the first try against her.
    for key, row in best.items():
        for stat, name in ((section_stat, section_of.get(key)),
                           (mode_stat, MODE_LABELS.get(mode_of.get(key, "")))):
            if not name:
                continue
            stat[name]["earned"] += row["marks"]
            stat[name]["possible"] += row["marks_total"] or 0
            stat[name]["attempts"] += 1

    def ranked(stat: dict, order: list[str] | None = None) -> list[dict]:
        out = [{"name": name, **v,
                "percent": round(v["earned"] / v["possible"] * 100) if v["possible"] else 0}
               for name, v in stat.items() if v["possible"]]
        if order:  # sections read in the order the paper prints them
            return sorted(out, key=lambda d: order.index(d["name"]))
        return sorted(out, key=lambda d: (d["percent"], -d["possible"]))

    printed_order = [s["section"] for p in wanted
                     for s in load_questions(p)["sections"]
                     if s["section"] in BOOKLET_A_SECTIONS]
    seen: dict[str, None] = {}
    for name in printed_order:
        seen.setdefault(name, None)

    chart_papers = by_paper_and_day(
        rows, CN_KINDS, lambda row: mode_of.get((row["paper"], row["question"])))
    # The chart labels a bar with the paper it came from. A PSLE Chinese paper is
    # named by its year, so the id already reads fine; a prelim's id is not its
    # name, so the school's own label is used instead -- matching Science's
    # main._progress exactly, down to using the same describe() rather than a
    # narrower label()-only lookup, so a later frontend change wanting `group`
    # or `prelim` on a bar needs no server change to get it.
    for entry in chart_papers:
        entry.update(paper_ids.describe(entry["paper"]))
    return {
        "subject": "chinese",
        "papers_indexed": [paper_ids.describe(p) for p in wanted],
        "papers": chart_papers,
        "kinds": kinds_present(chart_papers, CN_KINDS),
        "sections": ranked(section_stat, list(seen)),
        "modes": ranked(mode_stat),
        "slots": slots,
        # Attempted but unmarked still counts as touched.
        "untouched": slots - len(best.keys() | awaiting),
        "unmarked": len(awaiting),
        "total_attempts": len(rows),
    }
