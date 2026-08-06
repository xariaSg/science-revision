"""Unit tests for answer segmentation.

Every case here is a bug that actually occurred against the 2024/2025 answer pages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from segment_answers import (  # noqa: E402
    QUESTION_RE, SUBPART_RE, SEPARATOR_RE, QUESTION_RANGE_RE, Word, find_gutter,
)


def test_question_number_accepts_full_stop_and_comma():
    """OCR reads 2024's "21." as "21,"."""
    assert QUESTION_RE.match("29.").group(1) == "29"
    assert QUESTION_RE.match("21,").group(1) == "21"


def test_question_number_rejects_colon():
    """2025 Q37 is a procedure: "Step 1:", "Step 2:" ... Those are not questions."""
    assert QUESTION_RE.match("2:") is None
    assert QUESTION_RE.match("6:") is None


def test_question_number_rejects_bare_digits():
    assert QUESTION_RE.match("29") is None


def test_subpart_letters_and_romans():
    assert SUBPART_RE.match("(a)").group(1) == "a"
    assert SUBPART_RE.match("(b)").group(1) == "b"
    assert SUBPART_RE.match("(ii)").group(1) == "ii"
    assert SUBPART_RE.match("(iv)").group(1) == "iv"


def test_subpart_accepts_at_sign_for_a():
    """Tesseract reads 2024 Q37's "(a)" as "@)"."""
    assert SUBPART_RE.match("@)").group(1) == "@"


def test_subpart_rejects_digits():
    """"(1)"..."(4)" are Booklet A's MCQ answer values, not sub-part labels."""
    for token in ("(1)", "(3)", "(4)"):
        assert SUBPART_RE.match(token) is None


def test_separator_matches_dotted_rule_artifacts():
    for token in (":", "|", ";", "}", "!", "'"):
        assert SEPARATOR_RE.match(token)


def test_separator_does_not_match_content():
    for token in ("(a)", "29.", "13", "the"):
        assert SEPARATOR_RE.match(token) is None


def test_question_range_parsed_from_booklet_b_instructions():
    match = QUESTION_RANGE_RE.search(
        "For questions 29 to 40, write your answers in this booklet.")
    assert (int(match.group(1)), int(match.group(2))) == (29, 40)


def _row(x0: int, x1: int, y: int) -> Word:
    return Word("x", x0, y, x1, y + 40)


def test_find_gutter_prefers_centre_band_over_wider_one():
    """2025 p34: the widest band is the right column's own label/body gap.

    Layout: left body [300..1200], "40." [1224..1330], right body [1378..2200].
    The gap [1330..1378] is wider than the true gutter [1200..1224], so picking the
    widest band puts "40." in the left column and loses the question.
    """
    words = []
    for y in range(200, 3000, 100):
        words.append(_row(300, 1200, y))
        words.append(_row(1378, 2200, y))
    words.append(_row(1224, 1330, 500))

    gutter = find_gutter(words, 2480, 3509)
    assert 1200 <= gutter <= 1224, gutter
    assert (1224 + 1330) / 2 > gutter, "'40.' must fall in the right column"


def test_find_gutter_ignores_narrow_noise():
    words = []
    for y in range(200, 3000, 100):
        words.append(_row(300, 1235, y))
        words.append(_row(1245, 2200, y))
    # A 10px gap inside the left column must not be mistaken for the gutter.
    words = [w for w in words if not (w.left == 300 and w.top == 500)]
    words.append(_row(300, 800, 500))
    words.append(_row(810, 1235, 500))

    assert 1235 <= find_gutter(words, 2480, 3509) <= 1245
