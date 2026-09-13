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
    paper       TEXT    NOT NULL DEFAULT '',  -- '2024' | '2025-prelim-rosyth'
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
    ON attempts (subject, paper, question, part);
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
    # Which paper, as opposed to which year. They were the same thing until the
    # 2025 school prelims arrived: fourteen papers sat in one year, so a year no
    # longer names a paper. Backfilled below from the year, because every attempt
    # logged before then was against the PSLE paper whose id *is* its year.
    "paper": "TEXT NOT NULL DEFAULT ''",
}


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)")}
        for column, decl in LATER_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} {decl}")
        # SQLite cannot default one column from another, so the backfill is its
        # own statement. It is safe to repeat: only rows with no paper are
        # touched, and a paper id is never empty once written.
        conn.execute("UPDATE attempts SET paper = CAST(year AS TEXT) "
                     "WHERE paper IS NULL OR paper = ''")


def _json(value) -> str | None:
    return json.dumps(value) if value is not None else None


def save_attempt(payload: dict) -> dict:
    row = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject": payload.get("subject", "science"),
        # A caller that knows only a year is talking about a PSLE paper, whose id
        # is that year written out.
        "paper": str(payload.get("paper") or payload["year"]),
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
            "INSERT INTO attempts (created_at, subject, paper, year, booklet,"
            " question, part, mode, answer, transcript, marks, marks_total,"
            " graded, claims, outcomes, gate_passed, topics)"
            " VALUES (:created_at, :subject, :paper, :year, :booklet, :question,"
            " :part, :mode, :answer,"
            " :transcript, :marks, :marks_total, :graded, :claims, :outcomes,"
            " :gate_passed, :topics)", row)
        row["id"] = cursor.lastrowid
    return row


def attempted_papers(subject: str) -> set[str]:
    """Paper ids with at least one logged attempt, for one subject.

    For the paper picker: a paper is "attempted" once anything at all has been
    logged against it, regardless of which booklet or how many rows -- the
    picker is marking "has she had a go at this one", not tallying a score.
    """
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT paper FROM attempts WHERE subject = ? AND paper != ''",
            (subject,)).fetchall()
    return {row["paper"] for row in rows}


def list_attempts(paper: str | int | None = None, question: int | None = None,
                  booklet: str | None = None,
                  subject: str = "science",
                  limit: int | None = 200) -> list[dict]:
    """Attempts for one subject, newest first.

    Filtered by paper rather than by year: fifteen Science papers now carry the
    year 2025 -- the PSLE one and fourteen school prelims -- so a year selects a
    stack of different papers rather than one. An int is accepted and read as a
    PSLE id, which is what a year has always meant here.

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
    if paper is not None:
        clauses.append("paper = ?")
        params.append(str(paper))
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


def day_of(row: dict) -> str:
    """The day an attempt is filed under.

    Its own function because two things must agree on it: the chart buckets bars
    by it, and the drill-down behind a bar re-selects the rows by it. A bar the
    click could not reproduce is worse than no drill-down at all.
    """
    return (row.get("created_at") or "")[:10]


def percent(earned: int, possible: int) -> int:
    return round(earned / possible * 100) if possible else 0


def kinds_present(papers: list[dict], kinds: list[tuple[str, str, str]]) -> list[dict]:
    """The split's key, in the order the paper is sat and filtered to what is on
    the chart.

    Filtered because a key should describe the picture: a subject she has only
    ever answered one way should not be told about the other. Ordered from the
    declaration rather than from the data, because first-seen order is the order
    the *days* happened to fall in -- which put Booklet B ahead of Booklet A in
    the key while the chart stacked them the other way round.
    """
    present = {part["id"] for paper in papers for part in paper["parts"]}
    return [{"id": kind_id, "name": label, "short": short}
            for kind_id, label, short in kinds if kind_id in present]


def by_paper_and_day(rows: list[dict], kinds: list[tuple[str, str, str]] = (),
                     kind_of=None) -> list[dict]:
    """Roll marked attempts up into one entry per paper per day.

    The unit the progress chart plots. Collapsing to the day alone would be the
    obvious rollup and it loses the one thing the chart is labelled with -- which
    paper the marks came from. A morning on the 2022 paper and an afternoon on
    2024 are two results, not one average. Keyed on the paper id rather than the
    year for the same reason: a morning on Rosyth's prelim and an afternoon on
    Nanyang's are two results too, and both are 2025.

    `possible` is the marks of what was actually attempted, not the paper's full
    total, so a two-question sitting is not reported as a near-zero score.

    Each bucket is then split again by the kind of answering it was: Science's
    MCQ against its written half, Chinese's chosen against its written. They are
    close to two different skills sharing one paper, and a bar that sums them
    hides a full-marks Booklet A behind a weak Booklet B -- the one comparison
    the sitting is actually about. `kinds` is [(id, label, short), ...] in the
    order the paper is sat, and `kind_of(row)` says which one a row belongs to;
    returning None leaves that row out of the split but still in the total. A
    kind with nothing in it does not appear, so a Booklet A morning still draws
    as one block rather than as a half-empty pair.
    """
    from collections import defaultdict

    def fresh() -> dict:
        return {"earned": 0, "possible": 0, "attempts": 0}

    buckets: dict[tuple[str, int], dict] = defaultdict(
        lambda: {**fresh(), "parts": defaultdict(fresh)})
    for row in rows:
        if row["marks"] is None:
            continue
        bucket = buckets[(day_of(row), row["paper"])]
        targets = [bucket]
        kind = kind_of(row) if kind_of else None
        if kind is not None:
            targets.append(bucket["parts"][kind])
        for target in targets:
            target["earned"] += row["marks"]
            target["possible"] += row["marks_total"] or 0
            target["attempts"] += 1

    out = []
    for (date, paper), bucket in sorted(buckets.items()):
        parts = bucket.pop("parts")
        out.append({
            "date": date, "paper": paper, **bucket,
            "percent": percent(bucket["earned"], bucket["possible"]),
            "parts": [{"id": kind_id, "name": label, "short": short, **parts[kind_id],
                       "percent": percent(parts[kind_id]["earned"],
                                          parts[kind_id]["possible"])}
                      for kind_id, label, short in kinds if kind_id in parts],
        })
    return out
