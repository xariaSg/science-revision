"""Attempt log.

Minimal for Phase 2: enough that practice is not lost, and enough that the Phase 4
progress views have history to read when they arrive. Grading columns are nullable
because Phase 2 has no grader.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "attempts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    subject     TEXT    NOT NULL DEFAULT 'science', -- 'science' | 'chinese'
    year        INTEGER NOT NULL,
    booklet     TEXT    NOT NULL DEFAULT 'B', -- 'A' (MCQ) | 'B' (open-ended)
    question    INTEGER NOT NULL,
    part        TEXT,
    mode        TEXT    NOT NULL,          -- 'voice' | 'typed' | 'mcq'
    answer      TEXT    NOT NULL,          -- as submitted, after any correction
    transcript  TEXT,                      -- raw transcript before correction
    marks       INTEGER,                   -- awarded, by the grader or self-marked
    marks_total INTEGER,
    graded      INTEGER NOT NULL DEFAULT 0, -- 1 when the grader produced the mark
    claims      TEXT,                       -- Stage A output, JSON
    outcomes    TEXT,                       -- per-keypoint verdicts, JSON
    gate_passed INTEGER,                    -- contextual gate, when graded
    topics      TEXT                        -- rubric topics, JSON, for weak-area rollup
);
CREATE INDEX IF NOT EXISTS attempts_by_question
    ON attempts (subject, year, question, part);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Columns added after the first release. SQLite has no "add column if missing",
# so this brings an existing attempts.db up to date without losing its rows.
LATER_COLUMNS = {
    "graded": "INTEGER NOT NULL DEFAULT 0",
    "claims": "TEXT",
    "outcomes": "TEXT",
    "gate_passed": "INTEGER",
    "topics": "TEXT",
    # Every attempt logged before Booklet A existed was a Booklet B one, which is
    # what the default backfills. Question numbers do not currently collide between
    # the booklets -- B continues A's numbering -- but that is the paper's
    # convention, not something the log should depend on.
    "booklet": "TEXT NOT NULL DEFAULT 'B'",
    # Every attempt logged before Chinese existed was a Science one, which is what
    # the default backfills. Question numbers collide freely across subjects --
    # both papers have a Q1 -- so nothing may read the log without a subject.
    "subject": "TEXT NOT NULL DEFAULT 'science'",
}


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)")}
        for column, decl in LATER_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} {decl}")


def _json(value) -> str | None:
    return json.dumps(value) if value is not None else None


def save_attempt(payload: dict) -> dict:
    row = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject": payload.get("subject", "science"),
        "year": int(payload["year"]),
        "booklet": payload.get("booklet", "B"),
        "question": int(payload["question"]),
        "part": payload.get("part"),
        "mode": payload["mode"],
        "answer": payload["answer"],
        "transcript": payload.get("transcript"),
        "marks": payload.get("marks"),
        "marks_total": payload.get("marks_total"),
        "graded": 1 if payload.get("graded") else 0,
        "claims": _json(payload.get("claims")),
        "outcomes": _json(payload.get("outcomes")),
        "gate_passed": (None if payload.get("gate_passed") is None
                        else int(bool(payload["gate_passed"]))),
        "topics": _json(payload.get("topics")),
    }
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO attempts (created_at, subject, year, booklet, question,"
            " part, mode, answer, transcript, marks, marks_total, graded, claims,"
            " outcomes, gate_passed, topics)"
            " VALUES (:created_at, :subject, :year, :booklet, :question, :part,"
            " :mode, :answer,"
            " :transcript, :marks, :marks_total, :graded, :claims, :outcomes,"
            " :gate_passed, :topics)", row)
        row["id"] = cursor.lastrowid
    return row


def list_attempts(year: int | None = None, question: int | None = None,
                  booklet: str | None = None,
                  subject: str = "science",
                  limit: int | None = 200) -> list[dict]:
    """Attempts for one subject, newest first.

    `subject` is not optional-by-default the way the other filters are: Science
    Q1 and Chinese Q1 are different questions, so a caller that forgets it would
    silently mix two papers' marks into one score.

    `limit=None` returns every row. The cap is a sensible default for "show me
    recent attempts" and the wrong thing entirely for the progress report: rows
    come back newest first, so a truncated read drops the *oldest* days -- the
    left-hand end of the trend chart, and the half of the comparison that shows
    improvement. A Chinese paper is 40 questions, so two sittings of one year
    already reach the default.
    """
    clauses, params = ["subject = ?"], [subject]
    if year is not None:
        clauses.append("year = ?")
        params.append(year)
    if question is not None:
        clauses.append("question = ?")
        params.append(question)
    if booklet is not None:
        clauses.append("booklet = ?")
        params.append(booklet)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM attempts{where} ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def by_paper_and_day(rows: list[dict]) -> list[dict]:
    """Roll marked attempts up into one entry per paper per day.

    The unit the progress chart plots. Collapsing to the day alone would be the
    obvious rollup and it loses the one thing the chart is labelled with -- which
    paper the marks came from. A morning on the 2022 paper and an afternoon on
    2024 are two results, not one average.

    `possible` is the marks of what was actually attempted, not the paper's full
    total, so a two-question sitting is not reported as a near-zero score.
    """
    from collections import defaultdict

    buckets: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    for row in rows:
        if row["marks"] is None:
            continue
        key = ((row["created_at"] or "")[:10], row["year"])
        bucket = buckets[key]
        bucket["earned"] += row["marks"]
        bucket["possible"] += row["marks_total"] or 0
        bucket["attempts"] += 1
    return [{"date": date, "year": year, **v,
             "percent": round(v["earned"] / v["possible"] * 100) if v["possible"] else 0}
            for (date, year), v in sorted(buckets.items())]
