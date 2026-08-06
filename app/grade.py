"""Two-stage grading (CLAUDE.md section 3.5).

The split exists to stop a rambling but correct spoken answer being marked down.
Markers ignore phrasing as long as the science is clear, but an LLM judge shown a
raw transcript rewards fluency by default -- and these transcripts are speech, full
of filler and false starts. So:

  Stage A  normalise   transcript -> scientific claims. Awards nothing.
  Stage B  judge       claims -> per-link verdicts. Never sees the transcript.

Stage B is given the claims and the rubric and nothing else. That is enforced here
rather than asked for in a prompt, and tested in tests/test_grade.py.

Two further things are enforced in code rather than trusted to the model:

* The mark is computed from the per-link verdicts according to the rubric's
  mark_model. Stage B judges links; it never reports a total. A model that
  misjudges one link costs one mark instead of inventing a score.
* Convention notes are coaching only and cannot change the mark, because the mark
  is already computed before they are read.

Grading is optional. If the API key is absent or the call fails, the caller gets a
GradingUnavailable and the student can still practise and self-check (section 2.2).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

MODEL = os.environ.get("PSLE_GRADER_MODEL", "claude-opus-5")
MAX_TOKENS = 16000

LinkStatus = Literal["hit", "partial", "broken"]


class GradingUnavailable(RuntimeError):
    """Grading could not run. The practice loop continues without it."""


# --------------------------------------------------------------------- schemas

class NormalisedAnswer(BaseModel):
    """Stage A output. Deliberately carries no marks and no judgement."""

    claims: list[str] = Field(
        description="Each distinct scientific claim the student made, in their own "
                    "meaning but cleaned of filler, repetition and false starts.")
    abandoned: list[str] = Field(
        default_factory=list,
        description="Positions the student stated and then retracted or corrected.")
    incomplete: bool = Field(
        description="True if the answer trails off mid-sentence, so it is an "
                    "unfinished attempt rather than a wrong one.")


class LinkVerdict(BaseModel):
    kp_id: str
    status: LinkStatus
    note: str = Field(
        default="",
        description="Only when status is partial or broken: what is missing, "
                    "addressed to the student.")


class ChainVerdict(BaseModel):
    chain_id: str
    links: list[LinkVerdict]


class ContextGate(BaseModel):
    passed: bool = Field(
        description="False only when the answer is a general recital that never "
                    "operates on this question's specific entities.")
    anchors_used: list[str] = Field(default_factory=list)
    note: str = Field(default="")


class StageBJudgement(BaseModel):
    """Stage B output. Note the absence of any total -- the mark is computed."""

    context_gate: ContextGate
    chains: list[ChainVerdict]
    missed_summary: list[str] = Field(
        default_factory=list,
        description="What was missing, as a next step rather than a failure.")
    improved_answer: str = Field(
        description="The student's own answer rewritten to earn full marks, "
                    "staying as close to their wording as possible.")
    convention_notes: list[str] = Field(
        default_factory=list,
        description="Comparative language, 'gains/loses heat', pronoun ambiguity. "
                    "Coaching only. Never spelling or grammar.")


@dataclass
class Grade:
    marks_awarded: int
    marks_total: int
    context_gate: ContextGate
    chains: list[ChainVerdict]
    missed_summary: list[str]
    improved_answer: str
    convention_notes: list[str]
    claims: list[str]
    incomplete_attempt: bool
    model: str = MODEL
    stage_b_saw_transcript: bool = False  # always False; recorded for the record

    def as_dict(self) -> dict:
        return {
            "marks_awarded": self.marks_awarded,
            "marks_total": self.marks_total,
            "context_gate": self.context_gate.model_dump(),
            "chains": [c.model_dump() for c in self.chains],
            "missed_summary": self.missed_summary,
            "improved_answer": self.improved_answer,
            "convention_notes": self.convention_notes,
            "claims": self.claims,
            "incomplete_attempt": self.incomplete_attempt,
            "model": self.model,
        }


# --------------------------------------------------------------------- prompts

STAGE_A_SYSTEM = """\
You extract the scientific content of a primary-school student's spoken answer.

This is a speech-to-text transcript from an 11-year-old. It contains filler, false \
starts, repetition and mis-transcribed words. None of that is a mistake by the \
student and none of it is yours to judge.

Rules:
- List each distinct scientific claim, in the student's own meaning, cleaned up.
- Do not merge two claims into one, and do not split one claim into two.
- Do not add anything the student did not say, however obvious it seems.
- On self-correction, take the FINAL stated position. Put the abandoned one in \
`abandoned`.
- If the answer trails off mid-sentence, set `incomplete` -- an unfinished attempt \
is not a wrong one.
- Award nothing. Judge nothing. You are not marking.
"""

STAGE_B_SYSTEM = """\
You mark a primary-school science answer against a marking rubric, the way a \
Singapore PSLE marker would.

You are given the student's scientific claims -- not their words. Phrasing, \
grammar and spelling are already gone and are irrelevant to the mark. Never \
mention them.

