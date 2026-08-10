"""FastAPI app: practise a PSLE Science paper against its original scanned pages.

Both booklets, sharing the same shape -- the student picks a question, reads it off
the scan, and answers it beside the page:

* Booklet B is open-ended. The answer is spoken or typed, transcribed locally, and
  marked against a rubric (or self-marked when grading is unavailable).
* Booklet A is multiple choice. The answer is one of four options, marked against
  the answer key, which needs no API key and never fails.

Two deliberate constraints, and they apply to both:

* Only question pages are served. The papers also contain the answer pages, and
  serving whole papers would put the answers one URL guess away.
* The answer is a separate, explicit request -- the model answer for Booklet B, the
  correct option for Booklet A. Neither is in the question payload, so neither can
  be read out of the page source before attempting.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import chinese
from db import by_paper_and_day, init_db, list_attempts, save_attempt
from grade import GradingUnavailable, grade
from stt import transcribe_bytes, model_name

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"
# The backfilled papers were unpacked as Booklet B only, so they live here rather
# than in work/, which holds the two full-paper unpacks the pipeline was built on.
# Each paper's questions.json numbers its own pages, so the two roots need no
# reconciling — only searching in order, with work/ winning if a year is in both.
WORK_ROOTS = (WORK_DIR, REPO / "work-b")
# Booklet A: the question inventory sits with the rendered pages, the answer key
# with the answer pages it was read from.
WORK_A = REPO / "work-a"
WORK_ANS = REPO / "work-ans"
RUBRIC_DIR = REPO / "rubrics"
FLAGS_FILE = REPO / "review" / "flags.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

def _load_env_file(path: Path = REPO / ".env") -> None:
    """Read .env into the environment before anything reads a key from it.

    Kept to a few lines rather than a dependency: this is one file, read once, on
    a local single-user app. Values already set in the real environment win, so
    an exported key still overrides the file.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_env_file()

app = FastAPI(title="PSLE practice")
app.include_router(chinese.router)


# Science splits into two booklets that are practised separately; Chinese Paper 2
# is one booklet and loads whole. The UI branches on `modes`, so adding a subject
# does not mean teaching the front end a new special case.
SUBJECTS = [
    {
        "id": "science",
        "label": "Science",
        "modes": [
            {"id": "A", "label": "Booklet A", "hint": "multiple choice"},
            {"id": "B", "label": "Booklet B", "hint": "written"},
        ],
    },
    {
        "id": "chinese",
        "label": "华文 Chinese",
        "modes": [],
    },
]


@app.get("/api/subjects")
def subjects() -> list[dict]:
    """Which subjects have papers indexed, and how each is practised."""
    years = {
        "science": sorted(set(indexed_years()) | set(mcq_years())),
        "chinese": chinese.indexed_years(),
    }
    return [{**subject, "years": years.get(subject["id"], [])}
            for subject in SUBJECTS if years.get(subject["id"])]


def paper_dir(year: int) -> Path:
    for root in WORK_ROOTS:
        path = root / str(year)
        if (path / "questions.json").exists():
            return path
    raise HTTPException(404, f"no indexed paper for {year}")


def indexed_years() -> list[int]:
    """Every year with a question inventory, across both work roots."""
    years: dict[int, None] = {}
    for root in WORK_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            if (path.is_dir() and path.name.isdigit()
                    and (path / "questions.json").exists()):
                years.setdefault(int(path.name), None)
    return sorted(years)


def load_questions(year: int) -> dict:
    return json.loads((paper_dir(year) / "questions.json").read_text())


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/papers")
def papers() -> list[dict]:
    out = []
    for year in indexed_years():
        data = load_questions(year)
        out.append({
            "year": data["year"],
            "questions": len(data["questions"]),
            "marks": data["counted_marks"],
            "stated_marks": data["stated_total_marks"],
            "needs_review": data["needs_review"],
        })
    return out


