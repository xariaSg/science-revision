"""Tests for transcript anchor repair.

Scenario anchors are what the contextual gate keys on (CLAUDE.md section 3.3), so a
transcript that loses "plant E" fails a correct answer. These pin the repair.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from stt import build_prompt, repair_anchors  # noqa: E402


def test_runs_together_anchor_is_restored():
    """Observed with both small.en and base.en: "plant E" -> "Planty"."""
    out = repair_anchors("Planty has longer roots than Plant H.",
                         ["plant E", "plant H"])
    assert "plant E" in out
    assert "Planty" not in out


def test_spelled_out_letter_is_restored():
    out = repair_anchors("Fish sea decreased because bird bee ate more.",
                         ["fish C", "bird B"])
    assert "fish C" in out and "bird B" in out


def test_already_correct_text_is_left_alone():
    text = "plant E has longer roots than plant H."
    assert repair_anchors(text, ["plant E", "plant H"]) == text


def test_ordinary_words_are_not_rewritten():
    """"plants" must not become "plant E"."""
    text = "The plants grew well in the soil."
    assert repair_anchors(text, ["plant E"]) == text


def test_no_anchors_is_a_passthrough():
    text = "The water evaporated."
    assert repair_anchors(text, []) == text
    assert repair_anchors(text, None) == text


def test_unrelated_anchor_does_not_fire():
    text = "The beaker was full."
    assert repair_anchors(text, ["tube A"]) == text


def test_prompt_leads_with_this_questions_anchors():
    prompt = build_prompt(["plant E", "bird B"])
    assert prompt.startswith("This question is about plant E, bird B.")


def test_prompt_without_anchors_is_the_glossary():
    assert "PSLE primary science" in build_prompt(None)
