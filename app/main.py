"""FastAPI app: browse Booklet B questions, answer them aloud, self-check.

Phase 2 -- no grading. The student picks a question, reads it off the original
scanned page, answers each sub-part by voice or typing, corrects the transcript, and
reveals the model answer to mark themselves.

Two deliberate constraints:

* Only Booklet B pages are served. The papers also contain the answer pages, and
  serving whole papers would put the answers one URL guess away.
* The model answer is a separate, explicit request. It is never included in the
  question payload, so it cannot be read out of the page source before attempting.
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

from db import init_db, list_attempts, save_attempt
from grade import GradingUnavailable, grade
from stt import transcribe_bytes, model_name

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"
RUBRIC_DIR = REPO / "rubrics"
FLAGS_FILE = REPO / "review" / "flags.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="PSLE Booklet B")


def paper_dir(year: int) -> Path:
    path = WORK_DIR / str(year)
    if not (path / "questions.json").exists():
        raise HTTPException(404, f"no indexed paper for {year}")
    return path


def load_questions(year: int) -> dict:
    return json.loads((paper_dir(year) / "questions.json").read_text())


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/papers")
def papers() -> list[dict]:
    out = []
    for path in sorted(WORK_DIR.iterdir()) if WORK_DIR.exists() else []:
        if not (path.is_dir() and path.name.isdigit()):
            continue
        if not (path / "questions.json").exists():
            continue
        data = json.loads((path / "questions.json").read_text())
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
    """The suggested answer, requested explicitly after an attempt."""
    path = paper_dir(year) / "answers" / "segments.json"
    if not path.exists():
        raise HTTPException(404, "no answers extracted for this paper")
    data = json.loads(path.read_text())
    entry = next((q for q in data["questions"] if q["question"] == question), None)
    if entry is None:
        raise HTTPException(404, f"no answer segmented for Q{question}")
    return {
        "question": question,
        "source": data.get("source", "EPH suggested answer"),
        "draft_only": data.get("ocr_draft_only", True),
        "parts": [{"part": p["part"], "text": p["ocr_draft"],
                   "crops": [f"/api/papers/{year}/answers/{question}/crop/"
                             f"{Path(c).name}" for c in p.get("crops", [])]}
                  for p in entry["parts"]],
    }


@app.get("/api/papers/{year}/answers/{question}/crop/{name}")
def answer_crop(year: int, question: int, name: str) -> FileResponse:
    if "/" in name or ".." in name:
        raise HTTPException(400, "bad crop name")
    path = paper_dir(year) / "answers" / "crops" / name
    if not path.exists():
        raise HTTPException(404, "crop not found")
    return FileResponse(path, media_type="image/png")


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
    for asset in ("style.css", "app.js", "review.js"):
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
