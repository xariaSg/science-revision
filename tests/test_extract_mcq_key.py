"""Unit tests for the Booklet A answer key.

Every case here is a real reading from the 14 papers. The stakes are different from
Booklet B's: an MCQ answer is one digit with no partial credit, so a misread does
not soften a mark, it tells a child they were wrong when they were right. The tests
are correspondingly weighted towards the extractor *refusing* rather than guessing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from extract_mcq_key import (  # noqa: E402
    BARE_OPTION_RE, BOOKLET_RE, CONFUSABLE, FURNITURE_RE, LEADING_NOISE_RE,
    LOOSE_MARKER_RE, MARKER_RE, Candidate, Entry, _gap_bands, _section_index,
    choose_run, is_number,
)


def line(text, left=200, top=100, height=50, width=400):
    return Line(text, left, top, left + width, top + height, 1.0)


def candidate(index, question, option=1, page=1, column=0):
    return Candidate(index, question, option, page, column, line(""))


# --------------------------------------------------------------- the marker

def test_marker_reads_a_plain_answer():
    match = MARKER_RE.match("1. (3)")
    assert (match.group("question"), match.group("option")) == ("1", "3")


def test_marker_tolerates_the_spacing_of_the_older_papers():
    """2012 prints its options loosely: "3. (3 )" and "5. ( 1)"."""
    assert MARKER_RE.match("3. (3 )").group("option") == "3"
    assert MARKER_RE.match("5. ( 1)").group("option") == "1"
    assert MARKER_RE.match("12.(4)").group("option") == "4"


def test_marker_rejects_an_option_outside_one_to_four():
    """Booklet A has four options. A "(5)" is a misread, not an answer."""
    assert MARKER_RE.match("7. (5)") is None
    assert MARKER_RE.match("7. (0)") is None


def test_marker_does_not_match_explanation_prose():
    """2018 Q2's explanation ends "...option (1) and option (4) cannot be
    concluded", which must not read as an answer to question 1."""
    assert MARKER_RE.match("and option (1) cannot be concluded") is None


def test_bare_option_is_recognised_without_a_number():
    """2012's first answer opens "( 2) To drink the nectar...", its "1." dropped."""
    assert BARE_OPTION_RE.match("( 2) To drink the nectar").group("option") == "2"


# ------------------------------------------------------------ choosing the run

def test_choose_run_keeps_a_clean_sequence():
    chosen = choose_run([candidate(i, n) for i, n in enumerate([1, 2, 3, 4])])
    assert chosen == {0, 1, 2, 3}


def test_choose_run_survives_a_dropped_marker():
    """The whole reason this is not a +1 rule. 2020 loses Q3's marker; requiring
    each number to follow the last threw away all 25 answers after it."""
    chosen = choose_run([candidate(i, n) for i, n in enumerate([1, 2, 4, 5, 6])])
    assert chosen == {0, 1, 2, 3, 4}


def test_choose_run_discards_a_number_that_breaks_the_count():
    """Prose that happens to open with a bracketed digit does not count upwards."""
    numbers = [1, 2, 3, 99, 4, 5, 6]
    chosen = choose_run([candidate(i, n) for i, n in enumerate(numbers)])
    assert 3 not in chosen                      # the "99"
    assert chosen == {0, 1, 2, 4, 5, 6}


def test_choose_run_ignores_bare_options_when_numbers_exist():
    """A bare option is only ever promoted at the head of the run, by the caller."""
    entries = [candidate(0, None), candidate(1, 1), candidate(2, 2)]
    assert choose_run(entries) == {1, 2}


def test_choose_run_on_nothing():
    assert choose_run([]) == set()


# ------------------------------------------------------- confusable digits

def test_is_number_accepts_a_confused_glyph():
    """2020's smudged "10." comes back from Vision as "1D."."""
    assert is_number("1D", 10)
    assert is_number("2l", 21)


def test_is_number_refuses_a_different_number():
    """The safeguard: it answers yes/no about a number the sequence already fixed,
    so a genuinely different reading must not pass."""
    assert not is_number("49", 19)
    assert not is_number("11", 10)


def test_is_number_refuses_something_that_is_not_a_number():
    assert not is_number("as", 5)
    assert not is_number("", 1)


def test_confusable_map_only_moves_letters_to_digits():
    assert all(value.isdigit() for value in CONFUSABLE.values())


def test_loose_marker_is_searchable_mid_string():
    """A single-row crop picks up debris from the dotted rule beside it: 2018 Q21
    comes back from --psm 7 as "oe 2 21. (1)"."""
    found = [m for m in LOOSE_MARKER_RE.finditer("oe 2 21. (1)")
             if is_number(m.group("question"), 21)]
    assert len(found) == 1
    assert found[0].group("option") == "1"


# ---------------------------------------------------------------- the section

