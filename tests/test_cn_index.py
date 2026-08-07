"""Unit tests for the Chinese Paper 2 question inventory.

Two failures here are silent rather than loud, and both are covered below:

* A damaged question label read as a shorter number. 2025's Q17 comes back from
  OCR as "Q1Z"; matched naively that is Q1, which already exists, so nothing looks
  broken while page 7's cloze quietly attaches itself to a question on page 3.
* A mark allocation credited to the wrong question. Several are printed on their
  own line, sometimes ABOVE the question they belong to, so attaching them to
  whatever was last seen moves marks between questions without changing the total
  the validator checks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from cn_index import (  # noqa: E402
    BANK_ENTRY, GROUP, MARKS, MCQ_RANGE, QUESTION, QUESTION_LOOSE,
    QUESTION_RANGE, SECTION_COUNTS, SECTION_NAME, WRITTEN_FROM, _as_number,
    validate,
)


def line(text, left=300, top=100, height=50, width=1400):
    return Line(text, left, top, left + width, top + height, 1.0)


# ----------------------------------------------------- what the paper says of itself

def test_section_header_states_its_own_count_and_marks():
    match = SECTION_COUNTS.search("语文应用（15题30分）")
    assert (match.group(1), match.group(2)) == ("15", "30")
    assert SECTION_NAME.search("一 语文应用（15题30分）").group(1) == "语文应用"


def test_section_header_accepts_the_traditional_glyph():
    """2024 prints 題 where 2025 prints 题, in the same header."""
    assert SECTION_COUNTS.search("短文填空（5題10分）").group(1) == "5"


def test_group_header_states_a_range_and_a_total():
    match = GROUP.search("B组（Q34-Q40，7题22分）")
    assert [match.group(i) for i in range(1, 6)] == ["B", "34", "40", "7", "22"]


def test_group_header_of_the_other_year():
    match = GROUP.search("A組（Q30-Q33,4題10分）")
    assert [match.group(i) for i in range(1, 6)] == ["A", "30", "33", "4", "10"]


def test_the_two_range_statements():
    mcq = MCQ_RANGE.search(
        "从第1题到第 25题，每题都提供4 个选项，请选出答案（1，2，3或 4），"
        "然后把电脑作答卷")
    assert (mcq.group(1), mcq.group(2)) == ("1", "25")
    written = WRITTEN_FROM.search("从第26题到第40题，请把答案写在作答簿上。")
    assert (written.group(1), written.group(2)) == ("26", "40")


# ------------------------------------------------------------------ finding questions

def test_questions_are_found_inline_not_only_at_the_left_margin():
    """短文填空 is a cloze: the number sits mid-sentence, not at the margin."""
    assert QUESTION.findall("卫 Q16（1控制 2管理 3阻拦 4 克服）了这个困难") == ["16"]
    assert QUESTION.findall("小丽：你放心，Q28。我会说到做到的。") == ["28"]


def test_instruction_ranges_are_not_questions():
    """"Q1—Q2" and "（Q21-Q25）" name ranges in instruction text."""
    assert QUESTION_RANGE.search("［Q1—Q2 请选出画线词语的汉语拼音。］")
    assert QUESTION_RANGE.search("（Q21-Q25）")
    assert QUESTION_RANGE.search("A组（Q30-Q33，4题10分）")
    assert not QUESTION_RANGE.search("Q16（1控制 2管理 3阻拦 4克服）")


def test_a_damaged_label_is_not_read_as_a_shorter_number():
    """The whole point: "Q1Z" is Q17, and reading it as Q1 is worse than
    missing it, because Q1 exists and nothing looks wrong."""
    assert QUESTION.findall("有一天，大卫在游泳池边发生了 Q1Z（1危险 2意外") == []
    assert QUESTION_LOOSE.findall("发生了 Q1Z（1危险") == ["1Z"]


def test_confusable_glyphs_resolve_to_the_predicted_number():
    assert _as_number("1Z") == 17
    assert _as_number("1D") == 10
    assert _as_number("B") == 8
    assert _as_number("17") == 17


def test_confusable_map_refuses_what_it_cannot_read():
    assert _as_number("XY") is None
    assert _as_number("") is None


def test_marks_are_read_from_their_own_bracket():
    assert MARKS.findall("Q37 兄妹三人要怎么做？（3分）") == ["3"]
    # Q36 and Q39 print one allocation per sub-part on the same line.
    assert MARKS.findall("Q36 家里经常发生什么事？（1分）为什么？（2分）") == ["1", "2"]
    # The section header is not a mark allocation.
    assert MARKS.findall("语文应用（15题30分）") == []


def test_answer_bank_entries_are_counted():
    assert BANK_ENTRY.match("8 我一定会做个负责任的主人").group(1) == "8"
    assert BANK_ENTRY.match("1 把作业做完").group(1) == "1"
    assert BANK_ENTRY.match("小明：我家的猫最近生了四只小猫") is None


# ------------------------------------------------------------------------ validation

def _paper(**overrides):
    paper = {
        "mcq_range": [1, 25],
        "written_range": [26, 40],
        "sections": [{"section": "语文应用", "count": 2, "marks": 4}],
        "groups": [],
        "unresolved": [],
        "questions": [
            {"question": 1, "section": "语文应用", "marks": 2,
             "response_mode": "choose", "options": 4},
            {"question": 2, "section": "语文应用", "marks": 2,
             "response_mode": "choose", "options": 4},
        ],
    }
    paper.update(overrides)
    return paper


def test_a_paper_agreeing_with_its_own_header_passes():
    paper = _paper()
    paper["mcq_range"], paper["written_range"] = [1, 2], [1, 2]
    assert validate(paper) == []


def test_a_missing_question_is_caught_by_the_section_count():
    paper = _paper(questions=[
        {"question": 1, "section": "语文应用", "marks": 2,
         "response_mode": "choose", "options": 4}])
    assert any("found 1 questions, header states 2" in p for p in validate(paper))


def test_marks_moved_between_questions_still_fail_the_group_total():
    """The section total cannot catch a mark moved from one question to another,
    but a group with its own stated total can."""
    paper = _paper(
        groups=[{"group": "B", "start": 1, "end": 2, "count": 2, "marks": 5}])
    assert any("marks sum to 4, header states 5" in p for p in validate(paper))


def test_an_unplaced_damaged_label_is_reported_not_swallowed():
    paper = _paper(unresolved=[{"raw": "1Z", "page": 7}])
    assert any("unplaced damaged label" in p for p in validate(paper))


def test_a_paper_that_cannot_read_its_own_ranges_is_flagged():
    paper = _paper(mcq_range=None)
    assert any("could not read the paper's own question ranges" in p
               for p in validate(paper))
