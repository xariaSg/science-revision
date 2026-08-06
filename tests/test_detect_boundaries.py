"""Unit tests for boundary-detection signal parsing.

These run on OCR text fixtures rather than on the papers, which are gitignored --
the point is to pin the parsing rules, not to re-verify the scans.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from contact_sheet import section_of  # noqa: E402
from detect_boundaries import page_signals  # noqa: E402

# Verbatim from work/2025/ocr/page-001.txt -- the Booklet A cover.
COVER_A_2025 = """MINISTRY OF EDUCATION, SINGAPORE
PRIMARY SCHOOL LEAVING EXAMINATION
0009/2 (A)

a This booklet consists of 15 printed pages and 1 blank page.
Singapore Examinations and Assessment Board
"""

# Verbatim from work/2024/ocr/page-001.txt -- no blank-page clause.
COVER_A_2024 = """MINISTRY OF EDUCATION, SINGAPORE
0009/2 (A)
This booklet consists of 16 printed pages.
"""

COVER_B = """PASTE YOUR BARCODE LABEL HERE
MINISTRY OF EDUCATION, SINGAPORE
0009/2 (B)
This booklet consists of 12 printed pages.
"""

BLANK = """16

BLANK PAGE

Copyright Acknowledgements:
"""


def test_cover_a_with_blank_clause():
    s = page_signals(COVER_A_2025)
    assert s["printed_pages"] == 15
    assert s["blank_pages"] == 1
    assert s["code_a"] and not s["code_b"]


def test_cover_a_without_blank_clause():
    s = page_signals(COVER_A_2024)
    assert s["printed_pages"] == 16
    assert s["blank_pages"] == 0


def test_cover_a_is_not_a_blank_page():
    """The cover says "and 1 blank page"; that must not mark the cover itself blank."""
    assert page_signals(COVER_A_2025)["blank_page"] is False


def test_blank_page_heading_detected():
    assert page_signals(BLANK)["blank_page"] is True


def test_booklet_b_cover():
    s = page_signals(COVER_B)
    assert s["barcode_cover"] is True
    assert s["printed_pages"] == 12


def test_paper_code_a_not_read_as_b():
    """"0009/02(A)" also satisfies a loose B pattern; A must win."""
    s = page_signals("(Go on to the next page) 0009/02(A)")
    assert s["code_a"] is True


def test_paper_code_b():
    s = page_signals("(Go on to the next page) 0009/2B")
    assert s["code_b"] is True and s["code_a"] is False


def test_goto_booklet_b_marker():
    assert page_signals("(Go on to Booklet B) 0009/02(A)")["goto_booklet_b"] is True


def test_answers_marker():
    assert page_signals("PSLE Yearly Science - Answers")["answers"] is True
    assert page_signals("© Educational Publishing House Pte Ltd")["answers"] is True


BOUNDS_2025 = {
    "year": 2025,
    "booklet_a": {"start": 1, "end": 16},
    "booklet_b": {"start": 17, "end": 28},
    "answers": {"start": 29, "end": 34},
    "blank_pages": [16],
}


def test_section_assignment():
    assert section_of(1, BOUNDS_2025) == "A"
    assert section_of(15, BOUNDS_2025) == "A"
    assert section_of(16, BOUNDS_2025) == "blank"
    assert section_of(17, BOUNDS_2025) == "B"
    assert section_of(28, BOUNDS_2025) == "B"
    assert section_of(29, BOUNDS_2025) == "answers"
