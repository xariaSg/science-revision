"""Unit tests for the English Booklet B inventory.

Two of the five sections state no question range, so their ranges are derived.
That derivation is the thing worth testing: it is arithmetic over the marks the
paper prints, it must refuse when the arithmetic does not come out, and a wrong
answer here would file every cloze answer under the wrong question number while
looking like a perfectly well-formed index.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from en_index_b import (  # noqa: E402
    ANSWERABLE, BOOKLET_TOTAL_RE, MARKS_RE, RANGE_RE, RESPONSE_MODES,
    fill_ranges,
)


def section(marks, first=None, last=None, mode="word"):
    return {"marks": marks, "first": first, "last": last,
            "response_mode": mode, "row": 0, "page": 1, "block_row": 0,
            "instruction": ""}


def mode_of(text):
    return next((mode for mode, pattern in RESPONSE_MODES if pattern.search(text)),
                "not_built")


# ---------------------------------------------------- what the paper says it is

def test_marks_statement_is_read():
    assert MARKS_RE.search("Fill in each blank with a suitable word. (15 marks)"
                           ).group("marks") == "15"


def test_per_question_allocation_is_not_a_section_total():
    """The comprehension writes "[2m]" and "(1m)" — neither opens a section."""
    assert MARKS_RE.search("state two ways [2m]") is None
    assert MARKS_RE.search("Tick the correct answer. (1m)") is None


def test_range_is_read_from_all_four_wordings():
    for text, expected in [
        ("There are 10 blanks, numbered 26 to 35, in the passage below.", ("26", "35")),
        ("For each of the questions 61 to 65, rewrite the given sentence(s)", ("61", "65")),
        ("answer questions 66 to 75.", ("66", "75")),
        ("questions 21-25", ("21", "25")),
    ]:
        match = RANGE_RE.search(text)
        assert match and (match.group("first"), match.group("last")) == expected, text


def test_booklet_total_on_the_cover():
    assert BOOKLET_TOTAL_RE.search("returned. Booklet B / 65").group("total") == "65"


# --------------------------------------------------------------- response modes

def test_letter_bank_beats_word():
    """The grammar cloze instruction says "word" too, so order matters: read as a
    word question its answers would be compared against "had" and never "F"."""
    assert mode_of("choose the most suitable word for each blank. "
                   "Write its letter (A to Q) in the blank.") == "letter"


def test_editing_and_cloze_are_word_questions():
    assert mode_of("Each of the underlined words contains either a spelling or "
                   "grammatical error. Write the correct word in each of the "
                   "boxes.") == "word"
    assert mode_of("Fill in each blank with a suitable word.") == "word"


def test_synthesis_is_a_sentence():
    assert mode_of("rewrite the given sentence(s) using the word(s) provided. "
                   "Your answer must be in one sentence.") == "sentence"


def test_comprehension_falls_through_to_not_built():
    """Nothing matches, and that is the wanted answer: an app that offers the
    wrong kind of answer box is worse than one that offers none."""
    mode = mode_of("Read the passage on page 10 of Booklet A and answer "
                   "questions 66 to 75.")
    assert mode == "not_built"
    assert mode not in ANSWERABLE


# ------------------------------------------------------------ derived ranges

def test_a_run_of_unstated_ranges_is_split_by_its_marks():
    sections = [section(10, 26, 35), section(10), section(15), section(10, 61, 65)]
    assert fill_ranges(sections) == []
    assert [(s["first"], s["last"]) for s in sections] == [
        (26, 35), (36, 45), (46, 60), (61, 65)]
    assert sections[1]["range_source"] == "derived from the stated marks"


def test_a_run_that_does_not_add_up_is_refused():
    """25 questions between the stated ranges, but the sections claim 21 marks.
    One of the two readings is wrong and nothing here says which, so no range is
    filled in at all."""
    sections = [section(10, 26, 35), section(6), section(15), section(10, 61, 65)]
    problems = fill_ranges(sections)
    assert problems and "left unset rather than guessed" in problems[0]
    assert sections[1]["first"] is None and sections[2]["first"] is None


def test_a_run_with_nothing_stated_after_it_is_refused():
    sections = [section(10, 26, 35), section(15)]
    problems = fill_ranges(sections)
    assert problems and "nothing after them" in problems[0]
    assert sections[1]["first"] is None


def test_a_run_with_nothing_stated_before_it_is_refused():
    sections = [section(10), section(10, 36, 45)]
    problems = fill_ranges(sections)
    assert problems and "nothing before them" in problems[0]
    assert sections[0]["first"] is None


def test_stated_ranges_are_left_alone():
    sections = [section(10, 26, 35), section(10, 36, 45)]
    assert fill_ranges(sections) == []
    assert all("range_source" not in s for s in sections)
