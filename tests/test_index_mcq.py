"""Unit tests for the Booklet A question inventory.

The failure that matters here is silent: if a question is placed on the wrong page,
the student reads one question and is marked against another's key, and nothing in
the app looks broken. So the tests cover both the recovery tiers and the refusals.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from index_mcq import (  # noqa: E402
    FURNITURE_RE, NUMBER_RE, OPTION_RE, QUESTION_RE, RANGE_RE, TOTAL_MARKS_RE,
    _after_option_block, _row_at, longest_increasing_run,
)


def line(text, left=300, top=100, height=50, width=1400):
    return Line(text, left, top, left + width, top + height, 1.0)


# ------------------------------------------------------------- what the paper says

def test_range_statement_is_read():
    """The anchor for everything else: it fixes the numbering and separates the
    questions from the cover's own numbered instructions."""
    match = RANGE_RE.search(
        "For each question from 1 to 28, four options are given.")
    assert (match.group("first"), match.group("last")) == ("1", "28")


def test_range_statement_of_the_older_papers():
    assert RANGE_RE.search(
        "For each question from 1 to 30, four options are given.").group("last") == "30"


def test_total_marks_is_read():
    assert TOTAL_MARKS_RE.search("(56 marks)").group("marks") == "56"
    assert TOTAL_MARKS_RE.search("(60 marks)").group("marks") == "60"


# ------------------------------------------------------------------- the markers

def test_question_number_leads_its_own_text():
    """Vision returns the number joined to the question it opens."""
    match = QUESTION_RE.match("12 Devi carried out an experiment using 2 boxes")
    assert match.group("question") == "12"
    assert match.group("rest").startswith("Devi")


def test_question_number_alone_on_a_line():
    assert QUESTION_RE.match("7").group("question") == "7"
    assert QUESTION_RE.match("7.").group("question") == "7"


def test_question_pattern_rejects_an_option_label():
    """Options are indented past the marker zone, but the pattern must not depend
    on that alone."""
    assert QUESTION_RE.match("(1) They can reproduce.") is None


def test_number_token_is_how_tesseract_returns_a_marker():
    assert NUMBER_RE.match("10").group("question") == "10"
    assert NUMBER_RE.match("10.").group("question") == "10"
    assert NUMBER_RE.match("10 Devi carried out") is None


def test_options_are_counted_off_a_row():
    """2012 prints picture options two to a row: "(1) (2)"."""
    assert OPTION_RE.findall("(1) (2)") == ["1", "2"]
    assert OPTION_RE.findall("(4) type of body covering") == ["4"]


def test_furniture_is_recognised():
    assert FURNITURE_RE.search("0009/02(A)/2018")
    assert FURNITURE_RE.search("(Go on to the next page)")
    assert FURNITURE_RE.search("4")
    assert FURNITURE_RE.search("BLANK PAGE")
    assert not FURNITURE_RE.search("5 Fertilisers help tiny floating plants")


# ---------------------------------------------------------------- run selection

def test_longest_run_keeps_a_clean_sequence():
    assert longest_increasing_run([1, 2, 3, 4]) == {0, 1, 2, 3}


def test_longest_run_tolerates_a_dropped_number():
    assert longest_increasing_run([1, 2, 4, 5]) == {0, 1, 2, 3}


def test_longest_run_drops_a_number_that_does_not_count_upwards():
    """"20 cm", a page number, an axis label — all left-margin digits that are not
    questions."""
    chosen = longest_increasing_run([1, 2, 56, 3, 4, 5])
    assert 2 not in chosen
    assert chosen == {0, 1, 3, 4, 5}


def test_longest_run_on_nothing():
    assert longest_increasing_run([]) == set()


# ------------------------------------------------------------------ row matching

def test_row_at_finds_the_nearest_row_on_the_page():
    rows = [(1, line("a", top=100)), (1, line("b", top=500)), (2, line("c", top=100))]
    assert _row_at(rows, 1, 110, 50) == 0
    assert _row_at(rows, 2, 110, 50) == 2


