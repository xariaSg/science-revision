"""Unit tests for Chinese written-answer marking.

The mark is computed here, not by the model. Stage B reports a status per
keypoint and never a total, so these tests pin the arithmetic that turns statuses
into marks -- including the case that makes counting hits wrong, where keypoints
are worth different amounts.

The other thing worth pinning is the questions that never reach the model at all.
"文中表示…的词语是____" has exactly one right answer, and comparing two short
strings beats asking a model about it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from cn_grade import (  # noqa: E402
    Judgement, KeypointVerdict, compute_marks, grade_exact,
    is_exact_match_question,
)


def rubric(points, marks, **extra):
    out = {
        "marks": marks,
        "model_answer": "".join(f"{p['statement']}（{p['marks']:g}）" for p in points),
        "keypoints": points,
        "note": "",
    }
    out.update(extra)
    return out


def kp(kp_id, statement, marks):
    return {"kp_id": kp_id, "position": 1, "marks": marks, "statement": statement}


# ------------------------------------------------------------- one-word answers

def test_a_single_short_keypoint_is_marked_by_comparison():
    assert is_exact_match_question(rubric([kp("kp_1", "插嘴", 2)], 2))


def test_a_constructed_answer_is_not():
    points = [kp("kp_1", "贝贝的两个哥哥经常吵架", 1), kp("kp_2", "因为二哥争做老大", 1)]
    assert not is_exact_match_question(rubric(points, 2))


def test_the_right_word_earns_the_marks():
    result = grade_exact("插嘴", rubric([kp("kp_1", "插嘴", 2)], 2))
    assert (result.marks, result.method) == (2, "exact")
    assert result.verdicts[0]["status"] == "hit"


def test_punctuation_and_spacing_around_the_word_are_ignored():
    """A child typing the answer may add a full stop; the science is the word."""
    for written in ("插嘴。", " 插嘴 ", "插嘴，"):
        assert grade_exact(written, rubric([kp("kp_1", "插嘴", 2)], 2)).marks == 2


def test_a_different_word_earns_nothing_and_is_told_which_was_wanted():
    result = grade_exact("抢话", rubric([kp("kp_1", "插嘴", 2)], 2))
    assert result.marks == 0
    assert "插嘴" in result.feedback


# --------------------------------------------------------------- computed marks

def test_marks_come_from_the_verdicts():
    points = [kp("kp_1", "甲", 1), kp("kp_2", "乙", 1), kp("kp_3", "丙", 1)]
    judgement = Judgement(verdicts=[
        KeypointVerdict(kp_id="kp_1", status="hit"),
        KeypointVerdict(kp_id="kp_2", status="hit"),
        KeypointVerdict(kp_id="kp_3", status="miss"),
    ])
    assert compute_marks(judgement, rubric(points, 3)) == 2


def test_keypoints_are_worth_what_they_are_worth_not_one_each():
    """Q39's first point is worth 2. Counting hits would score this 1."""
    points = [kp("kp_1", "妈妈是个聪明的人", 2), kp("kp_2", "她用了妙招", 1)]
    judgement = Judgement(verdicts=[KeypointVerdict(kp_id="kp_1", status="hit")])
    assert compute_marks(judgement, rubric(points, 3)) == 2


def test_a_partial_earns_nothing():
    points = [kp("kp_1", "甲", 1), kp("kp_2", "乙", 1)]
    judgement = Judgement(verdicts=[
        KeypointVerdict(kp_id="kp_1", status="partial"),
        KeypointVerdict(kp_id="kp_2", status="hit"),
    ])
    assert compute_marks(judgement, rubric(points, 2)) == 1


def test_the_total_cannot_exceed_the_question():
    """A model that invents a keypoint, or reports one twice, cannot inflate the
    mark past what the paper allows."""
    points = [kp("kp_1", "甲", 1), kp("kp_2", "乙", 1)]
    judgement = Judgement(verdicts=[
        KeypointVerdict(kp_id="kp_1", status="hit"),
        KeypointVerdict(kp_id="kp_1", status="hit"),
        KeypointVerdict(kp_id="kp_2", status="hit"),
    ])
    assert compute_marks(judgement, rubric(points, 2)) == 2


def test_an_unknown_keypoint_id_awards_nothing():
    points = [kp("kp_1", "甲", 1)]
    judgement = Judgement(verdicts=[KeypointVerdict(kp_id="invented", status="hit")])
    assert compute_marks(judgement, rubric(points, 1)) == 0
