"""Unit tests for answer extraction.

Every case here is a bug that actually occurred while backfilling 2012-2023. The
first two papers built (2024, 2025) exercised none of them, which is why the
extractor looked finished and was not.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from ocr_vision import Line  # noqa: E402
from extract_answers import (  # noqa: E402
    LABEL_DEBRIS_RE, LEADING_NOISE_RE, MARKER_RE, ROMAN_FALLBACK_RE, YEAR_RE,
    Answer, Chunk, drop_artefacts, merge_rows, recover_label, satisfied_by,
    split_columns,
)


def line(text, left, top, height=50, width=700, confidence=1.0):
    return Line(text, left, top, left + width, top + height, confidence)


def test_year_line_is_recognised():
    """The answer archives are multi-year compilations: 2023's own answers run out
    partway down page 6, whose right column opens "2022"."""
    assert YEAR_RE.match("2022").group("year") == "2022"
    assert YEAR_RE.match(" 2015 ").group("year") == "2015"


def test_year_line_does_not_match_text_containing_a_year():
    assert YEAR_RE.match("In 2022 the reading was 30") is None


def test_leading_noise_is_stripped_from_a_question_number():
    """2023 Q38 OCRs as "÷38. (a) When switch S was closed..." — left in place the
    number never matches and the whole question is absorbed by Q37."""
    text = LEADING_NOISE_RE.sub("", "÷38. (a) When switch S was closed")
    marker = MARKER_RE.match(text)
    assert marker.group("question") == "38"
    assert marker.group("part") == "a"


def test_leading_noise_keeps_an_opening_bracket():
    """"(b) ..." must survive: the bracket is the label, not noise."""
    assert LEADING_NOISE_RE.sub("", "(b) Bulbs P and Q") == "(b) Bulbs P and Q"


def test_roman_fallback_reads_a_damaged_closing_bracket():
    """2022 Q31(a)(ii) comes back as "i* The number of bacteria"."""
    match = ROMAN_FALLBACK_RE.match("i* The number of bacteria")
    assert match.group("roman") == "i"
    assert match.group("body") == "The number of bacteria"


def test_roman_fallback_ignores_prose_beginning_with_a_roman_letter():
    """An answer opening "is" or "in" must not read as a label."""
    assert ROMAN_FALLBACK_RE.match("is the same as before") is None
    assert ROMAN_FALLBACK_RE.match("in the beaker the potato") is None


def test_label_debris_is_removed_but_prose_is_not():
    assert LABEL_DEBRIS_RE.sub("", "i* The number of bacteria") == "The number of bacteria"
    # "Elastic" begins with a letter in the a-h range and must survive.
    assert LABEL_DEBRIS_RE.sub("", "Elastic potential energy") == "Elastic potential energy"


def test_merge_rows_joins_a_marker_to_the_answer_beside_it():
    """2023 has "37. (a)" at y=1773 and its answer "30°C" at y=1774. Ordering on
    `top` alone put the answer above its own marker, and 2022 Q35(a) lost "400 g"
    to the question before it."""
    merged = merge_rows([line("30°C", 438, 1774, width=120),
                         line("37. (a)", 249, 1773, width=150)])
    assert len(merged) == 1
    assert merged[0].text == "37. (a) 30°C"


def test_merge_rows_keeps_separate_rows_apart():
    merged = merge_rows([line("first line", 440, 1000),
                         line("second line", 440, 1060)])
    assert [m.text for m in merged] == ["first line", "second line"]


def test_columns_are_merged_independently():
    """A marker in the left column and body text in the right sit at the same
    height but are unrelated — joining them across the gutter is the failure the
    tesseract pass had."""
    lines = [line("29. (a) left column text", 400, 500, width=600),
             line("right column text", 1400, 500, width=600)]
    result = split_columns(lines, width=2481)
    assert [r.text for r in result] == ["29. (a) left column text",
                                        "right column text"]


def test_artefact_is_dropped_when_oversized_and_unsure():
    """2024 page 6 carries a "woul" box three line-heights tall at confidence
    0.30, which lands in the middle of Q40(b)'s model answer."""
    lines = [line("real text one", 440, 1000),
             line("real text two", 440, 1060),
             line("woul", 1050, 1286, height=175, width=190, confidence=0.3)]
    assert [l.text for l in drop_artefacts(lines)] == ["real text one", "real text two"]


def test_low_confidence_subpart_label_is_kept():
    """Most low-confidence lines in this corpus are real "(b)" / "(c)" labels.
    Dropping one silently merges its answer into the previous sub-part."""
    lines = [line("body text here", 440, 1000),
             line("(b)", 351, 1060, height=46, width=90, confidence=0.3)]
    assert [l.text for l in drop_artefacts(lines)] == ["body text here", "(b)"]


def test_recover_label_splits_at_the_outdented_line():
    """2023 Q36(b): Vision drops the "(b)" glyph but still starts the box where the
    label was, leaving the line outdented from the body around it."""
    answer = Answer(36, "a", [
        Chunk(line("The greater the number of turns", 254, 958), "The greater the number of turns", False),
        Chunk(line("of the propeller, the longer the", 443, 1014), "of the propeller, the longer the", False),
        Chunk(line("distance moved by the boat.", 448, 1070), "distance moved by the boat.", False),
        Chunk(line("Elastic potential energy", 407, 1121), "Elastic potential energy", False),
        Chunk(line("energy + sound energy", 438, 1177), "energy + sound energy", False),
    ])
    recovered = recover_label(answer, "b")
    assert recovered is not None
    assert recovered.part == "b"
    assert recovered.repaired is True
    assert " ".join(recovered.model_answer) == "Elastic potential energy energy + sound energy"
    assert "Elastic" not in " ".join(answer.model_answer)


def test_recover_label_refuses_when_the_split_is_ambiguous():
    """Two candidate outdents mean the geometry cannot say where the label was. A
    wrong split hands the child one sub-part's answer labelled as another's, so it
    refuses and leaves the warning standing."""
    answer = Answer(36, "a", [
        Chunk(line("first body line", 440, 1000), "first body line", False),
        Chunk(line("outdented one", 400, 1060), "outdented one", False),
        Chunk(line("more body text", 440, 1120), "more body text", False),
        Chunk(line("outdented two", 400, 1180), "outdented two", False),
    ])
    assert recover_label(answer, "b") is None


def test_recover_label_refuses_a_single_line_answer():
    answer = Answer(36, "a", [Chunk(line("only one line", 440, 1000), "only one line", False)])
    assert recover_label(answer, "b") is None


def test_nested_answer_label_satisfies_a_bare_indexed_one():
    """The inventory stops at "b" where the answers correctly nest "b(i)"/"b(ii)";
    2023 Q40 is indexed that way and must not raise a false alarm."""
    assert satisfied_by("b", {"b(i)", "b(ii)"})
    assert satisfied_by("a", {"a"})
    assert not satisfied_by("c", {"a", "b"})