@app.get("/api/papers/{year}/questions")
def questions(year: int) -> dict:
    data = load_questions(year)
    # Some sub-parts are answered by drawing on the paper. Answering them aloud is
    # not possible, so the UI needs to know before it offers a microphone.
    drawn: set[tuple[int, str | None]] = set()
    rubric_path = RUBRIC_DIR / f"{year}.json"
    if rubric_path.exists():
        for rubric in json.loads(rubric_path.read_text())["rubrics"]:
            if rubric.get("response_mode") == "drawn":
                drawn.add((rubric["question"], rubric["part"]))
    return {
        "year": data["year"],
        "booklet_b": data["booklet_b"],
        "questions": [
            {
                "question": q["question"],
                "pages": q["pages"],
                "total_marks": q["total_marks"],
                # Parents of nested sub-parts are headings, not answerable slots.
                "parts": [
                    {"part": p["part"], "marks": p["marks"],
                     "drawn": (q["question"], p["part"]) in drawn,
                     "uncertain": p["marks"] is None or p.get("marks_source") == "repair"}
                    for p in q["parts"] if not p.get("is_parent")
                ],
            }
            for q in data["questions"]
        ],
    }


@app.get("/api/papers/{year}/pages/{page}")
def page_image(year: int, page: int) -> FileResponse:
    data = load_questions(year)
    booklet_b = data["booklet_b"]
    if not booklet_b["start"] <= page <= booklet_b["end"]:
        # The answer pages live in the same directory; never serve outside Booklet B.
        raise HTTPException(403, "only Booklet B pages are available")
    path = paper_dir(year) / "pages" / f"page-{page:03d}.png"
    if not path.exists():
        raise HTTPException(404, "page not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/papers/{year}/answers/{question}")
def answer(year: int, question: int) -> dict:
    """The suggested answer, requested explicitly after an attempt.

    Served as text from the rubrics rather than as image crops of the answer page.
    The crops came from the tesseract pass and were the only trustworthy form back
    when the OCR text was a draft full of errors; the Vision extraction that
    replaced it is accurate, so text is now both correct and more useful — it
    reflows, it is selectable, and it separates the model answer from the
    explanation, which the crop could not.

    The explanation is returned as its own field so the UI can hold it back until
    after the mark: the model answer drives the marking, the explanation drives the
    teaching (CLAUDE.md 1.6).
    """
    path = RUBRIC_DIR / f"{year}.json"
    if not path.exists():
        raise HTTPException(404, "no answers extracted for this paper")
    data = json.loads(path.read_text())
    parts = [r for r in data["rubrics"] if r["question"] == question]
    if not parts:
        raise HTTPException(404, f"no answer for Q{question}")
    return {
        "question": question,
        "source": data.get("source", "EPH suggested answer"),
        "parts": [{"part": r["part"],
                   "text": r.get("model_answer", ""),
                   "explanation": r.get("explanation", ""),
                   "flagged": bool(r.get("flagged")),
                   "flag_reason": r.get("flag_reason", "")}
                  for r in parts],
    }


"""Booklet A -- multiple choice.

The same shape as Booklet B above and for the same reasons: the original page is
served and the student answers beside it. Two differences follow from it being
multiple choice.

First, marking is a comparison rather than a judgement, so it needs no API key and
never fails -- Booklet A works whether or not grading is available.

Second, the answer is one digit, which makes hiding it until it is asked for more
important here than there, not less. The questions payload carries no key, and the
option a question was answered with only comes back once a choice has been sent.
"""


def mcq_dir(year: int) -> Path:
    path = WORK_A / str(year)
    if not (path / "questions.json").exists():
        raise HTTPException(404, f"no indexed Booklet A for {year}")
    return path


def load_mcq(year: int) -> dict:
    return json.loads((mcq_dir(year) / "questions.json").read_text())


def load_mcq_key(year: int) -> dict:
    path = WORK_ANS / str(year) / "mcq-answers.json"
    if not path.exists():
        raise HTTPException(404, f"no answer key for {year}; run "
                                 f"build/extract_mcq_key.py")
    return json.loads(path.read_text())


def mcq_years() -> list[int]:
    if not WORK_A.exists():
        return []
    return sorted(int(path.name) for path in WORK_A.iterdir()
                  if path.is_dir() and path.name.isdigit()
                  and (path / "questions.json").exists())


@app.get("/api/mcq/papers")
def mcq_papers() -> list[dict]:
    out = []
    for year in mcq_years():
        data = load_mcq(year)
        out.append({
            "year": year,
            "questions": len(data["questions"]),
            "marks": data["stated_total_marks"],
            "needs_review": data["needs_review"],
        })
    return out


