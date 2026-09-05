"""Unit tests for the English Booklet A inventory.

The failures that matter here are the silent ones. A question shown without the
poster it asks about is unanswerable and looks fine; a question that swallows
Booklet B's passage shows a child the wrong page under the right number; and a
section whose stated marks disagree with what was found is a paper indexed
wrongly rather than not at all. Each has a test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from en_index import (  # noqa: E402
    MARKS_RE, RANGE_MENTION_RE, SECTION_RE, find_context, find_handover,
    pages_of, read_sections,
)


def line(text, left=400, top=100, height=50, width=1400):
    return Line(text, left, top, left + width, top + height, 1.0)


def rows(*entries):
    """(page, text) pairs -> the (page, Line) list the module works on."""
    return [(page, line(text, top=100 + 60 * i))
            for i, (page, text) in enumerate(entries)]


# ---------------------------------------------------- what the paper says it is

def test_section_header_is_read():
    match = SECTION_RE.search(
        "For each question from 1 to 10, four options are given.")
    assert (match.group("first"), match.group("last")) == ("1", "10")


def test_section_header_without_from():
    """Worded differently by different schools; both halves are optional."""
    match = SECTION_RE.search("For questions 21 to 25, choose the best answer.")
    assert (match.group("first"), match.group("last")) == ("21", "25")


def test_marks_are_read_from_their_own_line():
    assert MARKS_RE.search("(10 marks)").group("marks") == "10"
    assert MARKS_RE.search("[5 marks]").group("marks") == "5"


def test_per_question_allocation_is_not_a_section_total():
    """The comprehension writes "[2m]" and "(1m)"; neither is a section total."""
    assert MARKS_RE.search("state two ways [2m]") is None


def test_four_sections_with_their_own_totals():
    found = read_sections(rows(
        (2, "For each question from 1 to 10, four options are given."),
        (2, "(10 marks)"),
        (4, "For each question from 11 to 15, four options are given."),
        (4, "(5 marks)"),
    ))
    assert [(s["first"], s["last"], s["marks"]) for s in found] == [
        (1, 10, 10), (11, 15, 5)]


def test_marks_line_below_the_instruction_belongs_to_it():
    """The total is right-aligned on its own line, one or two rows down, and can
    land between the lines of the instruction it belongs to."""
    found = read_sections(rows(
        (5, "For each question from 16 to 20, choose the word(s) closest in"),
        (5, "(5 marks)"),
        (5, "meaning to the underlined word(s)."),
    ))
    assert found[0]["marks"] == 5


def test_a_sections_marks_are_not_taken_from_the_next_one():
    found = read_sections(rows(
        (2, "For each question from 1 to 10, four options are given."),
        (4, "For each question from 11 to 15, four options are given."),
        (4, "(5 marks)"),
    ))
    # Nothing between Q1-10's own row and Q11-15's states a total for it, so it
    # falls back to the one-mark-per-question invariant rather than picking up
    # Q11-15's "(5 marks)" -- assumed at its own question count (10), not 5.
    assert found[0]["marks"] == 10
    assert found[0]["marks_source"] == "assumed"
    assert found[1]["marks"] == 5
    assert found[1]["marks_source"] == "stated"


# --------------------------------------------------------- stimulus and handover

def test_stimulus_statement_is_not_a_section_header():
    """"...and answer questions 21 to 25" introduces material; "For each question
    from 21 to 25" asks them. Only the second opens a section."""
    text = "Study the poster (Text 1) and answer questions 21 to 25."
    assert SECTION_RE.search(text) is None
    assert RANGE_MENTION_RE.search(text).group("first") == "21"


def test_context_pages_are_found_for_a_later_section():
    data = rows(
        (5, "(4) not appealing"),                       # the last option of Q20
        (6, "Study the poster (Text 1) and the extract from an article and answer"),
        (6, "questions 21 to 25."),
        (7, "School bags are designed to be both roomy and trendy."),
    )
    found = find_context(data, 1, len(data), later={21, 22, 23, 24, 25})
    assert found is not None
    boundary, span = found
    assert span == {21, 22, 23, 24, 25}
    # The boundary is the *first* row of the page, not the row that matched. The
    # sentence is split across two rows and cutting at the second leaves the first
    # in the previous question's page span.
    assert boundary == 1


def test_a_range_outside_the_booklet_is_not_a_stimulus():
    """"questions 66 to 75 in Booklet B" names the other booklet, not this one."""
    data = rows((9, "the passage for Comprehension questions 66 to 75 in Booklet B"))
    assert find_context(data, 0, len(data), later={21, 22, 23, 24, 25}) is None


def test_handover_ends_booklet_a():
    data = rows(
        (9, "(4) students should fit everything into their school bags"),
        (9, "Please note that the passage for questions 66 to 75 in Booklet B"),
        (10, "Refer to the passage below when you answer questions 66 to 75."),
    )
    assert find_handover(data, after=0) == 1


def test_handover_is_not_found_before_the_last_question():
    """The cover says "Total Time for Booklets A and B". Searching from the start
    would truncate the booklet at page one."""
    data = rows(
        (1, "Total Time for Booklets A and B: 1 hour 50 minutes"),
        (2, "1. Sam and his groupmates ____ their group project."),
    )
    assert find_handover(data, after=1) is None


# ------------------------------------------------------------------- page spans

def test_pages_of_drops_a_furniture_only_page():
    """A BLANK PAGE between the poster and the questions about it is not part of
    either. Shown to a child it reads as something failing to load."""
    data = rows(
        (6, "Peaks School Bag"),
        (7, "School bags are designed to be both roomy and trendy."),
        (8, "BLANK PAGE"),
        (8, "8"),
    )
    assert pages_of(data, 0, len(data)) == [6, 7]


def test_pages_of_keeps_order_and_deduplicates():
    data = rows((2, "1. first"), (2, "(1) an option"), (3, "continued"))
    assert pages_of(data, 0, len(data)) == [2, 3]
