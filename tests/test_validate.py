"""Tests for the mechanical rubric checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from validate import check_rubric  # noqa: E402


def rubric(**overrides) -> dict:
    base = {
        "question_id": "2024_Q32", "question": 32, "part": "c", "marks": 2,
        "scenario_anchors": ["plant G", "fish C"],
        "mark_model": "per_keypoint",
        "chains": [{"chain_id": "food", "keypoints": [
            {"kp_id": "f1", "position": 1, "facet": "variable",
             "statement": "fewer plant G means less food for bird B", "accepts": []},
            {"kp_id": "f2", "position": 2, "facet": "result",
             "statement": "the number of fish C decreases", "accepts": []},
        ]}],
    }
    base.update(overrides)
    return base


def test_valid_rubric_has_no_problems():
    assert check_rubric(rubric()) == []


def test_unauthored_rubric_is_reported():
    assert check_rubric(rubric(chains=[])) == ["2024_Q32(c): no chains authored"]


def test_keypoint_count_must_match_marks():
    problems = check_rubric(rubric(marks=3))
    assert any("2 keypoints for 3 marks" in p for p in problems)


def test_per_chain_counts_chains_not_keypoints():
    """2024 Q32(c) reaches one conclusion by two routes, each worth a mark."""
    two_routes = rubric(
        mark_model="per_chain", marks=2, chains_required=2,
        chains=[
            {"chain_id": "food", "keypoints": [
                {"kp_id": "f1", "position": 1, "facet": "variable",
                 "statement": "less food for bird B", "accepts": []},
                {"kp_id": "f2", "position": 2, "facet": "result",
                 "statement": "fish C decreases", "accepts": []}]},
            {"chain_id": "oxygen", "keypoints": [
                {"kp_id": "o1", "position": 1, "facet": "variable",
                 "statement": "less photosynthesis", "accepts": []},
                {"kp_id": "o2", "position": 2, "facet": "result",
                 "statement": "fish C decreases", "accepts": []}]},
        ])
    assert check_rubric(two_routes) == []


def test_per_chain_flags_missing_route():
    one_route = rubric(mark_model="per_chain", marks=2, chains_required=2)
    problems = check_rubric(one_route)
    assert any("1 chains for 2 marks" in p for p in problems)


def test_same_facet_on_a_multi_mark_chain_is_flagged():
    split = rubric(chains=[{"chain_id": "x", "keypoints": [
        {"kp_id": "a", "position": 1, "facet": "result", "statement": "one",
         "accepts": []},
        {"kp_id": "b", "position": 2, "facet": "result", "statement": "two",
         "accepts": []}]}])
    assert any("all on facet 'result'" in p for p in check_rubric(split))


def test_anchors_required_for_explanation_questions():
    problems = check_rubric(rubric(scenario_anchors=[]))
    assert any("no scenario anchors" in p for p in problems)


def test_general_gate_exempts_questions_with_no_scenario():
    """"State two functions of roots" has nothing to anchor to."""
    problems = check_rubric(rubric(scenario_anchors=[], context_gate="general"))
    assert not any("no scenario anchors" in p for p in problems)


def test_one_mark_recall_needs_no_anchors():
    single = rubric(marks=1, scenario_anchors=[], chains=[
        {"chain_id": "name", "keypoints": [
            {"kp_id": "n1", "position": 1, "facet": "result",
             "statement": "pollination", "accepts": []}]}])
    assert check_rubric(single) == []


def test_accepts_duplicating_the_statement_is_flagged():
    dup = rubric(chains=[{"chain_id": "x", "keypoints": [
        {"kp_id": "a", "position": 1, "facet": "variable", "statement": "the same",
         "accepts": ["The Same"]},
        {"kp_id": "b", "position": 2, "facet": "result", "statement": "other",
         "accepts": []}]}])
    assert any("identical to its statement" in p for p in check_rubric(dup))


def test_bad_facet_is_flagged():
    bad = rubric(chains=[{"chain_id": "x", "keypoints": [
        {"kp_id": "a", "position": 1, "facet": "cause", "statement": "one",
         "accepts": []},
        {"kp_id": "b", "position": 2, "facet": "result", "statement": "two",
         "accepts": []}]}])
    assert any("has facet 'cause'" in p for p in check_rubric(bad))


def test_duplicate_keypoint_ids_flagged():
    dup = rubric(chains=[{"chain_id": "x", "keypoints": [
        {"kp_id": "same", "position": 1, "facet": "variable", "statement": "one",
         "accepts": []},
        {"kp_id": "same", "position": 2, "facet": "result", "statement": "two",
         "accepts": []}]}])
    assert any("duplicate keypoint ids" in p for p in check_rubric(dup))