@app.get("/api/mcq/papers/{year}/questions")
def mcq_questions(year: int) -> dict:
    data = load_mcq(year)
    marks = data.get("marks_per_question")
    return {
        "year": year,
        "booklet_a": data["booklet_a"],
        "marks_per_question": marks,
        "stated_total_marks": data["stated_total_marks"],
        "questions": [{"question": q["question"], "pages": q["pages"],
                       "marks": marks}
                      for q in data["questions"]],
    }


@app.get("/api/mcq/papers/{year}/pages/{page}")
def mcq_page_image(year: int, page: int) -> FileResponse:
    data = load_mcq(year)
    booklet_a = data["booklet_a"]
    if not booklet_a["start"] <= page <= booklet_a["end"]:
        raise HTTPException(403, "only Booklet A pages are available")
    path = mcq_dir(year) / "pages" / f"page-{page:03d}.png"
    if not path.exists():
        raise HTTPException(404, "page not found")
    return FileResponse(path, media_type="image/png")


@app.post("/api/mcq/papers/{year}/answer/{question}")
def mcq_answer(year: int, question: int, payload: dict) -> dict:
    """Mark one MCQ against the key, and log it.

    Logged here rather than on a separate Save click, for the same reason the
    graded Booklet B attempt is: a mark the student never saved is a mark the
    paper total never sees.
    """
    choice = payload.get("choice")
    if choice not in (1, 2, 3, 4):
        raise HTTPException(400, "choose one of options 1 to 4")

    key = load_mcq_key(year)
    entry = next((a for a in key["answers"] if a["question"] == question), None)
    if entry is None:
        raise HTTPException(404, f"no answer key for Q{question}")

    marks_total = load_mcq(year).get("marks_per_question") or 0
    correct = choice == entry["answer"]
    marks = marks_total if correct else 0

    save_attempt({
        "year": year, "booklet": "A", "question": question, "part": None,
        "mode": "mcq", "answer": str(choice),
        "marks": marks, "marks_total": marks_total, "graded": True,
    })
    return {
        "question": question,
        "choice": choice,
        "answer": entry["answer"],
        "correct": correct,
        "marks": marks,
        "marks_total": marks_total,
        "explanation": entry.get("explanation", ""),
        # An answer the pipeline had to reconstruct is worth saying so about, so a
        # confident-looking "you were wrong" can be doubted when it deserves to be.
        "answer_source": entry.get("answer_source"),
        "source": key.get("source", "EPH suggested answer"),
    }


@app.get("/api/mcq/papers/{year}/score")
def mcq_score(year: int) -> dict:
    """Marks earned across Booklet A, best attempt per question."""
    data = load_mcq(year)
    per_question = data.get("marks_per_question") or 0
    slots = [q["question"] for q in data["questions"]]

    best: dict[int, int] = {}
    for row in list_attempts(year=year, booklet="A"):
        if row["marks"] is None:
            continue
        best[row["question"]] = max(best.get(row["question"], 0), int(row["marks"]))

    return {
        "year": year,
        "earned": sum(best.get(q, 0) for q in slots),
        "available": per_question * len(slots),
        "attempted": len(best),
        "slots": len(slots),
    }


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...),
                     year: int | None = Form(None),
                     question: int | None = Form(None)) -> dict:
    payload = await audio.read()
    if not payload:
        raise HTTPException(400, "empty recording")
    # Seed recognition with this question's scenario anchors. Without them Whisper
    # renders "plant E" as "Planty", destroying the label the marking gate keys on.
    anchors: list[str] = []
    if year is not None and question is not None:
        entry = next((q for q in load_questions(year)["questions"]
                      if q["question"] == question), None)
        if entry:
            anchors = entry.get("scenario_anchors", [])
    started = time.perf_counter()
    text = transcribe_bytes(payload, suffix=Path(audio.filename or "a.webm").suffix,
                            anchors=anchors)
    return {"text": text, "seconds": round(time.perf_counter() - started, 2),
            "model": model_name(), "anchors": anchors}


