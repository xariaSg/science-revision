"""Unit tests for how English answers are marked.

Booklet A is a comparison of digits and needs no test beyond the one below.
Booklet B is a comparison of *text*, and text comparison is where the judgement
calls are: what counts as the same answer, what is fed back rather than deducted,
and where the rule inverts against the rest of the project — spelling is the
assessed object in an editing question, so a misspelling is wrong here even
though CLAUDE.md 3.2 says never to deduct for one in Science.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from fastapi import HTTPException  # noqa: E402

import english  # noqa: E402


def entry(marks=1):
    return {"marks": marks}


def key(*accept):
    return {"accept": list(accept)}


# --------------------------------------------------------------- normalisation

def test_case_and_surrounding_punctuation_are_ignored():
    assert english.normalise('  "Despite," ') == "despite"


def test_inner_punctuation_survives():
    """"don't" and "dont" are not the same word, and neither are "well-known"
    and "well known"."""
    assert english.normalise("don't") == "don't"
    assert english.normalise("well-known") == "well-known"


def test_whitespace_is_collapsed():
    assert english.normalise("no   sooner\nhad") == "no sooner had"


# ------------------------------------------------------------ a typed answer

def test_the_right_word_earns_the_mark():
    result = english._mark_typed(entry(), key("commemorate"), "commemorate")
    assert result["correct"] and result["marks"] == 1


def test_a_misspelling_is_wrong():
    """The rule that inverts. These are editing and cloze questions, so the word
    is the answer — marking "commemerate" right would teach the misspelling."""
    result = english._mark_typed(entry(), key("commemorate"), "commemerate")
    assert not result["correct"] and result["marks"] == 0


def test_case_is_fed_back_not_deducted():
    """"Despite" opens a sentence in the passage. A child who typed "despite" has
    the English right, so the mark stands and the convention is taught."""
    result = english._mark_typed(entry(), key("Despite"), "despite")
    assert result["correct"] and result["marks"] == 1
    assert "Despite" in result["note"]


def test_no_note_when_the_answer_matches_exactly():
    assert "note" not in english._mark_typed(entry(), key("groups"), "groups")


def test_either_the_letter_or_the_word_is_accepted():
    """The key prints "F (had)". A child who understood the blank may write
    either, and both mean they understood it."""
    for given in ("F", "f", "had"):
        assert english._mark_typed(entry(), key("F", "had"), given)["correct"]


def test_a_second_acceptable_answer_also_earns_the_mark():
    assert english._mark_typed(entry(), key("F", "G", "had", "have"),
                               "have")["correct"]


def test_an_empty_answer_is_rejected_rather_than_marked_zero():
    """Nothing to mark is not the same as a wrong answer, and logging it as one
    would put a zero in the progress report the student never earned."""
    with pytest.raises(HTTPException):
        english._mark_typed(entry(), key("had"), "   ")


def test_the_expected_answers_come_back_with_the_verdict():
    result = english._mark_typed(entry(), key("F", "had"), "Q")
    assert result["expected"] == ["F", "had"]


# --------------------------------------------------------------- a chosen answer

def test_the_right_option_earns_the_mark():
    result = english._mark_choice(entry(), {"answer": 2}, 2)
    assert result["correct"] and result["marks"] == 1


def test_the_wrong_option_earns_nothing_and_shows_the_answer():
    result = english._mark_choice(entry(), {"answer": 4}, 1)
    assert not result["correct"] and result["marks"] == 0
    assert result["answer"] == 4


def test_an_option_outside_1_to_4_is_rejected():
    for choice in (0, 5, "2", None):
        with pytest.raises(HTTPException):
            english._mark_choice(entry(), {"answer": 2}, choice)