def test_row_at_refuses_a_row_too_far_away():
    rows = [(1, line("a", top=100))]
    assert _row_at(rows, 1, 900, 50) is None


def test_row_at_will_not_cross_pages():
    """A number on page 4 must never be matched to a row on page 3."""
    rows = [(3, line("a", top=100))]
    assert _row_at(rows, 4, 100, 50) is None


# --------------------------------------------------------- the option-block tier

def rows_from(spec):
    """(page, text) pairs as rows, one per 100px down their page."""
    out, top, page = [], 0, None
    for row_page, text in spec:
        top = 0 if row_page != page else top + 100
        page = row_page
        out.append((row_page, line(text, top=top)))
    return out


def test_question_after_a_complete_option_block():
    """2017 and 2024 both lose a "4" so completely that the question's first row
    starts at the body indent with nothing to its left. The layout still says where
    it begins: the row after the previous question's fourth option."""
    rows = rows_from([
        (3, "3 Which one of the following organisms is not a fungus?"),
        (3, "(1) fern"), (3, "(2) yeast"), (3, "(3) mould"), (3, "(4) mushroom"),
        (3, "Which of the following correctly describes the transfer of energy?"),
        (3, "(1) Energy is transferred from predators to prey"),
        (3, "5 Halim found an animal in a stream"),
    ])
    assert _after_option_block(rows, 0, 7) == 5


def test_option_block_takes_the_first_complete_run_not_the_last():
    """The missing question has options of its own further down the band; on 2024
    they are labels on a diagram, so a later "(4)" is not the boundary."""
    rows = rows_from([
        (3, "3 Fatimah wants to find out whether the organism is an insect"),
        (3, "(1) Measure its length."), (3, "(2) Count its legs."),
        (3, "(3) Examine its wings."), (3, "(4) Observe what it feeds on."),
        (3, "Which part controls the movement of substances in and out of the cell?"),
        (3, "- (1)"), (3, "- (2)"), (3, "- (3)"), (3, "- (4)"),
        (3, "5 Water droplets are observed on the surface of leaves"),
    ])
    assert _after_option_block(rows, 0, 10) == 5


def test_option_block_steps_over_the_page_furniture():
    """A question ending at the foot of a page has the footer and the next page's
    number between its last option and the question following it."""
    rows = rows_from([
        (3, "4 The diagram below shows a food web"),
        (3, "(1) X is a decomposer."), (3, "(2) W eats plants."),
        (3, "(3) When V decreases, S will increase."), (3, "(4) Energy from the Sun"),
        (3, "0009/02(A)/2018 (Go on to the next page)"),
        (4, "4"),
        (4, "Fertilisers help tiny floating plants to grow quickly"),
        (4, "6 The chart below shows how substances P and Q are transported"),
    ])
    # Overleaf, so the question owns the page from the top rather than from the
    # first row that happened to be readable.
    assert _after_option_block(rows, 0, 8) == 6


def test_option_block_refuses_when_the_options_are_pictures():
    """No complete run of four means no boundary, and a gap left for a human beats
    a question placed on the wrong page."""
    rows = rows_from([
        (2, "1 Some birds feed on the nectar of this flower."),
        (2, "Which bird is best suited for pollinating this flower?"),
        (2, "3 The diagram shows a plant cell."),
    ])
    assert _after_option_block(rows, 0, 2) is None


def test_option_block_refuses_when_the_boundary_is_the_next_question():
    """A complete run whose following row is already the next placed question
    leaves nowhere for the missing one to go."""
    rows = rows_from([
        (2, "1 Which is a characteristic of all living things?"),
        (2, "(1) a"), (2, "(2) b"), (2, "(3) c"), (2, "(4) d"),
        (2, "3 What is one effect of deforestation?"),
    ])
    assert _after_option_block(rows, 0, 5) is None