@app.get("/api/papers/{year}/score")
def paper_score(year: int) -> dict:
    """Marks earned across the whole paper, from the attempt log.

    Best attempt per sub-part, so re-practising a question improves the total
    rather than dragging it down — the point is what the student can now do.
    """
    data = load_questions(year)
    slots = [(q["question"], p["part"], p["marks"] or 0)
             for q in data["questions"] for p in q["parts"]
             if not p.get("is_parent")]
    available = sum(marks for _, _, marks in slots)

    best: dict[tuple[int, str | None], int] = {}
    for row in list_attempts(year=year, booklet="B"):
        if row["marks"] is None:
            continue
        key = (row["question"], row["part"])
        best[key] = max(best.get(key, 0), int(row["marks"]))

    earned = sum(best.get((q, part), 0) for q, part, _ in slots)
    return {
        "year": year,
        "earned": earned,
        "available": available,
        "attempted": len(best),
        "slots": len(slots),
    }


@app.get("/api/papers/{year}/progress")
def paper_progress(year: int) -> dict:
    """Progress on one Science paper: marks over time, weak topics, coverage."""
    return _progress(year)


@app.get("/api/progress")
def progress_all() -> dict:
    """Progress across every Science paper.

    Chinese has its own report at /api/chinese/progress rather than a `subject`
    parameter here. The two subjects share only the attempt log and the chart --
    everything else in a Science report (chains, facets, the contextual gate) is
    an idea Chinese marking does not have (CLAUDE.md 7.6), so one endpoint
    serving both would be a union of two shapes with half its fields always null.
    """
    return _progress(None)


def _progress(year: int | None) -> dict:
    from collections import defaultdict

    years = [year] if year is not None else indexed_years()

    # Rubric topics/themes keyed by sub-part, so a weak area can be named.
    meta: dict[tuple[int, int, str | None], dict] = {}
    for y in years:
        path = RUBRIC_DIR / f"{y}.json"
        if not path.exists():
            continue
        for r in json.loads(path.read_text())["rubrics"]:
            meta[(y, r["question"], r["part"])] = r

    # Two reads of the log, because the report has two halves and they do not want
    # the same rows. The chart is about the paper, so it counts both booklets -- a
    # Booklet A morning is marks earned on that paper and belongs on the bar. The
    # rollups below are keyed to Booklet B's rubrics, and the MCQ log has no chains,
    # facets or topics in it to roll up.
    all_rows = [row for y in years
                for row in list_attempts(year=y, limit=None)]
    rows = [row for row in all_rows if row["booklet"] == "B"]

    topic_stat: dict[str, dict] = defaultdict(lambda: {"earned": 0, "possible": 0, "attempts": 0})
    theme_stat: dict[str, dict] = defaultdict(lambda: {"earned": 0, "possible": 0, "attempts": 0})
    facet_stat: dict[str, dict] = defaultdict(lambda: {"hit": 0, "missed": 0})
    gate_fails = 0
    best: dict[tuple, dict] = {}

    for row in rows:
        if row["marks"] is None:
            continue
        if row["gate_passed"] == 0:
            gate_fails += 1

        key = (row["year"], row["question"], row["part"])
        if key not in best or row["marks"] > best[key]["marks"]:
            best[key] = dict(row)

        for outcome in json.loads(row["outcomes"] or "[]"):
            facet = outcome.get("facet") or "unknown"
            bucket = "hit" if outcome.get("status") == "hit" else "missed"
            facet_stat[facet][bucket] += 1

    # Topic and theme strength use the best attempt only: the question is what the
    # student can do now, not what they got wrong on the way there.
    for key, row in best.items():
        rubric = meta.get(key)
        if not rubric:
            continue
        for topic in rubric.get("syllabus_topics") or rubric.get("topics") or []:
            topic_stat[topic]["earned"] += row["marks"]
            topic_stat[topic]["possible"] += row["marks_total"] or 0
            topic_stat[topic]["attempts"] += 1
        for theme in rubric.get("themes") or []:
            theme_stat[theme]["earned"] += row["marks"]
            theme_stat[theme]["possible"] += row["marks_total"] or 0
            theme_stat[theme]["attempts"] += 1

    def ranked(stat: dict) -> list[dict]:
        out = [{"name": name, **v,
                "percent": round(v["earned"] / v["possible"] * 100) if v["possible"] else 0}
               for name, v in stat.items() if v["possible"]]
        return sorted(out, key=lambda d: (d["percent"], -d["possible"]))

    # Coverage is a count, not a list. Naming every untouched sub-part turned the
    # bottom of the report into a wall of question numbers that says nothing a
    # number does not -- and reads as a list of failures rather than of work left.
    slots = untouched = 0
    for y in years:
        for q in load_questions(y)["questions"]:
            for part in q["parts"]:
                if part.get("is_parent"):
                    continue
                slots += 1
                untouched += (y, q["question"], part["part"]) not in best

    return {
        "subject": "science",
        "years": sorted(years),
        "papers": by_paper_and_day(all_rows),
        "topics": ranked(topic_stat),
        "themes": ranked(theme_stat),
        "facets": [{"name": f, **v,
                    "percent": round(v["hit"] / (v["hit"] + v["missed"]) * 100)
                               if (v["hit"] + v["missed"]) else 0}
                   for f, v in sorted(facet_stat.items())],
        "gate_failures": gate_fails,
        "slots": slots,
        "untouched": untouched,
        "total_attempts": len(all_rows),
    }


