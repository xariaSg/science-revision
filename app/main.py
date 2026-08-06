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
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import init_db, list_attempts, save_attempt
from stt import transcribe_bytes, model_name

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work"
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


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
