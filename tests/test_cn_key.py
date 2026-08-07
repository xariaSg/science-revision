"""Unit tests for the Chinese Paper 2 answer key.

A misread option here is the worst failure the Chinese pipeline has, for the same
reason it was in Science: these questions carry no partial credit, so a wrong
digit tells a child they were wrong when they were right. The extractor is
therefore built to refuse rather than guess, and the refusals are tested
alongside the successes.

The other failure is quieter. A model answer's first line is typeset level with
its own question number but starts a few pixels higher, so ordering by `top`
alone slides every answer onto the previous question -- and the result still
looks like a well-formed rubric, just with the wrong marks on the wrong
questions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from cn_key import (  # noqa: E402
    ANCHOR, FREE_RESPONSE, MARK_SCHEME, MARKER, NOTE, number_of, option_of,
    rows, validate,
)


def option(text, expected=None):
    """The option a whole key row yields, as the parser reads it."""
    _, rest = number_of(text, expected)
    return option_of(rest)[0]


def line(text, left=300, top=100, height=50, width=1400):
    return Line(text, left, top, left + width, top + height, 1.0)


# ------------------------------------------------------------------- reading options

def test_a_plain_option_is_read():
    assert option("Q1 （2）") == 2


def test_a_circled_numeral_is_read():
    """Vision renders some of the key's plain "(4)" as "④"."""
    assert option_of("④")[0] == 4


def test_an_option_with_no_brackets_at_all_is_read():
    """2021 drops the brackets entirely: Q1 arrives as "Q1 ②"."""
    assert option("Q1 ②") == 2


def test_a_doubled_glyph_is_accepted_when_both_forms_agree():
    """2024 Q7 comes back as "（②2）"; the scan shows an ordinary (2)."""
    assert option("Q7 （②2）") == 2


def test_debris_beside_the_digit_does_not_block_the_read():
    """The rule between the columns lands beside the digit as | or ;."""
    assert option_of("④|")[0] == 4


def test_an_option_run_together_with_the_next_column_is_still_read():
    """2021-2023 merge the columns: "Q16（4） |实现" and "Q21（2） 考生可以…"."""
    assert option("Q16（4） |实现") == 4
    assert option("Q21（2） 考生可以从文章第一段第二句中找到答案。") == 2


def test_two_different_digits_are_refused_rather_than_guessed():
    assert option_of("23")[0] is None
    assert option_of("②3")[0] is None


def test_a_bracket_with_no_digit_is_refused():
    assert option_of("")[0] is None
    assert option_of("|")[0] is None


def test_a_written_answer_is_not_mistaken_for_an_option():
    """"Q34 插嘴（2）" is a model answer whose bracket holds a mark marker, not an
    option. Its text starts in Chinese, which is what rules it out."""
    assert option("Q34 插嘴（2）") is None
    assert ANCHOR.match("Q34 插嘴（2）").group(1) == "34"


# ------------------------------------------------------- reading the number

def test_a_lost_bracket_does_not_invent_a_question():
    """2023 Q19 arrives as "Q194） 所有" -- read greedily that is question 194,
    and the real Q19 disappears without leaving a gap anyone would notice."""
    assert number_of("Q194） 所有", expected={19, 20}) == (19, "4） 所有")
    assert option("Q194） 所有", expected={19, 20}) == 4


def test_a_number_the_paper_does_have_is_taken_whole():
    assert number_of("Q19 （4）", expected={19, 20})[0] == 19
    assert number_of("Q4 （1）", expected={4, 5})[0] == 4


def test_without_an_expected_set_the_digits_are_taken_as_read():
    """Paper 3 restarts its numbering and is not served, so it is read as-is."""
    assert number_of("Q10 （1）")[0] == 10


# ----------------------------------------------------------------------- mark markers

def test_markers_are_read_from_the_model_answer():
    body = "两个哥哥经常吵架（1）。因为二哥经常争做老大（1），大哥也不相让（1）。"
    assert [float(v) for v in MARKER.findall(body)] == [1.0, 1.0, 1.0]


def test_half_marks_are_read():
    body = "将在11月29日上午十点到下午三点（0.5），在东海岸海滩举行。"
    assert [float(v) for v in MARKER.findall(body)] == [0.5]


def test_a_note_is_recognised_so_its_brackets_never_count_as_marks():
    """"故选（3）" inside a 注解 references an option, not an award."""
    assert NOTE.match("（注解：见第二段第三句。）")
    assert NOTE.match("（註解：见第二段第三句。）")
    assert not NOTE.match("插嘴（2）")


def test_the_free_response_flag_is_read():
    assert FREE_RESPONSE.search("（答案合理即可）")
    assert not FREE_RESPONSE.search("（注解：这是自由发挥的一道题。）")