@app.get("/api/grading")
def grading_status() -> dict:
    """Whether grading is available, so the UI can say so before a student tries."""
    return {"available": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/grade/{year}/{question}")
def grade_answer(year: int, question: int, payload: dict) -> dict:
    """Mark one sub-part against its rubric.

    Grading is optional by design (CLAUDE.md 2.2). When it is unavailable the
    student can still practise, self-check against the model answer and log the
    attempt — so this returns a 503 the UI can absorb, not an error page.
    """
    answer = (payload.get("answer") or "").strip()
    if not answer:
        raise HTTPException(400, "no answer to mark")

    rubrics = load_rubrics(year)["rubrics"]
    part = payload.get("part")
    rubric = next((r for r in rubrics
                   if r["question"] == question and r["part"] == part), None)
    if rubric is None:
        raise HTTPException(404, f"no rubric for Q{question}({part or '-'})")
    if rubric.get("flagged"):
        raise HTTPException(409, "this rubric is flagged for review and is not in use")
    if not rubric.get("chains"):
        raise HTTPException(409, "this sub-part has no rubric to mark against")

    try:
        result = grade(answer, rubric, question_context=payload.get("context", ""))
    except GradingUnavailable as exc:
        raise HTTPException(503, str(exc))

    # Log the graded attempt here rather than waiting for a Save click. A mark the
    # student never saved is a mark the progress report never sees, and the report
    # is the point of keeping the log at all.
    facet_of = {kp["kp_id"]: kp.get("facet")
                for chain in rubric.get("chains", [])
                for kp in chain.get("keypoints", [])}
    outcomes = [{"kp_id": link.kp_id, "status": link.status,
                 "chain_id": chain.chain_id, "facet": facet_of.get(link.kp_id)}
                for chain in result.chains for link in chain.links]
    save_attempt({
        "year": year, "question": question, "part": part,
        "mode": payload.get("mode", "typed"),
        "answer": answer, "transcript": payload.get("transcript"),
        "marks": result.marks_awarded, "marks_total": result.marks_total,
        "graded": True, "claims": result.claims, "outcomes": outcomes,
        "gate_passed": result.context_gate.passed,
        "topics": rubric.get("topics", []),
    })
    return result.as_dict()


@app.post("/api/attempts")
def create_attempt(payload: dict) -> dict:
    required = {"year", "question", "part", "answer", "mode"}
    missing = required - payload.keys()
    if missing:
        raise HTTPException(400, f"missing fields: {sorted(missing)}")
    return save_attempt(payload)


@app.get("/api/attempts")
def attempts(year: int | None = None, question: int | None = None) -> list[dict]:
    return list_attempts(year=year, question=question)


def load_rubrics(year: int) -> dict:
    path = RUBRIC_DIR / f"{year}.json"
    if not path.exists():
        raise HTTPException(404, f"no rubrics for {year}; run build/rubric.py")
    return json.loads(path.read_text())


@app.get("/api/review/{year}")
def review_queue(year: int) -> dict:
    """Rubrics to sign off — only authored ones can be reviewed.

    Sign-off is read from review/reviewed.json rather than from the rubrics file,
    which only reflects approvals after build/rubric.py re-runs. Reading the
    derived file made a page refresh show completed review as undone.
    """
    data = load_rubrics(year)
    flags = json.loads(FLAGS_FILE.read_text()) if FLAGS_FILE.exists() else {}
    decisions = flags.get(str(year), {})
    # Drawing questions have no chains by design. They still need a human to
    # confirm the classification, so they belong in the queue rather than
    # disappearing from it.
    rubrics = [r for r in data["rubrics"]
               if r.get("chains") or r.get("response_mode") == "drawn"]
    for rubric in rubrics:
        decision = decisions.get(f"{rubric['question']}{rubric['part'] or ''}")
        rubric["flagged"] = isinstance(decision, dict)
        rubric["reviewed"] = not rubric["flagged"]
        if rubric["flagged"]:
            rubric["flag_reason"] = decision.get("reason", "")
            rubric["flag_source"] = decision.get("source", "")
            rubric["flagged_at"] = decision.get("at")
    return {
        "year": year,
        "total": len(data["rubrics"]),
        "authored": len(rubrics),
        "flagged": sum(1 for r in rubrics if r.get("flagged")),
        "source": data.get("source"),
        "rubrics": rubrics,
    }


@app.post("/api/flags/{year}")
def set_flag(year: int, payload: dict) -> dict:
    """Raise or clear a flag on one rubric or model answer.

    Rubrics are approved by default, so this file records only the exceptions.
    Flagging is available from the practice app as well as the review page,
    because a problem noticed while marking a real answer is the one most worth
    capturing — and the least likely to be found by reading rubrics in the
    abstract.
    """
    question = payload.get("question")
    if question is None:
        raise HTTPException(400, "question is required")
    key = f"{question}{payload.get('part') or ''}"
    reason = (payload.get("reason") or "").strip()

    FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(FLAGS_FILE.read_text()) if FLAGS_FILE.exists() else {}
    entries = data.setdefault(str(year), {})

    if payload.get("flagged", True):
        if not reason:
            raise HTTPException(400, "a reason is required when flagging")
        entries[key] = {
            "reason": reason,
            "source": payload.get("source", "review"),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        result = {"key": key, "flagged": True, **entries[key]}
    else:
        entries.pop(key, None)
        result = {"key": key, "flagged": False}

    if not entries:
        data.pop(str(year), None)
    FLAGS_FILE.write_text(json.dumps(data, indent=2))
    return result


@app.get("/api/flags/{year}")
def get_flags(year: int) -> dict:
    data = json.loads(FLAGS_FILE.read_text()) if FLAGS_FILE.exists() else {}
    return {k: v for k, v in data.get(str(year), {}).items() if isinstance(v, dict)}


@app.get("/progress", include_in_schema=False)
def progress_page() -> HTMLResponse:
    return _shell("progress.html")


@app.get("/review", include_in_schema=False)
def review_page() -> HTMLResponse:
    return _shell("review.html")


@app.get("/", include_in_schema=False)
def index() -> HTMLResponse:
    """Serve the shell with asset URLs versioned by file mtime.

    No build step means no content-hashed filenames, so an edited style.css or
    app.js can sit in the browser cache indefinitely and present as a bug in the
    app -- a stale stylesheet is what made the answer boxes look like they had
    failed to render. Stamping the mtime makes every edit a new URL.
    """
    return _shell("index.html")


def _shell(name: str) -> HTMLResponse:
    html = (STATIC_DIR / name).read_text()
    for asset in ("style.css", "app.js", "chinese.js", "review.js",
                  "progress.js"):
        path = STATIC_DIR / asset
        if path.exists():
            html = html.replace(f"/{asset}", f"/{asset}?v={int(path.stat().st_mtime)}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


class NoCacheStatic(StaticFiles):
    """Serve the frontend without caching.

    There is no build step and no cache-busting filenames, so a browser that holds
    on to style.css or app.js shows stale behaviour that looks exactly like a bug in
    the app. On localhost, for one user, re-reading a few small files costs nothing.
    """

    def is_not_modified(self, response_headers, request_headers) -> bool:
        return False

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


app.mount("/", NoCacheStatic(directory=STATIC_DIR, html=True), name="static")
