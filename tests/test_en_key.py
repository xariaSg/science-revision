"""Unit tests for the two English answer-key readers.

CLAUDE.md 1.6.1 says why this file matters more than its size suggests: a wrong
digit or a wrong word here has no partial credit to soften it, and the child is
simply told they were wrong when they were right. So the tests are mostly about
*refusing* — a cell whose readings disagree, a column bound that would file one
table's answer under another's question.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

import en_key  # noqa: E402
import en_key_b  # noqa: E402
from ocr_vision import Line  # noqa: E402


def line(text, left, top, width=200, height=40):
    return Line(text, left, top, left + width, top + height, 1.0)


# ------------------------------------------------ Booklet A: one digit per cell

def test_two_agreeing_readings_are_accepted():
    assert en_key.agree([2, 2, 2]) == 2


def test_a_single_reading_is_refused():
    """A grid of isolated digits is effectively a reconstruction from end to end,
    so one reader is not enough (CLAUDE.md 1.6.1)."""
    assert en_key.agree([3]) is None


def test_disagreeing_readings_are_refused():
    assert en_key.agree([2, 3, 2]) is None


def test_nothing_read_is_refused():
    assert en_key.agree([]) is None


def test_only_options_1_to_4_count_as_a_digit():
    """tesseract reads Q21's "2" as "9" on this paper. It is not an option, so it
    cannot outvote or contradict anything."""
    assert en_key._digits(["2", "9", "2."]) == [2, 2]


def test_a_question_number_cell_keeps_its_stop():
    assert en_key._numbers(["16.", "16", "1O."]) == [16, 16]


def test_booklet_heading_matches_only_at_the_start_of_a_line():
    assert en_key.BOOKLET_RE.match("BOOKLET A")
    assert en_key.BOOKLET_RE.match("BOOKLET B").group("booklet") == "B"
    assert en_key.BOOKLET_RE.match("Total Time for Booklets A and B") is None


def _grid(columns, rows_, top=100, left=100, cell=(120, 60)):
    """A synthetic ruled table: `columns` cell columns by `rows_` data rows."""
    width, height = cell
    page = np.zeros((top + (rows_ + 1) * height + 40,
                     left + (columns + 1) * width + 40), dtype=bool)
    for r in range(rows_ + 2):                       # header rule + row rules
        y = top + r * height
        page[y:y + 2, left:left + columns * width + 1] = True
    for c in range(columns + 1):                     # column rules, data rows only
        x = left + c * width
        page[top + height:top + (rows_ + 1) * height + 2, x:x + 2] = True
    return page


def test_a_ruled_table_is_found_with_its_columns_and_rows():
    tables = en_key.find_tables(_grid(2, 5), 0, 700)
    assert len(tables) == 1
    assert len(tables[0].columns) == 2
    assert len(tables[0].rows) == 5


def test_two_tables_side_by_side_are_told_apart_by_the_rule_between_them():
    """The gap between these tables is *narrower* than the cells inside them, so
    nothing about the spacing separates them — only the missing row rule does."""
    left = _grid(2, 5, left=100)
    right = _grid(2, 5, left=100 + 3 * 120 + 40)
    page = np.zeros((max(left.shape[0], right.shape[0]),
                     max(left.shape[1], right.shape[1])), dtype=bool)
    page[:left.shape[0], :left.shape[1]] |= left
    page[:right.shape[0], :right.shape[1]] |= right
    tables = en_key.find_tables(page, 0, page.shape[0])
    assert len(tables) == 2
    assert all(len(table.columns) == 2 for table in tables)


# --------------------------------------------- Booklet B: a word or a sentence

def test_columns_are_ordered_left_to_right():
    """Ordered by where a column sits, not by the number that opened it: each
    column's right edge is the next column's left, so a nearly-sorted order gives
    a column a bound to the left of its own text and it comes back empty."""
    numbered = [(46, line("46.", 1320, 100)), (26, line("26.", 270, 100)),
                (47, line("47.", 1320, 180)), (27, line("27.", 270, 180)),
                (36, line("36.", 770, 100)), (37, line("37.", 770, 180)),
                (28, line("28.", 270, 260)), (38, line("38.", 770, 260)),
                (48, line("48.", 1320, 260))]
    columns = en_key_b.columns_of(numbered)
    assert [min(e[1].left for e in c) for c in columns] == [270, 770, 1320]


def test_a_column_needs_more_than_a_stray_number():
    numbered = [(26, line("26.", 270, 100)), (27, line("27.", 270, 180)),
                (28, line("28.", 270, 260)), (99, line("99.", 2000, 900))]
    assert len(en_key_b.columns_of(numbered)) == 1


def test_a_letter_bank_answer_accepts_the_letter_and_the_word():
    entry = en_key_b.parse_answer("letter", ["F (had)"])
    assert entry["letters"] == ["F"]
    assert entry["accept"] == ["F", "had"]


def test_two_acceptable_letters_are_both_kept():
    """Q26 prints "F (had)" and "G (have)": either fits the blank."""
    entry = en_key_b.parse_answer("letter", ["F (had)", "G (have)"])
    assert entry["accept"] == ["F", "G", "had", "have"]


def test_a_word_answer_is_itself():
    assert en_key_b.parse_answer("word", ["commemorate"])["accept"] == ["commemorate"]


def test_a_sentence_answer_is_joined_not_split():
    entry = en_key_b.parse_answer(
        "sentence", ["No sooner had the rain stopped than the players",
                     "continued with the match."])
    assert entry["text"] == ("No sooner had the rain stopped than the players "
                             "continued with the match.")
    assert "accept" not in entry
