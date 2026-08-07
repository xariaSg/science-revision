"""Unit tests for the Chinese rubric builder.

The rubric is a split of the publisher's model answer at the mark markers it
prints. That makes it cheap, but it also makes it exactly as wrong as a bad split
would be: a keypoint that swallows the marker before it awards two marks for one
point, and a keypoint that keeps its trailing punctuation matches nothing.

The refusal matters more than the split. If the keypoints do not total what the
paper says the question is worth, the rubric would mark a right answer short
every time, so it is shipped un-auto-marked rather than shipped wrong.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from cn_rubric import keypoints  # noqa: E402
from cn_key import strip_pinyin  # noqa: E402


# ------------------------------------------------------------------- splitting

def test_a_three_mark_answer_splits_into_three_points():
    points = keypoints(
        "贝贝的两个哥哥经常吵架（1）。因为二哥经常争做老大（1），大哥也不相让（1）。")
    assert [p["statement"] for p in points] == [
        "贝贝的两个哥哥经常吵架", "因为二哥经常争做老大", "大哥也不相让"]
    assert [p["marks"] for p in points] == [1.0, 1.0, 1.0]


def test_leading_punctuation_is_not_kept():
    """A keypoint is cut out of a sentence, so it inherits the 。or ，that ended
    the point before it."""
    points = keypoints("甲（1）。乙（1）")
    assert [p["statement"] for p in points] == ["甲", "乙"]


def test_points_can_be_worth_different_amounts():
    """Q39's first point is worth 2 and its other two are worth 1 each, so marks
    cannot be recovered by counting keypoints."""
    points = keypoints("妈妈是个聪明的人（2）。她用了妙招（1）；她希望家人相爱（1）。")
    assert [p["marks"] for p in points] == [2.0, 1.0, 1.0]
    assert sum(p["marks"] for p in points) == 4.0


def test_half_marks_survive():
    points = keypoints("活动在11月29日举行（0.5），在东海岸海滩（0.5）。")
    assert [p["marks"] for p in points] == [0.5, 0.5]


def test_trailing_text_after_the_last_marker_is_not_a_point():
    """Q37 ends "...瓶子装满了（1），圣诞老人才会来他们家。" -- the tail carries no
    marker and awards nothing."""
    points = keypoints("兄妹三人要相亲相爱（1），圣诞老人才会来他们家。")
    assert len(points) == 1
    assert points[0]["statement"] == "兄妹三人要相亲相爱"


def test_an_answer_with_no_markers_yields_no_points():
    assert keypoints("这是一个没有标记的答案。") == []


def test_positions_are_numbered_from_one():
    points = keypoints("甲（1）。乙（1）。丙（1）")
    assert [p["position"] for p in points] == [1, 2, 3]
    assert [p["kp_id"] for p in points] == ["kp_1", "kp_2", "kp_3"]


# ---------------------------------------------------------------- pinyin strip

def test_the_unreliable_romanisation_is_dropped_from_a_gloss():
    """Not one gloss survived OCR with correct tones, and several were mangled
    into something that still reads as text. Wrong pinyin teaches a wrong
    pronunciation, so it is dropped rather than shown."""
    assert strip_pinyin("锻炼duan Idn：通过身体活动或练习。to exercise") == \
        "锻炼：通过身体活动或练习。to exercise"


def test_the_strip_does_not_need_a_space_before_the_romanisation():
    """The headword and the pinyin arrive as separate OCR lines and are joined
    without one, so a \\s lookbehind stripped only the second syllable."""
    assert strip_pinyin("克服KefG：战胜困难。to overcome") == "克服：战胜困难。to overcome"


def test_the_english_gloss_and_the_example_are_kept():
    text = strip_pinyin(
        "烦恼f6n nao：心里不开心的事情。worry; trouble【例句】我们遇到烦恼的时候。")
    assert "worry; trouble" in text
    assert "【例句】我们遇到烦恼的时候。" in text
    assert "f6n" not in text


def test_only_the_first_romanisation_is_removed():
    """One gloss, one headword. Stripping every ASCII run before a colon would
    eat into the definition."""
    assert strip_pinyin("勤奋qin fen：努力。hardworking") == "勤奋：努力。hardworking"


def test_text_with_no_romanisation_is_untouched():
    answer = "贝贝的两个哥哥经常吵架（1）。因为二哥经常争做老大（1）。"
    assert strip_pinyin(answer) == answer
