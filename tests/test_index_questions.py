"""Unit tests for the Booklet B question inventory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from index_questions import (  # noqa: E402
    MARK_CANDIDATE_RE, MARKS_RE, MAX_MARKS, MIN_MARKS, QUESTION_RE, SUBPART_RE,
    TOTAL_MARKS_RE,
)


def test_question_number_with_or_without_trailing_stop():
    """Full papers OCR "37" bare; the Booklet B extracts render it as "37."."""
    assert QUESTION_RE.match("32").group(1) == "32"
    assert QUESTION_RE.match("37.").group(1) == "37"
    assert QUESTION_RE.match("21,").group(1) == "21"


def test_question_number_rejects_non_numbers():
    assert QUESTION_RE.match("32a") is None
    assert QUESTION_RE.match("(3)") is None


def test_subpart_labels():
    assert SUBPART_RE.match("(a)").group(1) == "a"
    assert SUBPART_RE.match("(ii)").group(1) == "ii"
    assert SUBPART_RE.match("(1)") is None


def test_marks_parsed_from_brackets():
    assert MARKS_RE.findall("Explain why. [1]") == ["1"]
    assert MARKS_RE.findall("answer. [3]") == ["3"]


def test_mark_candidate_matches_mangled_brackets():
    """2024 Q29(a)'s "[2]" is read as "{?]" on the full page."""
    for token in ("{?]", "[?]", "(2]", "|1]"):
        assert MARK_CANDIDATE_RE.match(token), token


def test_mark_candidate_ignores_ordinary_words():
    for token in ("plant", "roots.", "(a)"):
        assert MARK_CANDIDATE_RE.match(token) is None, token


def test_mark_bounds_reject_invented_digits():
    """The digit whitelist returned "7" for a glyph it could not read."""
    assert not MIN_MARKS <= 7 <= MAX_MARKS
    assert not MIN_MARKS <= 0 <= MAX_MARKS
    for value in (1, 2, 3):
        assert MIN_MARKS <= value <= MAX_MARKS


def test_total_marks_parsed():
    text = ("in brackets [ ] at the end of each question or part question. "
            "(44 marks)")
    assert int(TOTAL_MARKS_RE.search(text).group(1)) == 44