How to judge:
- For each keypoint, decide `hit`, `partial` or `broken` against its statement and \
its accepted paraphrases. Accept any wording that carries the same science.
- Marks are awarded link by link. A chain with correct endpoints but a missing \
middle is broken at the middle -- say which link, not that the answer is wrong.
- The contextual gate comes first and is separate from the keypoints. It fails \
ONLY when the answer is a general recital that never operates on this question's \
specific entities. An answer that names them and is merely incomplete PASSES the \
gate and is marked normally.
- `improved_answer` rewrites the STUDENT'S answer so it would earn full marks, \
keeping as much of their own phrasing as possible. It is not a model answer.
- `convention_notes` are coaching only and never affect the mark: comparative \
language ("faster than", not just "faster"), "gains/loses heat" rather than \
"loses energy", ambiguous pronouns. Never spelling. Never grammar.

Tone: you are talking to an 11-year-old. Specific and encouraging. Never sarcastic, \
never "you failed to". Frame every gap as the next step.
"""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise GradingUnavailable("the anthropic SDK is not installed") from exc
    try:
        return anthropic.Anthropic()
    except Exception as exc:
        raise GradingUnavailable(f"could not create an API client: {exc}") from exc


def normalise(transcript: str, question_context: str = "") -> NormalisedAnswer:
    """Stage A. Extract claims from the raw transcript. Awards nothing."""
    if not transcript.strip():
        return NormalisedAnswer(claims=[], abandoned=[], incomplete=True)

    prompt = (f"Question context (for disambiguating references only):\n"
              f"{question_context}\n\n" if question_context else "")
    prompt += f"Transcript of the spoken answer:\n{transcript}"

    try:
        response = _client().messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=STAGE_A_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=NormalisedAnswer,
        )
    except Exception as exc:
        raise GradingUnavailable(f"stage A failed: {exc}") from exc
    return response.parsed_output


def _rubric_for_stage_b(rubric: dict) -> dict:
    """Exactly what Stage B is allowed to see.

    Built by allow-list rather than by deleting the transcript from a wider blob:
    a field added to the rubric later cannot leak in by accident.
    """
    return {
        "marks": rubric.get("marks"),
        "mark_model": rubric.get("mark_model", "per_keypoint"),
        "chains_required": rubric.get("chains_required", 1),
        "context_gate": rubric.get("context_gate", "anchored"),
        "scenario_anchors": rubric.get("scenario_anchors", []),
        "traps": rubric.get("traps", []),
        "chains": [
            {
                "chain_id": chain.get("chain_id"),
                "keypoints": [
                    {"kp_id": kp.get("kp_id"), "position": kp.get("position"),
                     "facet": kp.get("facet"), "statement": kp.get("statement"),
                     "accepts": kp.get("accepts", [])}
                    for kp in chain.get("keypoints", [])
                ],
            }
            for chain in rubric.get("chains", [])
        ],
    }


def judge(claims: list[str], rubric: dict) -> StageBJudgement:
    """Stage B. Match claims against the rubric. Never sees the transcript."""
    payload = {
        "student_claims": claims,
        "rubric": _rubric_for_stage_b(rubric),
    }
    try:
        response = _client().messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=STAGE_B_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
            output_format=StageBJudgement,
        )
    except Exception as exc:
        raise GradingUnavailable(f"stage B failed: {exc}") from exc
    return response.parsed_output


def compute_marks(judgement: StageBJudgement, rubric: dict) -> int:
    """Derive the mark from the per-link verdicts.

    Stage B never reports a total. Computing it here means the mark always follows
    the rubric's own mark model, a misjudged link costs exactly one mark rather
    than moving an invented score, and convention notes cannot touch it.

    A failed contextual gate is zero however much correct science is present --
    a memorised recital that ignores the scenario earns nothing (section 3.3).
    """
    total = rubric.get("marks") or 0
    if not judgement.context_gate.passed:
        return 0

    status: dict[str, str] = {
        link.kp_id: link.status
        for chain in judgement.chains for link in chain.links
    }

    if rubric.get("mark_model") == "per_chain":
        # One mark per route completed end to end.
        awarded = 0
        for chain in rubric.get("chains", []):
            keypoints = chain.get("keypoints", [])
            if keypoints and all(status.get(kp.get("kp_id")) == "hit"
                                 for kp in keypoints):
                awarded += 1
        return min(awarded, total)

    # per_keypoint: each link is a mark.
    awarded = sum(1 for chain in rubric.get("chains", [])
                  for kp in chain.get("keypoints", [])
                  if status.get(kp.get("kp_id")) == "hit")
    return min(awarded, total)


def grade(transcript: str, rubric: dict, question_context: str = "") -> Grade:
    """Run the full sequence and return a mark plus specific feedback."""
    normalised = normalise(transcript, question_context)
    if not normalised.claims:
        return Grade(
            marks_awarded=0,
            marks_total=rubric.get("marks") or 0,
            context_gate=ContextGate(
                passed=True, anchors_used=[],
                note="There was nothing to mark yet — have another go."),
            chains=[], missed_summary=[], improved_answer="",
            convention_notes=[], claims=[],
            incomplete_attempt=True,
        )

    judgement = judge(normalised.claims, rubric)
    return Grade(
        marks_awarded=compute_marks(judgement, rubric),
        marks_total=rubric.get("marks") or 0,
        context_gate=judgement.context_gate,
        chains=judgement.chains,
        missed_summary=judgement.missed_summary,
        improved_answer=judgement.improved_answer,
        convention_notes=judgement.convention_notes,
        claims=normalised.claims,
        incomplete_attempt=normalised.incomplete,
    )
