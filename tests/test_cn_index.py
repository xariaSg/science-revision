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
    BANK_ENTRY, GROUP, MARKS, MCQ_RANGE, OPTION, QUESTION, QUESTION_DAMAGED,
    QUESTION_LOOSE, QUESTION_RANGE, SECTION_COUNTS, SECTION_NAME,
    SECTION_STEMS, WRITTEN_FROM, Question, _as_number, _count_options,
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


def test_group_header_may_state_only_a_range():
    """2012-2016 print the group headers bare, leaving the totals to the parent
    section. Requiring the counts recorded no group at all on those years, and
    every written question in 阅读理解二 then fell through to the modern era's
    rules and came back as `choose` -- four option buttons under a question that
    prints ruled answer lines."""
    match = GROUP.search("A组（Q29-Q34）")
    assert [match.group(i) for i in range(1, 6)] == ["A", "29", "34", None, None]
    match = GROUP.search("B组（Q35-Q41）")
    assert [match.group(i) for i in range(1, 6)] == ["B", "35", "41", None, None]


def test_section_name_survives_a_misread_first_character():
    """2017 p16 reads "五 阔读理解二（Q30-Q33，4题10分）" -- 阅 as 阔. That one
    glyph kept the section from opening and 完成对话 absorbed Q30-Q40."""
    assert SECTION_NAME.search("五 阔读理解二（Q30-Q33，4题10分）").group(1) == "读理解二"
    assert SECTION_STEMS["读理解二"] == "阅读理解二"


def test_section_name_survives_a_dropped_numeral():
    """A 2026 school prelim prints "三 阅读理解（5题10分）" with no "一" at all,
    rather than misreading it -- the word is simply absent from the scan. A
    bare "读理解" must resolve to 阅读理解一 without ever winning over an
    explicit "二" elsewhere on the same corpus."""
    match = SECTION_NAME.search("三 阅读理解（5题10分）")
    assert SECTION_STEMS[match.group(1)] == "阅读理解一"


def test_section_name_survives_a_parenthesised_numeral():
    """Another school prints "三阅读理解（一）（5題10分）" -- the numeral present,
    but set off in its own brackets rather than run on."""
    match = SECTION_NAME.search("三阅读理解（一）（5題10分）")
    assert SECTION_STEMS[match.group(1)] == "阅读理解一"
    # The two comprehension sections stay distinct from each other.
    assert SECTION_NAME.search("三 阅读理解一（5题10分）").group(1) == "读理解一"


def test_a_section_header_that_names_a_range_is_describing_that_range():
    """2017 restates A組's range and totals on the parent header, so those counts
    describe four of the section's eleven questions rather than the section."""
    text = "五 阅读理解二（Q30-Q33，4题10分）"
    assert QUESTION_RANGE.search(text) is not None
    # ...and the counts are not in the section-header form anyway, because the
    # bracket opens with the range rather than with a digit.
    assert SECTION_COUNTS.search(text) is None


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


def test_a_dropped_q_before_an_option_bracket_is_caught():
    """A 2026 school prelim's "Q18" and "Q19" both come back with the "Q"
    itself replaced by a digit, not one of its own digits misread -- "918
    （1已经", "919（1询问". Scoped to immediately before an option opener so a
    date or a price in the surrounding passage cannot match."""
    assert QUESTION_DAMAGED.findall("帮助别人 918（1已经（2必须 3可能 4需要）") == ["18"]
    assert QUESTION_DAMAGED.findall("017（1力量2精神3意义4耐心）") == ["17"]


def test_a_dropped_q_without_a_following_option_is_not_matched():
    """The same corruption in a dialogue-completion blank has no option
    bracket after it ("，926？1"), so it is not this tier's job to catch --
    an unscoped match would also fire on a date or a price ("640元")."""
    assert QUESTION_DAMAGED.findall("欢欢：好，你说出来吧，926？") == []
    assert QUESTION_DAMAGED.findall("每周六上午640元") == []
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


def _bank_entry(text):
    """The bank entry's number, whichever of the three printed forms it took."""
    match = BANK_ENTRY.match(text)
    return next((g for g in match.groups() if g is not None), None) if match else None


