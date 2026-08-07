"""Marking for the written Chinese Paper 2 questions.

Deliberately not the Science grader. That one exists to stop a rambling *spoken*
answer being marked down: Stage A strips filler out of a transcript before Stage B
ever sees it, and keypoints are ordered links in a cause-and-effect chain. Neither
applies here. Chinese answers are typed, so there is no filler to strip, and a
comprehension answer is an unordered set of retrievable points -- Q38's four marks
are four separate observations, not a chain that breaks in the middle.

Two of the seven written questions never reach the model at all. 文中表示"..."的
词语是____ has exactly one right answer, a single word lifted from the passage, and
comparing two short strings is both more reliable than asking a model and free.

What is enforced in code rather than asked for in a prompt:

* The mark is computed from the per-keypoint verdicts. The model judges keypoints
  one at a time and never reports a total, so a misjudged keypoint costs its own
  marks instead of inventing a score.
* Nothing awards or deducts for handwriting, 错别字 or phrasing. Marks for 语言
  quality exist in this paper, but only on the writing task, which is self-marked
  and never arrives here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

MODEL = os.environ.get("PSLE_GRADER_MODEL", "claude-opus-5")
MAX_TOKENS = 8000

KeypointStatus = Literal["hit", "partial", "miss"]

# A question whose answer is a single word lifted from the passage. Anything
# longer is a constructed answer and goes to the model.
EXACT_MATCH_MAX_CHARS = 6
# Punctuation and whitespace a child may add around a one-word answer.
STRIP = "。，、；：？！,.;:?!\"'“”‘’ 　\t\n"


class GradingUnavailable(RuntimeError):
    """Raised when the grader cannot run. The student self-marks instead."""


class KeypointVerdict(BaseModel):
    kp_id: str
    status: KeypointStatus
    evidence: str = Field("", description="the words in the answer that earned it")
    missing: str = Field("", description="what a full answer would have added")


class Judgement(BaseModel):
    verdicts: list[KeypointVerdict]
    feedback: str = Field("", description="one or two sentences for the student")


@dataclass
class Grade:
    marks: int
    marks_total: int
    verdicts: list[dict] = field(default_factory=list)
    feedback: str = ""
    method: str = "model"
    model_answer: str = ""
    note: str = ""


def _normalise(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip(STRIP)


def is_exact_match_question(rubric: dict) -> bool:
    points = rubric.get("keypoints") or []
    return (len(points) == 1
            and len(_normalise(points[0]["statement"])) <= EXACT_MATCH_MAX_CHARS)


def grade_exact(answer: str, rubric: dict) -> Grade:
    """Mark a one-word answer by comparing it with the key."""
    point = rubric["keypoints"][0]
    wanted = _normalise(point["statement"])
    got = _normalise(answer)
    correct = got == wanted
    return Grade(
        marks=int(point["marks"]) if correct else 0,
        marks_total=rubric["marks"],
        verdicts=[{"kp_id": point["kp_id"], "status": "hit" if correct else "miss",
                   "evidence": answer if correct else "",
                   "missing": "" if correct else point["statement"]}],
        feedback=("对了。" if correct else
                  f"这题要的是文中的一个词语：{point['statement']}。"),
        method="exact",
        model_answer=rubric["model_answer"],
        note=rubric.get("note", ""),
    )


def _client():
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise GradingUnavailable("the anthropic SDK is not installed") from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GradingUnavailable("ANTHROPIC_API_KEY is not set")
    try:
        return Anthropic()
    except Exception as exc:  # pragma: no cover - environment dependent
        raise GradingUnavailable(f"could not create an API client: {exc}") from exc


SYSTEM = """You mark one answer from a Singapore PSLE Chinese Paper 2 reading \
comprehension question, written by a Primary 6 student.

You are given the marking points and the student's answer. Judge each marking \
point separately and report a status for each:

  hit      the answer clearly makes this point
  partial  the answer gestures at it but leaves out something the point requires
  miss     the answer does not make this point

Rules you must follow:

* Judge meaning, not wording. The student does not need the key's phrasing. An \
answer in their own words that says the same thing is a hit.
* Never comment on 错别字, handwriting, grammar or style, and never let any of \
them change a status. Only the content is being marked.
* Do not report a total or a score. You judge points; the marks are computed \
from your statuses.
* Where the question invites the student's own view, any reasonable view is \
acceptable -- judge whether they supported it, not whether it matches the key.
* Write `feedback` in simple Chinese, addressed to the student, warm and \
specific. Say what they got and what the next step is. Never say they failed."""


def judge(answer: str, rubric: dict) -> Judgement:
    client = _client()
    payload = {
        "marking_points": [
            {"kp_id": p["kp_id"], "marks": p["marks"], "point": p["statement"]}
            for p in rubric["keypoints"]
        ],
        "total_marks": rubric["marks"],
        "student_answer": answer,
        "open_response": rubric.get("free_response", False),
    }
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            tools=[{
                "name": "report",
                "description": "Report a status for every marking point.",
                "input_schema": Judgement.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": "report"},
            messages=[{"role": "user",
                       "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except Exception as exc:
        raise GradingUnavailable(f"grading failed: {exc}") from exc

    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return Judgement.model_validate(block.input)
    raise GradingUnavailable("the grader returned no judgement")


def compute_marks(judgement: Judgement, rubric: dict) -> int:
    """Marks from the verdicts, in code. A partial earns nothing.

    Each keypoint carries its own value because the publisher prints it that way
    -- Q39's first point is worth 2 and its other two are worth 1 each -- so the
    total cannot be recovered by counting hits.
    """
    values = {p["kp_id"]: p["marks"] for p in rubric["keypoints"]}
    earned = sum(values.get(v.kp_id, 0) for v in judgement.verdicts
                 if v.status == "hit")
    return int(min(earned, rubric["marks"]))


def grade(answer: str, rubric: dict) -> Grade:
    if not (answer or "").strip():
        raise GradingUnavailable("no answer to mark")
    if is_exact_match_question(rubric):
        return grade_exact(answer, rubric)

    judgement = judge(answer, rubric)
    return Grade(
        marks=compute_marks(judgement, rubric),
        marks_total=rubric["marks"],
        verdicts=[v.model_dump() for v in judgement.verdicts],
        feedback=judgement.feedback,
        method="model",
        model_answer=rubric["model_answer"],
        note=rubric.get("note", ""),
    )