def test_booklet_header_with_its_year_attached():
    """2012-2014 print "2012 Booklet A" on one line; later papers split them."""
    match = BOOKLET_RE.match("2012 Booklet A")
    assert (match.group("year"), match.group("label")) == ("2012", "A")
    assert BOOKLET_RE.match("Booklet A").group("year") is None
    assert BOOKLET_RE.match("Booklet B").group("label") == "B"


def test_furniture_is_skipped():
    assert FURNITURE_RE.search("PSLE Yearly Science - Answers")
    assert FURNITURE_RE.search("© Educational Publishing House Pte Ltd")
    assert FURNITURE_RE.search("26")
    assert not FURNITURE_RE.search("1. (3)")


def test_leading_noise_keeps_a_bracket():
    """The bracket is the option; stripping it would lose the answer."""
    assert LEADING_NOISE_RE.sub("", "• (2) something") == "(2) something"


# ------------------------------------------------------------- the gap bands

MANIFEST = {"pages": [{"width": 2400, "height": 3400}] * 6}


def entry(number, page=1, column=0, top=100, marker_bottom=150, left=300):
    return Entry(number, 1, page=page, column=column, top=top,
                 marker_bottom=marker_bottom, bottom=3000, left=left)


def test_gap_band_within_one_column_starts_below_the_previous_marker():
    """Not below the previous *answer*: when a marker is dropped its explanation is
    absorbed by the question before, so that entry's text runs past the line being
    looked for."""
    bands = _gap_bands(MANIFEST, entry(2, marker_bottom=150), entry(4, top=2000))
    assert len(bands) == 1
    page, (_, top, _, bottom) = bands[0]
    assert (page, top, bottom) == (1, 150, 2000)


def test_gap_band_across_a_column_offers_both_ends():
    before = entry(16, page=3, column=1, marker_bottom=1458)
    after = entry(18, page=4, column=0, top=523)
    bands = _gap_bands(MANIFEST, before, after)
    assert [page for page, _ in bands] == [3, 4]
    assert bands[0][1][3] == 3400              # to the foot of the column
    assert bands[1][1][1] == 0                 # from the head of the next


def test_gap_band_widens_to_keep_a_shifted_marker_whole():
    """The 2016 scan sits far enough left that the right column's markers begin
    before the page midpoint; a strip cut at the midpoint sliced the "1" off its
    "17. (3)"."""
    before = entry(16, page=3, column=1, left=1150)
    bands = _gap_bands(MANIFEST, before, entry(18, page=4, column=0))
    assert bands[0][1][0] <= 1150


def test_gap_band_for_a_trailing_question_has_no_successor():
    """2021 loses Q28, the last answer on the page, so there is nothing after it to
    bound the search — only the booklet's own question count says it is missing."""
    bands = _gap_bands(MANIFEST, entry(27, page=3, column=1), None)
    assert len(bands) == 1
    assert bands[0][1][3] == 3400


def test_gap_band_for_a_trailing_question_also_tries_the_next_column():
    bands = _gap_bands(MANIFEST, entry(27, page=3, column=0), None)
    assert [b[1][0] for b in bands] == [0, 1200]


# -------------------------------------------------- placing a recovered marker

def section(rows):
    """(page, left, top) triples as section lines."""
    return [(page, line("text", left=left, top=top, height=40))
            for page, left, top in rows]


def test_recovered_marker_is_placed_at_its_first_explanation_line():
    """A re-read marker was never in the reading order, so it is keyed to the first
    row below it -- which is already its explanation, and is where the question
    above it must stop."""
    lines = section([(1, 300, 1500), (1, 300, 1861), (1, 300, 1906)])
    recovered = Entry(3, 1, source="reread", page=1, column=0, top=1762,
                      marker_bottom=1801)
    assert _section_index(lines, MANIFEST, recovered) == 1


def test_recovered_marker_ignores_rows_above_it():
    lines = section([(1, 300, 100), (1, 300, 1900)])
    recovered = Entry(3, 1, source="reread", page=1, column=0, marker_bottom=1801)
    assert _section_index(lines, MANIFEST, recovered) == 1


def test_recovered_marker_stays_in_its_own_column():
    """The row at the same height in the other column belongs to another answer."""
    lines = section([(1, 1500, 1900), (1, 300, 1950)])
    recovered = Entry(3, 1, source="reread", page=1, column=0, marker_bottom=1801)
    assert _section_index(lines, MANIFEST, recovered) == 1


def test_recovered_marker_at_the_foot_of_a_page_has_nowhere_to_start():
    """Nothing below it means no explanation to claim — reported, not invented."""
    lines = section([(1, 300, 100)])
    recovered = Entry(3, 1, source="reread", page=1, column=0, marker_bottom=3000)
    assert _section_index(lines, MANIFEST, recovered) is None
