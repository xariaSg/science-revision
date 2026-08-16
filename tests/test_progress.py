"""Tests for the progress rollups.

These are the two pieces of the report that turned out to have a wrong answer that
still looks right: a bar split into how the marks were answered for, and the key
that names the split. Both read from the attempt log, so neither has a source of
truth to be checked against once it is on the page.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from db import by_paper_and_day, kinds_present  # noqa: E402

KINDS = [("mcq", "Booklet A · MCQ", "A"), ("oeq", "Booklet B · written", "B")]


def kind_of(row):
    return "mcq" if row["booklet"] == "A" else "oeq"


def attempt(day, year, booklet, marks, total):
    return {"created_at": f"{day}T09:00:00+00:00", "year": year,
            "booklet": booklet, "marks": marks, "marks_total": total}


def test_bucket_is_one_paper_on_one_day():
    """Two papers on one day are two results, not one average."""
    papers = by_paper_and_day([
        attempt("2026-08-16", 2021, "A", 2, 2),
        attempt("2026-08-16", 2024, "A", 0, 2),
        attempt("2026-08-17", 2021, "A", 2, 2),
    ], KINDS, kind_of)
    assert [(p["date"], p["year"], p["earned"]) for p in papers] == [
        ("2026-08-16", 2021, 2), ("2026-08-16", 2024, 0), ("2026-08-17", 2021, 2)]


def test_split_sums_to_the_bar():
    """The blocks are the bar taken apart, so they have to add back up to it."""
    [paper] = by_paper_and_day([
        attempt("2026-08-16", 2021, "A", 2, 2),
        attempt("2026-08-16", 2021, "A", 0, 2),
        attempt("2026-08-16", 2021, "B", 1, 3),
    ], KINDS, kind_of)

    assert (paper["earned"], paper["possible"], paper["attempts"]) == (3, 7, 3)
    assert [(p["id"], p["earned"], p["possible"], p["attempts"]) for p in paper["parts"]] \
        == [("mcq", 2, 4, 2), ("oeq", 1, 3, 1)]
    assert sum(p["earned"] for p in paper["parts"]) == paper["earned"]
    assert sum(p["possible"] for p in paper["parts"]) == paper["possible"]


def test_a_kind_with_nothing_in_it_does_not_appear():
    """A Booklet A morning draws as one block, not as a half-empty pair."""
    [paper] = by_paper_and_day([attempt("2026-08-16", 2021, "A", 2, 2)],
                               KINDS, kind_of)
    assert [p["id"] for p in paper["parts"]] == ["mcq"]


def test_blocks_stack_in_the_order_the_paper_is_sat():
    """Not the order the rows happen to arrive in: the chart stacks the first kind
    at the base, and a key ordered by the log would disagree with the picture."""
    rows = [attempt("2026-08-16", 2021, "B", 1, 1),
            attempt("2026-08-16", 2021, "A", 2, 2)]
    [paper] = by_paper_and_day(rows, KINDS, kind_of)
    assert [p["id"] for p in paper["parts"]] == ["mcq", "oeq"]
    assert [k["id"] for k in kinds_present([paper], KINDS)] == ["mcq", "oeq"]


def test_the_key_names_only_what_is_on_the_chart():
    papers = by_paper_and_day([attempt("2026-08-16", 2021, "A", 2, 2)],
                              KINDS, kind_of)
    assert [k["short"] for k in kinds_present(papers, KINDS)] == ["A"]


def test_unmarked_attempts_are_not_on_the_chart():
    """A written answer waiting to be marked is not a zero."""
    assert by_paper_and_day([attempt("2026-08-16", 2021, "B", None, 3)],
                            KINDS, kind_of) == []


def test_no_split_declared_still_rolls_up():
    """Chinese asked for a split before the chart could draw one; the bar itself
    must not depend on there being one."""
    [paper] = by_paper_and_day([attempt("2026-08-16", 2021, "A", 2, 2)])
    assert (paper["earned"], paper["percent"], paper["parts"]) == (2, 100, [])
