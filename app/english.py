"""English Paper 2: two booklets, practised whole, marked once at the end.

The third subject, and it borrows from both of the others rather than from either
alone:

* **Booklet A is multiple choice**, options 1 to 4, marked against a key -- which
  needs no API key and never fails, exactly as Science's Booklet A does.
* **Booklet B is typed**: a letter or a word into a blank for Q26-60, a rewritten
  sentence for Q61-65. The short answers are marked by comparing strings, which
  is what CLAUDE.md 7.6 settles on for Chinese Q34-35 and for the same reason --
  a one-word answer has one right form, and asking a model to judge it is less
  reliable than comparing it.

**The paper loads whole and nothing is marked until it is finished.** Both
booklets, and for CLAUDE.md 7.6's reason: most of this paper's questions are
blanks inside a passage, so the page is the unit of reading and a question cropped
out of its passage is not the question. Marking each blank as it is typed would
turn a 40-question booklet into 40 little tests, and a running total invites
watching the number instead of reading the passage.

Two things this does *not* do, and both are the honest state rather than an
oversight:

* **The comprehension section (Q66-75) is not marked.** Its answers are tables,
  ticks and explanations; marking them needs the kind of hand-authored rubric
  CLAUDE.md 3 describes, and section 10.5 is explicit that generating one from a
  model answer produces plausible rubrics that award marks in the wrong places.
  Its pages are served so the student can read and attempt it on paper.
* **Synthesis and transformation (Q61-65) is self-marked** against the model
  answer, which is the same footing nine of the fourteen Chinese years are on
  (CLAUDE.md 7.7) and every prelim Booklet B in Science (10.5).

Answer material never reaches a route. The keys live under `work-en-ans`, which
nothing here serves, and a question's answer is returned only in the response to
submitting the finished paper.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import papers as paper_ids
from db import (by_paper_and_day, day_of, kinds_present, list_attempts,
                percent, save_attempt)

REPO = Path(__file__).resolve().parent.parent
WORK_A = REPO / "work-en-a"
WORK_B = REPO / "work-en-b"
# Deliberately not reachable from any route: the keys are read from here on the
# server and never served as files (CLAUDE.md 7.1, 9).
WORK_ANS = REPO / "work-en-ans"

SUBJECT = "english"

# Which booklet a question was answered in. The two are marked by different
# machinery and behave differently under it, so the progress chart keeps them
# apart the way SCIENCE_KINDS does -- and here they are also two separate
# sittings, since the booklets are practised one at a time.
EN_KINDS = [("mcq", "Booklet A · multiple choice", "A"),
            ("written", "Booklet B · written", "B")]

ROOTS = {"A": WORK_A, "B": WORK_B}

# How a typed answer is compared with the key. Case and surrounding punctuation
# are ignored: "Despite" opens a sentence in the passage and a child who types
# "despite" has the English right, and CLAUDE.md 3.2 is explicit that a marker
# ignores form when the answer is clear. A difference in case is fed back as a
# note instead, which costs nothing and teaches the convention.
TRIM_RE = re.compile(r"^[\s\"'“”‘’.,;:!?()\[\]]+|[\s\"'“”‘’.,;:!?()\[\]]+$")

router = APIRouter(prefix="/api/english", tags=["english"])


def paper_dir(paper: str, booklet: str) -> Path:
    root = ROOTS.get(booklet.upper())
    if root is None:
        raise HTTPException(404, "booklet must be A or B")
    path = root / str(paper)
    if not (path / "questions.json").exists():
        raise HTTPException(404, f"no indexed Booklet {booklet.upper()} for {paper}")
    return path


def load_questions(paper: str, booklet: str) -> dict:
    return json.loads((paper_dir(paper, booklet) / "questions.json").read_text())


def load_key(paper: str, booklet: str) -> dict:
    name = "mcq-answers.json" if booklet.upper() == "A" else "answers.json"
    path = WORK_ANS / str(paper) / name
    if not path.exists():
        raise HTTPException(404, f"no answer key for {paper} Booklet "
                                 f"{booklet.upper()}; run build/en_key.py "
                                 f"(Booklet A) or build/en_key_b.py (Booklet B)")
    return json.loads(path.read_text())


def indexed(booklet: str) -> list[str]:
    return paper_ids.discover(ROOTS[booklet])


def built() -> list[str]:
    """Every English paper with at least one booklet indexed."""
    return sorted(set(indexed("A")) | set(indexed("B")), key=paper_ids.sort_key)


def _section_names(paper: str) -> dict[int, str]:
    """Section names, which the school prints on its key and not on the paper.

    "Grammar", "Vocab Cloze", "Visual Text" -- the booklet itself heads each
    section with an instruction and no name, so the only place the names exist is
    the key. They are not answers, and a name is worth far more to a child
    navigating twenty-five questions than "Questions 16-20" is, so they are read
    across. Nothing else crosses: the key is read here on the server and the
    answers in it never enter a questions payload.
    """
    try:
        key = load_key(paper, "A")
    except HTTPException:
        return {}
    return {index: name for index, name in enumerate(key.get("sections", []))}


@router.get("/papers")
def papers() -> list[dict]:
    out = []
    for paper in built():
        entry = {**paper_ids.describe(paper), "booklets": []}
        for booklet in ("A", "B"):
            if paper not in indexed(booklet):
                continue
            data = load_questions(paper, booklet)
            questions = data["questions"]
            entry["booklets"].append({
                "booklet": booklet,
                "label": f"Booklet {booklet}",
                "hint": ("multiple choice" if booklet == "A"
                         else "cloze, editing and sentences"),
                "questions": len(questions),
                "marks": data["stated_total_marks"],
                "answerable": data.get("answerable", len(questions)),
                "needs_review": data["needs_review"],
            })
        out.append(entry)
    return out


def page_sizes(paper: str, booklet: str) -> list[dict]:
    """Rendered size of every page, so the UI can reserve layout before loading.

    The same reason chinese.page_sizes exists: pages are lazy-loaded, and a lazy
    image occupies no height until it loads, so "jump to Q47" without an
    intrinsic size computes an offset near the top of the document.
    """
    manifest = paper_dir(paper, booklet) / "manifest.json"
    if not manifest.exists():
        return []
    return [{"page": p["page_number"], "width": p["width"], "height": p["height"]}
            for p in json.loads(manifest.read_text())["pages"]]


@router.get("/papers/{paper}/booklet-{booklet}/questions")
def questions(paper: str, booklet: str) -> dict:
    data = load_questions(paper, booklet)
    names = _section_names(paper) if booklet.upper() == "A" else {}
    first, last = _served_pages(data, booklet)
    sections = [{**section, "name": names.get(section["section"])}
                for section in data["sections"]]

    if booklet.upper() == "A":
        marks = data["marks_per_question"]
        items = [{"question": q["question"], "section": q["section"],
                  "pages": q["pages"], "context_pages": q.get("context_pages", []),
                  "marks": marks, "response_mode": "choose", "options": 4}
                 for q in data["questions"]]
    else:
        items = [{"question": q["question"], "section": q["section"],
                  "pages": q["pages"], "context_pages": [],
                  "marks": q["marks"], "response_mode": q["response_mode"]}
                 for q in data["questions"]]

    return {
        **paper_ids.describe(paper),
        "booklet": booklet.upper(),
        "pages": {"first": first, "last": last},
        "page_sizes": [size for size in page_sizes(paper, booklet)
                       if first <= size["page"] <= last],
        "sections": sections,
        "stated_total_marks": data["stated_total_marks"],
        "needs_review": data["needs_review"],
        "notes": data.get("notes", []),
        "questions": items,
    }


def _served_pages(data: dict, booklet: str) -> tuple[int, int]:
    """The page range this booklet is allowed to serve.

    Booklet A's last page carries Booklet B's comprehension passage and is not
    part of Booklet A (build/en_index.py), so the bound comes from the index
    rather than from the file's length.
    """
    span = data.get("booklet_a") if booklet.upper() == "A" else data.get("booklet_b")
    if not span:
        return 1, data["num_pages"]
    return span["start"], span["end"]


@router.get("/papers/{paper}/booklet-{booklet}/pages/{page}")
def page_image(paper: str, booklet: str, page: int) -> FileResponse:
    data = load_questions(paper, booklet)
    first, last = _served_pages(data, booklet)
    if not first <= page <= last:
        raise HTTPException(403, f"only Booklet {booklet.upper()} pages are available")
    path = paper_dir(paper, booklet) / "pages" / f"page-{page:03d}.png"
    if not path.exists():
        raise HTTPException(404, "page not found")
    return FileResponse(path, media_type="image/png")


def normalise(text: str) -> str:
    return TRIM_RE.sub("", " ".join((text or "").split())).lower()


def _mark_choice(entry: dict, key_entry: dict, given) -> dict:
    if not isinstance(given, int) or not 1 <= given <= 4:
        raise HTTPException(400, "choose one of options 1 to 4")
    correct = given == key_entry["answer"]
    total = entry["marks"] or 0
    return {"chose": given, "answer": key_entry["answer"], "correct": correct,
            "marks": total if correct else 0, "marks_total": total,
            "graded": True}


def _mark_typed(entry: dict, key_entry: dict, given) -> dict:
    """Compare a one-word or one-letter answer with the key.

    Case is ignored and reported rather than deducted (CLAUDE.md 3.2). The letter
    and the word behind it are both accepted for the grammar cloze, because the
    key prints both -- "F (had)" -- and a child who has understood the blank may
    write either.
    """
    given = (given or "").strip()
    if not given:
        raise HTTPException(400, "no answer to mark")
    accepted = key_entry.get("accept") or []
    match = next((a for a in accepted if normalise(a) == normalise(given)), None)
    total = entry["marks"] or 0
    result = {"answer": given, "expected": accepted, "correct": match is not None,
              "marks": total if match else 0, "marks_total": total, "graded": True}
    if match is not None and match != given.strip():
        result["note"] = f"The key writes it “{match}”."
    return result


@router.post("/papers/{paper}/booklet-{booklet}/submit")
def submit(paper: str, booklet: str, payload: dict) -> dict:
    """Mark a finished booklet in one go, and log every answer.

    One request rather than one per question, because the paper is marked once at
    the end: a partial submission is a partial sitting, and the log should read
    the way the sitting happened.

    A sentence answer is not marked here -- it is logged ungraded and comes back
    with its model answer for the student to mark against, which is the
    self-marking path CLAUDE.md 7.6 records for Chinese Q33 and 10.5 for every
    prelim Booklet B.
    """
    booklet = booklet.upper()
    data = load_questions(paper, booklet)
    key = load_key(paper, booklet)
    entries = {q["question"]: q for q in data["questions"]}
    if booklet == "A":
        marks = data["marks_per_question"]
        for entry in entries.values():
            entry["marks"] = marks
    key_entries = {a["question"]: a for a in key["answers"]}

    given = payload.get("answers") or {}
    if not isinstance(given, dict) or not given:
        raise HTTPException(400, "no answers submitted")

    results: list[dict] = []
    for number_text, value in given.items():
        try:
            number = int(number_text)
        except (TypeError, ValueError):
            raise HTTPException(400, f"not a question number: {number_text!r}")
        entry = entries.get(number)
        if entry is None:
            raise HTTPException(404, f"Booklet {booklet} has no Q{number}")
        mode = entry.get("response_mode", "choose")
        key_entry = key_entries.get(number)

        if mode == "not_built":
            raise HTTPException(409, f"Q{number} is not marked by this app")
        if key_entry is None and mode != "sentence":
            raise HTTPException(409, f"the key for Q{number} could not be read")

        if mode == "choose":
            result = _mark_choice(entry, key_entry, value)
        elif mode in ("letter", "word"):
            result = _mark_typed(entry, key_entry, value)
        else:
            text = (value or "").strip()
            if not text:
                raise HTTPException(400, f"no answer to log for Q{number}")
            result = {"answer": text, "marks": None,
                      "marks_total": entry["marks"] or 0, "graded": False,
                      "model_answer": (key_entry or {}).get("text", "")}

        save_attempt({
            "subject": SUBJECT, "paper": str(paper),
            "year": paper_ids.year_of(paper), "booklet": booklet,
            "question": number, "part": None, "mode": mode,
            "answer": str(result.get("chose", result.get("answer", ""))),
            "marks": result["marks"], "marks_total": result["marks_total"],
            "graded": result["graded"],
        })
        results.append({"question": number, "section": entry["section"],
                        "response_mode": mode, **result})

    results.sort(key=lambda row: row["question"])
    marked = [row for row in results if row["marks"] is not None]
    return {
        **paper_ids.describe(paper),
        "booklet": booklet,
        "earned": sum(row["marks"] for row in marked),
        "possible": sum(row["marks_total"] for row in marked),
        "self_marking": [row["question"] for row in results
                         if row["marks"] is None],
        "source": key.get("source"),
        "authoritative": key.get("authoritative", False),
        "results": results,
    }


@router.post("/papers/{paper}/booklet-{booklet}/self-mark/{question}")
def self_mark(paper: str, booklet: str, question: int, payload: dict) -> dict:
    """Record the marks a student gave themselves against the model answer."""
    booklet = booklet.upper()
    data = load_questions(paper, booklet)
    entry = next((q for q in data["questions"] if q["question"] == question), None)
    if entry is None:
        raise HTTPException(404, f"Booklet {booklet} has no Q{question}")
    total = entry.get("marks") or 0
    marks = payload.get("marks")
    if not isinstance(marks, int) or not 0 <= marks <= total:
        raise HTTPException(400, f"marks must be between 0 and {total}")

    save_attempt({
        "subject": SUBJECT, "paper": str(paper),
        "year": paper_ids.year_of(paper), "booklet": booklet,
        "question": question, "part": None, "mode": "self_marked",
        "answer": payload.get("answer", ""), "marks": marks,
        "marks_total": total, "graded": False,
    })
    return {"question": question, "marks": marks, "marks_total": total}


@router.get("/papers/{paper}/booklet-{booklet}/score")
def score(paper: str, booklet: str) -> dict:
    """Marks across one booklet, best attempt per question."""
    booklet = booklet.upper()
    data = load_questions(paper, booklet)
    if booklet == "A":
        per = data["marks_per_question"] or 0
        slots = {q["question"]: per for q in data["questions"]}
    else:
        slots = {q["question"]: (q["marks"] or 0) for q in data["questions"]
                 if q["response_mode"] != "not_built"}

    best: dict[int, int] = {}
    for row in list_attempts(paper=paper, booklet=booklet, subject=SUBJECT,
                             limit=None):
        if row["marks"] is None or row["question"] not in slots:
            continue
        best[row["question"]] = max(best.get(row["question"], 0), int(row["marks"]))

    earned = sum(best.values())
    available = sum(slots.values())
    return {**paper_ids.describe(paper), "booklet": booklet,
            "earned": earned, "available": available,
            "percent": percent(earned, available),
            "attempted": len(best), "slots": len(slots)}


# --------------------------------------------------------------------- progress
#
# The chart, plus where in the paper the marks are lost.
#
# CLAUDE.md 8 keeps the subjects' reports apart rather than folding them into one
# endpoint taking a `subject` parameter, and English is the case that shows why
# most plainly. It has neither Science's chains, facets and contextual gate nor
# Chinese's response modes as its natural axis: what a parent wants to know is
# which *section* she is losing marks in -- grammar, vocabulary cloze, editing,
# synthesis -- because that is the unit an English teacher would name and the unit
# the paper is built out of.
#
# The chart is shared, because a bar of marks over a day is the same idea in every
# subject. `db.by_paper_and_day` and `db.kinds_present` are that shared part; the
# booklet is what splits the bar, since the two are practised as separate sittings.


def _attempts(paper: str | None) -> list[dict]:
    """Every logged English attempt, uncapped.

    A booklet is 25 or 40 questions, so `list_attempts`' default cap of 200 is a
    handful of sittings -- and it drops the oldest rows, which is where both the
    best attempt at a question and the start of a trend live (CLAUDE.md 8.3).
    """
    wanted = [paper] if paper is not None else built()
    return [row for p in wanted
            for row in list_attempts(paper=p, subject=SUBJECT, limit=None)]


def _sections(papers: list[str]) -> dict[tuple[str, str, int], dict]:
    """(paper, booklet, question) -> the section it belongs to.

    A property of the paper, so it is read from the index rather than logged with
    the attempt. The name comes from the school's key where there is one and from
    the response mode otherwise, which is the same fallback the practice screen
    uses -- the two must agree, or the report names sections the student never saw.
    """
    out: dict[tuple[str, str, int], dict] = {}
    for paper in papers:
        names = _section_names(paper)
        for booklet in ("A", "B"):
            if paper not in indexed(booklet):
                continue
            data = load_questions(paper, booklet)
            sections = data["sections"]
            for question in data["questions"]:
                section = sections[question["section"]]
                mode = section.get("response_mode", "choose")
                label = (names.get(section["section"]) if booklet == "A" else None)
                out[(paper, booklet, question["question"])] = {
                    "name": label or MODE_NAMES.get(mode, mode),
                    "order": (booklet, section["section"]),
                    "mode": mode,
                }
    return out


# What a section is called when the paper prints no name for it. Booklet A's names
# are on the school's key; Booklet B heads each section with an instruction and no
# title, so the way it is answered names it. Kept in step with english.js's
# MODE_LABEL: a report that names a section differently from the screen the
# student answered it on is describing a paper she did not sit.
MODE_NAMES = {
    "choose": "Multiple choice",
    "letter": "Cloze — choose a word from the list",
    "word": "Fill in the blank",
    "sentence": "Synthesis and transformation",
    "not_built": "Comprehension",
}


def english_kind(row: dict) -> str:
    return "mcq" if row["booklet"] == "A" else "written"


@router.get("/papers/{paper}/progress")
def paper_progress(paper: str) -> dict:
    return _progress(paper)


@router.get("/progress")
def progress_all() -> dict:
    return _progress(None)


def _progress(paper: str | None) -> dict:
    from collections import defaultdict

    wanted = [paper] if paper is not None else built()
    rows = _attempts(paper)
    sections = _sections(wanted)
    # Only what this app marks: the comprehension is served to read and has no
    # answer box, so counting it as untouched work would make every finished
    # booklet look two thirds done.
    slots = sum(1 for entry in sections.values()
                if entry["mode"] != "not_built")

    section_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    booklet_stat: dict[str, dict] = defaultdict(
        lambda: {"earned": 0, "possible": 0, "attempts": 0})
    order: dict[str, tuple] = {}
    best: dict[tuple[str, str, int], dict] = {}
    # Submitted but never marked: a transformed sentence waiting to be self-marked
    # against the model answer. Counted by question rather than by row, because
    # three tries at one question is one thing to go back to.
    awaiting: set[tuple[str, str, int]] = set()

    for row in rows:
        key = (row["paper"], row["booklet"], row["question"])
        if row["marks"] is None:
            awaiting.add(key)
            continue
        if key not in best or row["marks"] > best[key]["marks"]:
            best[key] = row
    awaiting -= best.keys()

    labels = {kind_id: label for kind_id, label, _ in EN_KINDS}
    # Best attempt only, for the reason both other reports use it: the question is
    # what she can do now, not what she got wrong on the way there.
    for key, row in best.items():
        entry = sections.get(key)
        if entry:
            order.setdefault(entry["name"], entry["order"])
            stat = section_stat[entry["name"]]
            stat["earned"] += row["marks"]
            stat["possible"] += row["marks_total"] or 0
            stat["attempts"] += 1
        stat = booklet_stat[labels[english_kind(row)]]
        stat["earned"] += row["marks"]
        stat["possible"] += row["marks_total"] or 0
        stat["attempts"] += 1

    def ranked(stat: dict, printed: bool = False) -> list[dict]:
        out = [{"name": name, **v, "percent": percent(v["earned"], v["possible"])}
               for name, v in stat.items() if v["possible"]]
        if printed:  # sections read in the order the paper prints them
            return sorted(out, key=lambda d: order.get(d["name"], ("Z", 99)))
        return sorted(out, key=lambda d: (d["percent"], -d["possible"]))

    papers = by_paper_and_day(rows, EN_KINDS, english_kind)
    # A bar is labelled with the paper it came from, and for a school paper that
    # is the school -- fifteen bars reading "2026" would say nothing.
    for entry in papers:
        entry.update(paper_ids.describe(entry["paper"]))
    return {
        "subject": SUBJECT,
        "papers_indexed": [paper_ids.describe(p) for p in wanted],
        "papers": papers,
        "kinds": kinds_present(papers, EN_KINDS),
        "sections": ranked(section_stat, printed=True),
        "booklets": ranked(booklet_stat),
        "slots": slots,
        # Attempted but unmarked still counts as touched.
        "untouched": max(0, slots - len(best.keys() | awaiting)),
        "unmarked": len(awaiting),
        "total_attempts": len(rows),
    }


@router.get("/papers/{paper}/attempts/{date}")
def paper_day_attempts(paper: str, date: str) -> dict:
    """What one bar on the chart is made of: every answer given on one day.

    The same contract as the other two subjects' drill-downs (CLAUDE.md 8.4).
    The correct answer appears beside a wrong one, and that is not a leak: only
    questions attempted that day come back, and finishing a booklet shows its key
    at the time of marking, so nothing here was not already seen.
    """
    rows = sorted((row for row in _attempts(paper) if day_of(row) == date),
                  key=lambda row: row["id"])
    sections = _sections([paper])

    expected: dict[tuple[str, int], str] = {}
    for booklet in ("A", "B"):
        if paper not in indexed(booklet):
            continue
        try:
            key = load_key(paper, booklet)
        except HTTPException:
            # The marks were still logged, so the answers are still worth showing
            # -- just without the answer that was right beside them.
            continue
        for entry in key["answers"]:
            expected[(booklet, entry["question"])] = (
                str(entry["answer"]) if booklet == "A"
                else " / ".join(entry.get("accept") or [entry.get("text", "")]))

    groups = []
    for kind_id, name, short in EN_KINDS:
        members = [row for row in rows if english_kind(row) == kind_id]
        if not members:
            continue
        earned = sum(row["marks"] or 0 for row in members)
        possible = sum(row["marks_total"] or 0 for row in members)
        groups.append({
            "id": kind_id, "name": name, "short": short,
            "kind": "choice" if kind_id == "mcq" else "written",
            "earned": earned, "possible": possible,
            "percent": percent(earned, possible), "attempts": len(members),
            "rows": [_attempt_row(row, sections, expected) for row in members],
        })

    return {
        "subject": SUBJECT, **paper_ids.describe(paper), "date": date,
        "earned": sum(row["marks"] or 0 for row in rows),
        "possible": sum(row["marks_total"] or 0 for row in rows),
        "groups": groups,
    }


def _attempt_row(row: dict, sections: dict, expected: dict) -> dict:
    """One logged answer, shaped for reading rather than for re-marking."""
    marks, total = row["marks"], row["marks_total"]
    chosen = row["mode"] == "choose"
    section = sections.get((row["paper"], row["booklet"], row["question"])) or {}
    return {
        "question": row["question"],
        "part": None,
        "label": f"Q{row['question']}",
        "section": section.get("name"),
        "at": row["created_at"],
        "mode": row["mode"],
        "chose": row["answer"] if chosen else None,
        "answer": None if chosen else row["answer"],
        "correct_option": (expected.get((row["booklet"], row["question"]))
                           if chosen else None),
        "expected": None if chosen else expected.get((row["booklet"],
                                                      row["question"])),
        "marks": marks,
        "marks_total": total,
        # Full marks, not "not zero": a 1 of 2 on a sentence is neither right nor
        # wrong, and the UI shows those as marks rather than a verdict.
        "correct": None if marks is None or not total else marks >= total,
        "graded": bool(row["graded"]),
        # Submitted, unmarked, still to be self-marked against the model answer.
        "awaiting": marks is None,
    }
