"""Tests for the two-stage grader.

These run without an API key: the mark is computed in code from Stage B's per-link
verdicts, so the scoring rules — the part that decides what a child is told — are
testable without a network call.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from grade import (  # noqa: E402
    ChainVerdict, ContextGate, LinkVerdict, StageBJudgement, _rubric_for_stage_b,
    compute_marks,
)

# 2024 Q32(c): two parallel routes to the same conclusion, one mark each.
PER_CHAIN_RUBRIC = {
    "marks": 2,
    "mark_model": "per_chain",
    "chains_required": 2,
    "scenario_anchors": ["plant G", "bird B", "fish C"],
    "chains": [
        {"chain_id": "food", "keypoints": [
            {"kp_id": "food_1", "position": 1, "facet": "variable",
             "statement": "fewer plant G means less food for bird B", "accepts": []},
            {"kp_id": "food_2", "position": 2, "facet": "action",
             "statement": "bird B eats more fish C", "accepts": []},
            {"kp_id": "food_3", "position": 3, "facet": "result",
             "statement": "fish C decreases", "accepts": []}]},
        {"chain_id": "oxygen", "keypoints": [
            {"kp_id": "oxy_1", "position": 1, "facet": "variable",
             "statement": "less photosynthesis", "accepts": []},
            {"kp_id": "oxy_2", "position": 2, "facet": "action",
             "statement": "less dissolved oxygen", "accepts": []},
            {"kp_id": "oxy_3", "position": 3, "facet": "result",
             "statement": "fish C decreases", "accepts": []}]},
    ],
}

PER_KEYPOINT_RUBRIC = {
    "marks": 2,
    "mark_model": "per_keypoint",
    "scenario_anchors": ["the nest", "fungus L"],
    "chains": [{"chain_id": "conditions", "keypoints": [
        {"kp_id": "con_1", "position": 1, "facet": "variable",
         "statement": "the nest is dark, moist and warm", "accepts": []},
        {"kp_id": "con_2", "position": 2, "facet": "result",
         "statement": "these conditions favour fungus L", "accepts": []}]}],
}


def judgement(statuses: dict[str, str], gate_passed: bool = True,
              **kwargs) -> StageBJudgement:
    by_chain: dict[str, list[LinkVerdict]] = {}
    for kp_id, status in statuses.items():
        chain = "food" if kp_id.startswith("food") else \
                "oxygen" if kp_id.startswith("oxy") else "conditions"
        by_chain.setdefault(chain, []).append(LinkVerdict(kp_id=kp_id, status=status))
    return StageBJudgement(
        context_gate=ContextGate(passed=gate_passed),
        chains=[ChainVerdict(chain_id=c, links=l) for c, l in by_chain.items()],
        improved_answer="...",
        **kwargs,
    )


# ---------------------------------------------------------------- per_chain

def test_both_routes_complete_earns_full_marks():
    all_hit = {k: "hit" for k in
               ("food_1", "food_2", "food_3", "oxy_1", "oxy_2", "oxy_3")}
    assert compute_marks(judgement(all_hit), PER_CHAIN_RUBRIC) == 2


def test_one_complete_route_earns_one_mark():
    """Completing food and omitting oxygen is half the answer, not none of it."""
    statuses = {"food_1": "hit", "food_2": "hit", "food_3": "hit",
                "oxy_1": "broken", "oxy_2": "broken", "oxy_3": "broken"}
    assert compute_marks(judgement(statuses), PER_CHAIN_RUBRIC) == 1


def test_broken_middle_earns_nothing_for_that_route():
    """Both endpoints right with the middle missing is the failure the chain model
    exists to catch (CLAUDE.md 3.1)."""
    statuses = {"food_1": "hit", "food_2": "broken", "food_3": "hit",
                "oxy_1": "broken", "oxy_2": "broken", "oxy_3": "broken"}
    assert compute_marks(judgement(statuses), PER_CHAIN_RUBRIC) == 0


def test_partial_does_not_complete_a_route():
    statuses = {"food_1": "hit", "food_2": "partial", "food_3": "hit",
                "oxy_1": "hit", "oxy_2": "hit", "oxy_3": "hit"}
    assert compute_marks(judgement(statuses), PER_CHAIN_RUBRIC) == 1


# ------------------------------------------------------------- per_keypoint

def test_each_hit_keypoint_is_a_mark():
    assert compute_marks(judgement({"con_1": "hit", "con_2": "hit"}),
                         PER_KEYPOINT_RUBRIC) == 2
    assert compute_marks(judgement({"con_1": "hit", "con_2": "broken"}),
                         PER_KEYPOINT_RUBRIC) == 1
    assert compute_marks(judgement({"con_1": "broken", "con_2": "broken"}),
                         PER_KEYPOINT_RUBRIC) == 0


def test_marks_never_exceed_the_allocation():
    """A hallucinated extra keypoint id must not inflate the mark."""
    statuses = {"con_1": "hit", "con_2": "hit", "invented_3": "hit"}
    assert compute_marks(judgement(statuses), PER_KEYPOINT_RUBRIC) == 2


# ------------------------------------------------------------ contextual gate

def test_failed_gate_is_zero_however_much_science_is_present():
    """A textbook recital that ignores the scenario earns nothing (3.3)."""
    all_hit = {k: "hit" for k in
               ("food_1", "food_2", "food_3", "oxy_1", "oxy_2", "oxy_3")}
    assert compute_marks(judgement(all_hit, gate_passed=False),
                         PER_CHAIN_RUBRIC) == 0


def test_passing_gate_does_not_by_itself_award_anything():
    all_broken = {k: "broken" for k in ("con_1", "con_2")}
    assert compute_marks(judgement(all_broken, gate_passed=True),
                         PER_KEYPOINT_RUBRIC) == 0


# ------------------------------------------------ conventions cannot move marks

def test_convention_notes_do_not_change_the_mark():
    statuses = {"con_1": "hit", "con_2": "hit"}
    without = compute_marks(judgement(statuses), PER_KEYPOINT_RUBRIC)
    with_notes = compute_marks(
        judgement(statuses, convention_notes=["say 'warmer than', not just 'warm'"]),
        PER_KEYPOINT_RUBRIC)
    assert without == with_notes == 2


# --------------------------------------------- stage B never sees the transcript

def test_stage_b_payload_excludes_the_transcript():
    """The guarantee that protects a rambling but correct answer (3.2)."""
    rubric = dict(PER_KEYPOINT_RUBRIC)
    rubric["model_answer"] = "The nest is dark, moist and warm..."
    rubric["explanation"] = "Fungi grow in warm humid places."
    payload = _rubric_for_stage_b(rubric)

    assert "model_answer" not in payload
    assert "explanation" not in payload
    assert "transcript" not in payload


def test_stage_b_payload_is_an_allow_list():
    """A field added to the rubric later must not leak into Stage B by default."""
    rubric = dict(PER_KEYPOINT_RUBRIC)
    rubric["some_future_field"] = "should not appear"
    assert "some_future_field" not in _rubric_for_stage_b(rubric)


def test_stage_b_payload_keeps_what_marking_needs():
    payload = _rubric_for_stage_b(PER_KEYPOINT_RUBRIC)
    assert payload["marks"] == 2
    assert payload["scenario_anchors"] == ["the nest", "fungus L"]
    assert payload["chains"][0]["keypoints"][0]["kp_id"] == "con_1"
    assert payload["chains"][0]["keypoints"][0]["facet"] == "variable"
