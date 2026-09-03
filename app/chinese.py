"""Chinese Paper 2 API.

Unlike Science there is no Booklet A/B choice to make: 2012-2020 do print Paper 2
as two booklets, but they are sat as one paper and are served that way, so the
whole thing loads at once and each question carries its own way of being answered:

  choose       marked against the key. No API key, never fails.
  typed        marked against keypoints the publisher printed.
  self_marked  shown with its model answer; the student awards the mark.

Which question is which is read from questions.json, never assumed from its
number: 2021-2025 run Q1-Q32 chosen, Q34-Q40 typed and Q33 self-marked, but
2012-2016 have 41 questions and no chosen ones past Q28 (CLAUDE.md section 7.5).

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

from cn_grade import GradingUnavailable, grade
from db import (by_paper_and_day, day_of, kinds_present, list_attempts, percent,
                save_attempt)

REPO = Path(__file__).resolve().parent.parent
WORK_CN = REPO / "work-cn"

SUBJECT = "chinese"
# The whole of Paper 2, however the year happened to bind it: 2021-2025 print one
# booklet, 2012-2020 print two (A on the OAS, B written in the booklet). Either
# way it is practised as one paper, so the column carries the paper number rather
# than Science's A/B split.
BOOKLET = "2"

# The three response modes, said in a way a child can read. Kept here rather than
# in the front end because the progress report groups by them.
MODE_LABELS = {
    "choose": "Chosen answers",
    "typed": "Written answers",
    "self_marked": "Self-marked",
}

# The same split Science makes between its two booklets (main.SCIENCE_KINDS), drawn
# from what the paper asks for rather than from how it is bound: Paper 2 is one
# sitting, but choosing an option and writing an answer are close to two different
# skills, and a chart bar that sums them says which morning was good without saying
# which half of it was. `short` is a single character because it has to fit inside
# a chart segment; it is the first character of what the mode is called in Chinese
# -- 选 chosen, 写 written, 自 self-marked.
CN_KINDS = [("choose", MODE_LABELS["choose"], "选"),
            ("typed", MODE_LABELS["typed"], "写"),
            ("self_marked", MODE_LABELS["self_marked"], "自")]

router = APIRouter(prefix="/api/chinese", tags=["chinese"])


def paper_dir(year: int) -> Path:
    path = WORK_CN / str(year)
    if not (path / "questions.json").exists():
        raise HTTPException(404, f"no indexed Chinese paper for {year}")
    return path


def load_questions(year: int) -> dict:
    return json.loads((paper_dir(year) / "questions.json").read_text())


def load_key(year: int) -> dict:
    path = paper_dir(year) / "key.json"
    if not path.exists():
        raise HTTPException(404, f"no answer key for {year}; run build/cn_key.py")
    return json.loads(path.read_text())


def load_rubrics(year: int) -> dict:
    path = paper_dir(year) / "rubrics.json"
    if not path.exists():
        raise HTTPException(404, f"no rubrics for {year}; run build/cn_rubric.py")
    return json.loads(path.read_text())


def indexed_years() -> list[int]:
    if not WORK_CN.exists():
        return []
    return sorted(int(p.name) for p in WORK_CN.iterdir()
                  if p.is_dir() and p.name.isdigit()
                  and (p / "questions.json").exists())


def _question(year: int, number: int) -> dict:
    entry = next((q for q in load_questions(year)["questions"]
                  if q["question"] == number), None)
    if entry is None:
        raise HTTPException(404, f"no Q{number} in the {year} paper")
    return entry


def _key_entry(year: int, number: int) -> dict:
    entry = next((e for e in load_key(year)["entries"]
                  if e["booklet"] == "paper2" and e["question"] == number), None)
    if entry is None:
        raise HTTPException(404, f"no answer key for Q{number}")
    return entry


def _rubric(year: int, number: int) -> dict:
    entry = next((r for r in load_rubrics(year)["rubrics"]
                  if r["question"] == number), None)
    if entry is None:
        raise HTTPException(404, f"no rubric for Q{number}")
    return entry


@router.get("/papers")
def papers() -> list[dict]:
    out = []
    for year in indexed_years():
        data = load_questions(year)
        out.append({
            "year": year,
            "questions": len(data["questions"]),
            "marks": sum(q["marks"] or 0 for q in data["questions"]),
            "pages": data["num_pages"],
            "needs_review": data["needs_review"],
        })
    return out


def page_sizes(year: int) -> list[dict]:
    """Rendered pixel size of every page, for the UI to reserve layout with.

    Page images are lazy-loaded -- the paper is 19MB at 300 dpi and loading it
    all up front is a slow first paint. But a lazy image occupies no height until
    it loads, so without an intrinsic size every unloaded page collapses and
    "jump to page 15" computes an offset near the top of the document. Read from
    the manifest rather than assumed uniform: these are A4 scans today, but the
    corpus is not consistent about much (CLAUDE.md section 1.1).
    """
    manifest = paper_dir(year) / "manifest.json"
    if not manifest.exists():
        return []
    return [{"page": p["page_number"], "width": p["width"], "height": p["height"]}
            for p in json.loads(manifest.read_text())["paper"]["pages"]]


@router.get("/papers/{year}/questions")
def questions(year: int) -> dict:
    data = load_questions(year)
    return {
        "year": year,
        "pages": data["num_pages"],
        "page_sizes": page_sizes(year),
        "sections": data["sections"],
        "groups": data["groups"],
        "questions": [
            {"question": q["question"], "page": q["page"], "section": q["section"],
             "group": q["group"], "marks": q["marks"], "options": q["options"],
             "response_mode": q["response_mode"]}
            for q in data["questions"]
        ],
    }


@router.get("/papers/{year}/pages/{page}")
def page_image(year: int, page: int) -> FileResponse:
    data = load_questions(year)
    if not 1 <= page <= data["num_pages"]:
        raise HTTPException(404, "page not found")
    path = paper_dir(year) / "pages" / f"page-{page:03d}.png"
    if not path.exists():
        raise HTTPException(404, "page not found")
    return FileResponse(path, media_type="image/png")


@router.post("/papers/{year}/answer/{question}")
def answer_choose(year: int, question: int, payload: dict) -> dict:
    """Mark one chosen answer against the key, and log it."""
    entry = _question(year, question)
    if entry["response_mode"] != "choose":
        raise HTTPException(400, f"Q{question} is not a chosen-answer question")

    options = entry["options"] or 4
    choice = payload.get("choice")
    if not isinstance(choice, int) or not 1 <= choice <= options:
        raise HTTPException(400, f"choose one of options 1 to {options}")

    key = _key_entry(year, question)
    if key["option"] is None:
        raise HTTPException(409, f"the key for Q{question} could not be read")

    marks_total = entry["marks"] or 0
    correct = choice == key["option"]
    marks = marks_total if correct else 0

    save_attempt({
        "subject": SUBJECT, "paper": str(year), "year": year,
        "booklet": BOOKLET,
        "question": question, "part": None, "mode": "choose",
        "answer": str(choice), "marks": marks, "marks_total": marks_total,
        "graded": True,
    })
    return {
        "question": question, "choice": choice, "answer": key["option"],
        "correct": correct, "marks": marks, "marks_total": marks_total,
        # The vocabulary gloss doubles as the teaching note on the MCQ sections.
        "note": key["note"] or key["model_answer"],
        "source": load_key(year)["source"],
        "authoritative": load_key(year)["authoritative"],
    }


@router.post("/papers/{year}/written/{question}")
def answer_written(year: int, question: int, payload: dict) -> dict:
    """Mark one typed answer against its keypoints, and log it.

    Grading is optional (CLAUDE.md section 2.2): when it is unavailable the
    attempt is still logged, ungraded, and the caller is told to self-mark.
    """
    entry = _question(year, question)
    if entry["response_mode"] != "typed":
        raise HTTPException(400, f"Q{question} is not a typed question")

    text = (payload.get("answer") or "").strip()
    if not text:
        raise HTTPException(400, "no answer to mark")

    rubric = _rubric(year, question)
    marks_total = entry["marks"] or 0

    if not rubric["auto_marked"]:
        save_attempt({
            "subject": SUBJECT, "paper": str(year), "year": year,
        "booklet": BOOKLET,
            "question": question, "part": None, "mode": "typed", "answer": text,
            "marks": None, "marks_total": marks_total, "graded": False,
        })
        return {"question": question, "graded": False,
                "reason": "this question is not auto-marked",
                "marks_total": marks_total}

    try:
        result = grade(text, rubric)
    except GradingUnavailable as exc:
        save_attempt({
            "subject": SUBJECT, "paper": str(year), "year": year,
        "booklet": BOOKLET,
            "question": question, "part": None, "mode": "typed", "answer": text,
            "marks": None, "marks_total": marks_total, "graded": False,
        })
        return {"question": question, "graded": False, "reason": str(exc),
                "marks_total": marks_total}

    save_attempt({
        "subject": SUBJECT, "paper": str(year), "year": year,
        "booklet": BOOKLET,
        "question": question, "part": None, "mode": "typed", "answer": text,
        "marks": result.marks, "marks_total": result.marks_total, "graded": True,
        "outcomes": result.verdicts,
    })
    return {
        "question": question, "graded": True, "marks": result.marks,
        "marks_total": result.marks_total, "verdicts": result.verdicts,
        "feedback": result.feedback, "method": result.method,
        "model_answer": result.model_answer, "note": result.note,
        "source": load_rubrics(year)["source"],
        "authoritative": load_rubrics(year)["authoritative"],
    }


@router.get("/papers/{year}/model/{question}")
def model_answer(year: int, question: int) -> dict:
    """The model answer, as its own explicit request."""
    entry = _question(year, question)
    rubric = _rubric(year, question)
    return {
        "question": question,
        "marks": entry["marks"],
        "model_answer": rubric["model_answer"],
        "note": rubric["note"],
        "keypoints": rubric["keypoints"],
        "free_response": rubric["free_response"],
        "mark_scheme": rubric["mark_scheme"],
        "auto_marked": rubric["auto_marked"],
        "source": rubric["source"],
        "authoritative": rubric["authoritative"],
    }


@router.post("/papers/{year}/self-mark/{question}")
def self_mark(year: int, question: int, payload: dict) -> dict:
    """Log an attempt the student marked themselves."""
    entry = _question(year, question)
    marks_total = entry["marks"] or 0
    marks = payload.get("marks")
    if not isinstance(marks, (int, float)) or not 0 <= marks <= marks_total:
        raise HTTPException(400, f"award between 0 and {marks_total} marks")

    save_attempt({
        "subject": SUBJECT, "paper": str(year), "year": year,
        "booklet": BOOKLET,
        "question": question, "part": None, "mode": "typed",
        "answer": (payload.get("answer") or "").strip() or "(self-marked)",
        "marks": int(marks), "marks_total": marks_total, "graded": False,
    })
    return {"question": question, "marks": int(marks), "marks_total": marks_total,
            "self_marked": True}


@router.get("/papers/{year}/score")
def score(year: int) -> dict:
    """Marks across the whole paper, best attempt per question."""
    data = load_questions(year)
    slots = {q["question"]: q["marks"] or 0 for q in data["questions"]}

    best: dict[int, int] = {}
    for row in _attempts(year):
        if row["marks"] is None:
            continue
        best[row["question"]] = max(best.get(row["question"], 0), int(row["marks"]))

    return {
        "year": year,
        "earned": sum(best.values()),
        "available": sum(slots.values()),
        "attempted": len(best),
        "slots": len(slots),
        "per_question": best,
    }


def _attempts(year: int | None) -> list[dict]:
    """Every logged Chinese attempt, uncapped.

    The paper is 40 questions, so `list_attempts`' default cap of 200 is two
    sittings -- and it drops the oldest rows, which is where both the best
    attempt at a question and the start of a trend live.
    """
    years = [year] if year is not None else indexed_years()
    return [row for y in years
            for row in list_attempts(paper=str(y), booklet=BOOKLET, subject=SUBJECT,
                                     limit=None)]


def _modes(years: list[int]) -> dict[tuple[int, int], str]:
    """How each question is answered, read from the index.

    Not from the attempt's own `mode` column, which cannot tell the difference:
    a self-marked answer is logged as `typed`, because that is how it was given.
    Only the paper knows that Q33 is a writing task the student marks herself.
    """
    return {(y, q["question"]): q["response_mode"]
            for y in years for q in load_questions(y)["questions"]}


@router.get("/papers/{year}/attempts/{date}")
def paper_day_attempts(year: int, date: str) -> dict:
    """What one bar on the chart is made of: every answer given to one paper on
    one day, grouped the way the bar is split.

    Science's equivalent is main.paper_day_attempts, and the same reasoning about
    the key applies -- only questions attempted that day come back, and a chosen
    answer shows its correct option at the moment it is marked, so nothing here
    was not already seen.
    """
    rows = sorted((row for row in _attempts(year) if day_of(row) == date),
                  key=lambda row: row["id"])
    mode_of = _modes([year])

    # A key that could not be read leaves `option` None (CLAUDE.md 7.5); the
    # answers are still worth listing, just without the option beside them.
    correct_option = {entry["question"]: entry["option"]
                      for entry in load_key(year)["entries"]
                      if entry["booklet"] == "paper2"}

    groups = []
    for kind_id, name, short in CN_KINDS:
        members = [row for row in rows
                   if mode_of.get((row["year"], row["question"])) == kind_id]
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
        "subject": SUBJECT, "year": year, "date": date,
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
        # A written answer submitted while grading was unavailable, or from a year
        # whose key prints no mark points: logged, unmarked, still to be looked at.
        "graded": bool(row["graded"]),
        "awaiting": marks is None,
    }


@router.get("/papers/{year}/progress")
def paper_progress(year: int) -> dict:
    """Progress on one Chinese paper."""
    return _progress(year)


@router.get("/progress")
def progress_all() -> dict:
    """Progress across every Chinese paper."""
    return _progress(None)


def _progress(year: int | None) -> dict:
    """Chinese progress: the chart, plus where in the paper the marks are lost.

    Deliberately not the Science report with the names changed. There are no
    chains to break, no facets to miss and no contextual gate to fail
    (CLAUDE.md 7.6), so the weak-area rollup is by the paper's own five sections
    -- which is the unit a Chinese teacher would name anyway -- and by how the
    question is answered, because 语文应用's chosen answers and B组's written
    ones are close to two different skills sharing a paper.
    """
    from collections import defaultdict

    years = [year] if year is not None else indexed_years()
    rows = _attempts(year)

    # Which section each question belongs to, across the years in view. A property
    # of the paper, so it is read from the index rather than logged with the
    # attempt -- as is the response mode, for a sharper reason (see _modes).
    section_of: dict[tuple[int, int], str] = {}
    slots = 0
    for y in years:
        for q in load_questions(y)["questions"]:
            section_of[(y, q["question"])] = q["section"]
            slots += 1
    mode_of = _modes(years)

    section_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    mode_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    best: dict[tuple[int, int], dict] = {}
    # A typed answer from 2021-2022, or one logged while grading was unavailable:
    # submitted, never marked, and waiting to be self-marked. Counted by question
    # rather than by row -- three tries at one question is one thing to go back
    # to, and a question that has since been self-marked is not waiting at all,
    # even though its ungraded first attempt is still in the log.
    awaiting: set[tuple[int, int]] = set()

    for row in rows:
        key = (row["year"], row["question"])
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

    printed_order = [s["section"] for y in years
                     for s in load_questions(y)["sections"]]
    seen: dict[str, None] = {}
    for name in printed_order:
        seen.setdefault(name, None)

    papers = by_paper_and_day(
        rows, CN_KINDS, lambda row: mode_of.get((row["year"], row["question"])))
    # The chart labels a bar with the paper it came from. A Chinese paper is
    # named by its year, so the label is the id; Science has to look its up
    # because a school prelim's id is not its name.
    for entry in papers:
        entry["label"] = entry["paper"]
    return {
        "subject": "chinese",
        "years": sorted(years),
        "papers": papers,
        "kinds": kinds_present(papers, CN_KINDS),
        "sections": ranked(section_stat, list(seen)),
        "modes": ranked(mode_stat),
        "slots": slots,
        # Attempted but unmarked still counts as touched.
        "untouched": slots - len(best.keys() | awaiting),
        "unmarked": len(awaiting),
        "total_attempts": len(rows),
    }