def test_answer_bank_entries_are_counted():
    # Bare, on 2017-2025.
    assert _bank_entry("8 我一定会做个负责任的主人") == "8"
    assert _bank_entry("1 把作业做完") == "1"
    # Parenthesised, on 2012.
    assert _bank_entry("（1）你放心好了") == "1"
    assert _bank_entry("（8） 有人假扮政府人员进屋里偷东西") == "8"
    # Dotted, on 2013-2016 -- and 2016 prints some without even a space.
    assert _bank_entry("1. 太没有爱心了") == "1"
    assert _bank_entry("7.巴士在繁忙时间挤满了搭客") == "7"
    # Dialogue lines are not entries.
    assert _bank_entry("小明：我家的猫最近生了四只小猫") is None
    # Nor is the page number sitting alone at the top of the page: a separator of
    # some kind is always required, and there is nothing for it to separate.
    assert _bank_entry("3") is None


# -------------------------------------------------------------- chosen or written?

def _counted(rows_by_page, questions):
    """Run the option count over hand-built pages. rows_by_page: {page: [(top, text)]}."""
    index = {q.number: q for q in questions}
    lines = {page: [line(text, top=top) for top, text in rows]
             for page, rows in rows_by_page.items()}
    return _count_options(index, lines)


def test_a_block_question_is_recognised_by_its_four_options():
    """阅读理解二 A組 Q30-Q32 on 2017-2025: chosen, four options beneath."""
    counts = _counted(
        {12: [(100, "Q30 学校为什么举办比赛？（2分）"),
              (200, "（1）为了庆祝中秋节"),
              (300, "（2）为了推广华文"),
              (400, "（3）为了教学生做灯笼"),
              (500, "（4）为了筹款")]},
        [Question(number=30, page=12, tops=[100])])
    assert counts[30] == 4


def test_a_written_question_has_no_options_at_all():
    """2012-2016 print the whole of 阅读理解二 as ruled lines and a 得分 box.
    Read off the page the split is absolute -- four markers or none."""
    counts = _counted(
        {19: [(100, "Q37 为什么作者认为上学的路是那么的远？（3分）"),
              (300, "得分")]},
        [Question(number=37, page=19, tops=[100])])
    assert counts[37] == 0


def test_options_stop_at_the_next_question():
    """A question's band ends where the next one's anchor begins, so Q30 cannot
    collect the options printed under Q31."""
    counts = _counted(
        {12: [(100, "Q30 学校为什么举办比赛？"),
              (200, "（1）甲"), (300, "（2）乙"),
              (400, "Q31 参赛者要注意什么？"),
              (500, "（3）丙"), (600, "（4）丁")]},
        [Question(number=30, page=12, tops=[100]),
         Question(number=31, page=12, tops=[400])])
    assert counts[30] == 2
    assert counts[31] == 2


def test_option_marker_ignores_a_mark_allocation():
    """"（3分）" is an allocation, not an option -- the marker is a bare digit."""
    assert OPTION.findall("Q37 为什么？（3分）") == []
    assert OPTION.findall("（1）为了庆祝中秋节") == ["1"]


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


def test_a_group_range_that_disagrees_with_its_own_count_is_not_walked():
    """A 2026 school prelim misread "A组（Q30-Q33，4题10分）" as "A组（Q3-933,
    4題10分）" -- count intact, range destroyed. Walking range(3, 934) for
    missing questions invents hundreds of them; the count disagreeing with the
    range is what says the range cannot be trusted, so it is reported and
    skipped instead."""
    paper = _paper(
        groups=[{"group": "A", "start": 3, "end": 933, "count": 4, "marks": 10}])
    problems = validate(paper)
    assert any("does not match its own stated count" in p for p in problems)
    assert not any("missing Q" in p for p in problems)


def test_a_paper_that_cannot_read_its_own_ranges_is_flagged():
    paper = _paper(mcq_range=None)
    assert any("could not read the paper's own question ranges" in p
               for p in validate(paper))
