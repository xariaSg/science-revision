"""Tests for the 2025 school prelim corpus.

Three things here are worth a test rather than an eyeball, and they are the three
that failed silently while the corpus was being built:

* a paper is no longer named by its year, and fourteen papers now share one;
* the school prelims state their own shape in ways the PSLE papers never do, and
  one of them states it *wrongly*;
* their answer keys arrive in two typographies and one of those is a picture.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "app"))
sys.path.insert(0, str(REPO / "build"))

import papers as paper_ids  # noqa: E402
from db import by_paper_and_day  # noqa: E402
from index_mcq import read_structure, reconcile_structure  # noqa: E402
from ocr_vision import Line  # noqa: E402
from prelim_key import pair_runs  # noqa: E402
from prelims import paper_id, slugify  # noqa: E402


# --------------------------------------------------------------- paper identity

def test_a_prelim_id_carries_its_school_and_year():
    assert paper_id("MGS Paya Lebar") == "2025-prelim-mgs-paya-lebar"
    assert slugify("Raffles Girls") == "raffles-girls"


def test_a_psle_paper_is_still_named_by_its_year():
    """The ids that already existed do not move, so no URL and no logged
    attempt has to be rewritten."""
    assert paper_ids.year_of("2024") == 2024
    assert not paper_ids.is_prelim("2024")
    assert paper_ids.label("2024") == "2024"


def test_a_prelim_knows_the_year_it_was_sat():
    assert paper_ids.year_of("2025-prelim-rosyth") == 2025
    assert paper_ids.is_prelim("2025-prelim-rosyth")


def test_papers_sort_year_by_year_with_prelims_after_the_psle_paper():
    """A plain string sort interleaves the schools with later years."""
    ids = ["2025-prelim-ai-tong", "2024", "2025", "2025-prelim-rosyth", "2012"]
    assert sorted(ids, key=paper_ids.sort_key) == [
        "2012", "2024", "2025", "2025-prelim-ai-tong", "2025-prelim-rosyth"]


def test_the_picker_groups_psle_papers_before_prelims():
    groups = paper_ids.grouped(["2025-prelim-rosyth", "2024", "2025-prelim-ai-tong"])
    assert [g["group"] for g in groups] == ["PSLE papers", "2025 Prelims"]
    # Schools alphabetically: no school is more recent than another, so any other
    # order would look arbitrary.
    assert [p["paper"] for p in groups[1]["papers"]] == [
        "2025-prelim-ai-tong", "2025-prelim-rosyth"]


def test_two_prelims_from_one_year_are_two_bars():
    """The reason the rollup keys on the paper and not the year. Keyed on the
    year these would average into a single meaningless bar."""
    def attempt(paper, marks):
        return {"created_at": "2026-08-18T09:00:00+00:00", "paper": paper,
                "booklet": "A", "marks": marks, "marks_total": 2}

    bars = by_paper_and_day([attempt("2025-prelim-rosyth", 2),
                             attempt("2025-prelim-nanyang", 0),
                             attempt("2025", 2)])
    assert [(b["paper"], b["earned"]) for b in bars] == [
        ("2025", 2), ("2025-prelim-nanyang", 0), ("2025-prelim-rosyth", 2)]


# ------------------------------------------------- what a paper says about itself

def rows(*texts):
    """Recognised rows, one per line, all at the left margin."""
    return [(1, Line(text, 300, 100 * i, 2000, 100 * i + 40, 1.0))
            for i, text in enumerate(texts)]


def test_the_range_statement_is_read_in_every_wording_the_corpus_prints():
    """Nine schools use the PSLE wording; Red Swastika and Raffles Girls do not,
    and requiring the PSLE wording lost both."""
    for text in ("For each question from 1 to 28, four options are given.",
                 "For Questions 1 to 28, choose the most suitable answer",
                 "5. For Question 1-28, use 2B pencil to shade your answers"):
        expected, _, _, _, _ = reconcile_structure(read_structure(rows(text)))
        assert expected == (1, 28), text


def test_a_count_that_cannot_divide_the_total_is_rejected():
    """Rosyth prints "Booklet A [28 x 2 marks]" and, on the next line, a range
    statement whose 28 the scan renders as 23. 56 marks over 23 questions is not
    a whole number of marks each; over 28 it is exactly 2."""
    structure = read_structure(rows(
        "Booklet A [28 x 2 marks]",
        "For each question from 1 to 23, four options are given."))
    expected, total, each, _, warnings = reconcile_structure(structure)
    assert expected == (1, 28)
    assert (total, each) == (56, 2)
    assert any("23" in w for w in warnings), "the disagreement must be reported"


def test_a_count_and_a_total_on_one_line_are_one_statement():
    """Red Swastika's "Booklet A: 28 questions (56 marks)" states both. Counting
    it twice would let one printed line outvote two independent ones."""
    expected, total, _, _, _ = reconcile_structure(
        read_structure(rows("Booklet A: 28 questions (56 marks)")))
    assert expected == (1, 28)
    assert total == 56


def test_a_paper_stating_only_a_total_still_yields_a_range():
    """Nanyang prints no range and no count anywhere -- only "[56 marks]"."""
    expected, total, _, source, _ = reconcile_structure(
        read_structure(rows("Section A: Multiple Choice Questions [56 marks]")))
    assert expected == (1, 28)
    assert total == 56
    assert "assumed" in source, "an assumed value must say that it is assumed"


def test_a_paper_that_states_nothing_is_refused_rather_than_guessed():
    expected, _, _, _, _ = reconcile_structure(
        read_structure(rows("Answer all questions.")))
    assert expected is None


# ------------------------------------------------------------------ answer keys

def test_a_transposed_table_pairs_labels_with_the_answers_beneath_them():
    """Eleven schools print a row of Q labels then a row of digits."""
    tokens = ["Q1", "Q2", "Q3", "2", "3", "4"]
    found, problems = pair_runs(tokens, {1, 2, 3})
    assert found == {1: 2, 2: 3, 3: 4}
    assert not problems


def test_a_paired_grid_reads_the_same_way():
    """ACS Junior prints (question, answer) pairs instead."""
    found, problems = pair_runs(["Q1", "3", "Q11", "3", "Q21", "3"], {1, 11, 21})
    assert found == {1: 3, 11: 3, 21: 3}
    assert not problems


def test_a_label_with_a_space_is_still_a_label():
    """Methodist Girls types "Q 1" and "Q 15"."""
    found, _ = pair_runs(["Q 1", "Q 2", "3", "4"], {1, 2})
    assert found == {1: 3, 2: 4}


def test_booklet_b_answers_are_not_mistaken_for_booklet_a_ones():
    """Rosyth's key runs straight on into "Q29 (a) W -> Y -> Z -> X", which has
    no digit run after it and is not a Booklet A row."""
    found, problems = pair_runs(["Q1", "4", "Q29", "(a)", "W", "Q30"], {1})
    assert found == {1: 4}
    assert not problems


def test_a_short_answer_run_is_reported_rather_than_paired_off():
    """Three labels and two answers means one was dropped; pairing the two that
    survived against the first two labels would put every answer after it on the
    wrong question."""
    found, problems = pair_runs(["Q1", "Q2", "Q3", "2", "3"], {1, 2, 3})
    assert found == {}
    assert problems and "3 questions but 2 answers" in problems[0]


# -------------------------------------------------------- the built corpus itself

def built_keys():
    return sorted((REPO / "work-ans").glob("2025-prelim-*/mcq-answers.json"))


def test_every_built_prelim_key_covers_its_whole_booklet():
    """The check that actually guards the child: a key is only usable if it
    answers every question the booklet asks, and a misread digit here tells her
    she was wrong when she was right (CLAUDE.md section 1.6.1)."""
    keys = built_keys()
    if not keys:
        return  # nothing built in this checkout
    for path in keys:
        key = json.loads(path.read_text())
        answers = {a["question"]: a["answer"] for a in key["answers"]}
        assert len(answers) == key["booklet_questions"], f"{path.parent.name} short"
        assert set(answers.values()) <= {1, 2, 3, 4}, f"{path.parent.name} bad option"
        assert not key["warnings"], f"{path.parent.name}: {key['warnings']}"
