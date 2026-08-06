"""Attempt log.

Minimal for Phase 2: enough that practice is not lost, and enough that the Phase 4
progress views have history to read when they arrive. Grading columns are nullable
because Phase 2 has no grader.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "attempts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    year        INTEGER NOT NULL,
    question    INTEGER NOT NULL,
    part        TEXT,
    mode        TEXT    NOT NULL,          -- 'voice' | 'typed'
    answer      TEXT    NOT NULL,          -- as submitted, after any correction
    transcript  TEXT,                      -- raw transcript before correction
    marks       INTEGER,                   -- self-marked in Phase 2
    marks_total INTEGER
);
CREATE INDEX IF NOT EXISTS attempts_by_question
    ON attempts (year, question, part);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def save_attempt(payload: dict) -> dict:
    row = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": int(payload["year"]),
        "question": int(payload["question"]),
        "part": payload.get("part"),
        "mode": payload["mode"],
        "answer": payload["answer"],
        "transcript": payload.get("transcript"),
        "marks": payload.get("marks"),
        "marks_total": payload.get("marks_total"),
    }
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO attempts (created_at, year, question, part, mode, answer,"
            " transcript, marks, marks_total)"
            " VALUES (:created_at, :year, :question, :part, :mode, :answer,"
            " :transcript, :marks, :marks_total)", row)
        row["id"] = cursor.lastrowid
    return row


def list_attempts(year: int | None = None, question: int | None = None) -> list[dict]:
    clauses, params = [], []
    if year is not None:
        clauses.append("year = ?")
        params.append(year)
    if question is not None:
        clauses.append("question = ?")
        params.append(question)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attempts{where} ORDER BY id DESC LIMIT 200", params
        ).fetchall()
    return [dict(row) for row in rows]
