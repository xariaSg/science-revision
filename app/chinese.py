"""Chinese Paper 2 API.

Paper 2 is one booklet, so unlike Science there is no Booklet A/B choice to make
-- the whole paper loads at once and each question carries its own way of being
answered:

  choose       Q1-Q32. Marked against the key. No API key, never fails.
  typed        Q34-Q40. Marked against keypoints the publisher printed.
  self_marked  Q33. Shown with its model answer; the student awards the mark.

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
from db import list_attempts, save_attempt

REPO = Path(__file__).resolve().parent.parent
WORK_CN = REPO / "work-cn"

SUBJECT = "chinese"
# Paper 2 is a single booklet; the column exists for Science's A/B split.
BOOKLET = "2"

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
        "subject": SUBJECT, "year": year, "booklet": BOOKLET,
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
            "subject": SUBJECT, "year": year, "booklet": BOOKLET,
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
            "subject": SUBJECT, "year": year, "booklet": BOOKLET,
            "question": question, "part": None, "mode": "typed", "answer": text,
            "marks": None, "marks_total": marks_total, "graded": False,
        })
        return {"question": question, "graded": False, "reason": str(exc),
                "marks_total": marks_total}

    save_attempt({
        "subject": SUBJECT, "year": year, "booklet": BOOKLET,
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
        "subject": SUBJECT, "year": year, "booklet": BOOKLET,
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
    for row in list_attempts(year=year, booklet=BOOKLET, subject=SUBJECT):
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