def test_a_split_mark_scheme_is_read():
    assert MARK_SCHEME.search("（评分标准：内容2分；语言2分）").group(1) == "内容2分；语言2分"


# ------------------------------------------------------------------------ row banding

def test_a_body_line_typeset_above_its_own_anchor_stays_with_it():
    """The cascade this guards against: 插嘴（2） sits 5px higher than the Q34 it
    belongs to, so sorting by `top` alone hands it to Q33."""
    banded = rows([line("插嘴（2）", left=330, top=315),
                   line("Q34", left=188, top=320, width=150),
                   line("熟悉（2）", left=325, top=544),
                   line("Q35", left=188, top=555, width=150)])
    assert len(banded) == 2
    assert [ln.text for ln in banded[0]] == ["Q34", "插嘴（2）"]
    assert [ln.text for ln in banded[1]] == ["Q35", "熟悉（2）"]


def test_rows_are_ordered_left_to_right_within_a_band():
    banded = rows([line("body", left=800, top=100),
                   line("Q1", left=200, top=100, width=100)])
    assert [ln.text for ln in banded[0]] == ["Q1", "body"]


def test_lines_far_apart_are_not_banded_together():
    banded = rows([line("Q1", top=100), line("Q2", top=900)])
    assert len(banded) == 2


# ------------------------------------------------------------------------- validation

def _key(entries, **extra):
    key = {"entries": entries}
    key.update(extra)
    return key


def _paper(questions):
    return {"questions": questions}


def test_a_key_covering_the_paper_passes():
    key = _key([{"booklet": "paper2", "question": 1, "option": 3,
                 "marker_total": 0}])
    paper = _paper([{"question": 1, "response_mode": "choose", "options": 4,
                     "marks": 2}])
    assert validate(key, paper) == []


def test_a_question_with_no_key_entry_is_caught():
    key = _key([])
    paper = _paper([{"question": 1, "response_mode": "choose", "options": 4,
                     "marks": 2}])
    assert any("no key entry for Q[1]" in p for p in validate(key, paper))


def test_an_option_outside_the_papers_own_range_is_caught():
    """完成对话 answers from a bank of eight; everything else has four. An option
    of 6 is right there and wrong in 语文应用."""
    key = _key([{"booklet": "paper2", "question": 1, "option": 6,
                 "marker_total": 0}])
    paper = _paper([{"question": 1, "response_mode": "choose", "options": 4,
                     "marks": 2}])
    assert any("outside 1-4" in p for p in validate(key, paper))


def test_an_unreadable_option_is_reported_with_what_was_seen():
    key = _key([{"booklet": "paper2", "question": 1, "option": None,
                 "option_raw": "②3", "marker_total": 0}])
    paper = _paper([{"question": 1, "response_mode": "choose", "options": 4,
                     "marks": 2}])
    assert any("option unreadable, key shows '②3'" in p
               for p in validate(key, paper))


def test_markers_that_do_not_sum_to_the_stated_mark_are_caught():
    """Some markers read, but not all of them -- that is a bad read, and the
    rubric it would produce awards a right answer short."""
    key = _key([{"booklet": "paper2", "question": 36, "option": None,
                 "markers": [1.0], "marker_total": 1.0,
                 "model_answer": "甲（1）。乙。丙。"}])
    paper = _paper([{"question": 36, "response_mode": "typed", "options": None,
                     "marks": 3}])
    assert any("markers sum to 1.0, paper states 3" in p
               for p in validate(key, paper))


def test_a_year_that_prints_no_markers_at_all_is_a_note_not_a_problem():
    """2021 and 2022 print none anywhere; the publisher introduced them in 2023.
    No markers is that era. Some markers, wrongly totalled, is a bad read."""
    key = _key([{"booklet": "paper2", "question": 36, "option": None,
                 "markers": [], "marker_total": 0,
                 "model_answer": "小男孩去花店的目的是买一束兰花送给李老师。"}])
    paper = _paper([{"question": 36, "response_mode": "typed", "options": None,
                     "marks": 3}])
    assert validate(key, paper) == []
    assert any("no mark markers printed" in n for n in key["notes"])


def test_a_self_marked_question_records_a_note_rather_than_a_problem():
    """Q33's marks are half holistic 语言 quality, which has no span to award
    against -- that is why it is self-marked, not a defect to block on."""
    key = _key([{"booklet": "paper2", "question": 33, "option": None,
                 "markers": [0.5, 0.5, 0.5], "marker_total": 1.5,
                 "model_answer": "甲（0.5）乙（0.5）丙（0.5）"}])
    paper = _paper([{"question": 33, "response_mode": "self_marked",
                     "options": None, "marks": 4}])
    assert validate(key, paper) == []
    assert any("markers cover 1.5 of 4 marks" in n for n in key["notes"])
