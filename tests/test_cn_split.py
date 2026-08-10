"""Unit tests for splitting a Chinese compilation into Paper 2 and its answers.

This step used to be done by hand, and the hand-split files disagreed with each
other in a way nothing downstream could see: a Paper 2 missing its first booklet
still indexes, still validates, and simply has fewer questions in it. So the two
things worth testing are that the split is derived from the page's own footer,
and that the cross-check against each cover's stated length actually bites.

Both OCR failures below were hit on real pages. Neither is exotic and both are
silent: the slash vanishing from a code turns a cover into an unlabelled page,
and a Cyrillic letter standing in for a Latin one splits a booklet in two.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from cn_split import (  # noqa: E402
    CODE, CONSISTS, COVER, COVER_BOOKLET, LATIN_BOOKLET,
)


def code_of(text):
    """The page's label, as _label_pages reads it: the last code on the page."""
    label = None
    for match in CODE.finditer(text):
        paper, booklet = match.group("paper"), match.group("booklet")
        booklet = LATIN_BOOKLET.get(booklet, booklet) if booklet else None
        label = f"{paper}{booklet}" if booklet else paper
    return label


# ------------------------------------------------------------------- footer codes

def test_the_paper_and_booklet_are_read_from_the_footer():
    assert code_of("0005/2(A)/2017") == "2A"
    assert code_of("0005/2(B)/2012") == "2B"
    assert code_of("0005/1/2025") == "1"
    assert code_of("0005/3/LC/2017") == "3"


def test_a_bare_paper_two_code_carries_no_booklet():
    """2021-2025 print one booklet, so the code has no letter to read."""
    assert code_of("0005/2/2023") == "2"


def test_a_cyrillic_booklet_letter_is_read_as_latin():
    """2016 p23's footer comes back as "0005/2(В)/2016" with a Cyrillic Ve. A
    plain [AB] misses it, dropping the page's booklet and splitting the run."""
    assert code_of("0005/2(В)/2016") == "2B"
    assert code_of("0005/2(А)/2016") == "2A"


def test_the_footer_wins_over_a_code_mentioned_earlier_on_the_page():
    assert code_of("see 0005/1 for the composition\n0005/2(B)/2019") == "2B"


def test_a_page_with_no_code_is_unlabelled():
    """Answer pages carry no code at all, and that is what identifies them."""
    assert code_of("PSLE 华文历届会考-参考答案") is None


# ------------------------------------------------------------------------ covers

def test_a_cover_names_itself_in_latin():
    """A better anchor than the cover's own code: 2013 p17's reads "000512 (B)"
    with the slash gone, but every cover in the corpus titles itself cleanly."""
    text = ("MINISTRY OF EDUCATION, SINGAPORE\n000512 (B)\n"
            "CHINESE PAPER 2\n(BOOKLET B)")
    assert COVER.search(text)
    assert COVER_BOOKLET.search(text).group(1).upper() == "B"
    assert code_of(text) != "2B"          # the code alone would have missed it


def test_a_cover_states_its_own_length():
    match = CONSISTS.search("This booklet consists of 9 printed pages and 3 blank pages.")
    assert (match.group(1), match.group(2)) == ("9", "3")


def test_a_cover_may_state_no_blank_pages():
    match = CONSISTS.search("This booklet consists of  8 printed pages.")
    assert (match.group(1), match.group(2)) == ("8", None)


def test_the_cover_counts_itself_among_the_printed_pages():
    """"9 printed and 3 blank" is a 12-page booklet, cover included -- the same
    arithmetic as Science's Booklet A cover (CLAUDE.md section 1.3). Adding one
    for the cover made every year of the corpus disagree with its own footers."""
    match = CONSISTS.search("consists of 9 printed pages and 3 blank pages")
    printed, blank = int(match.group(1)), int(match.group(2) or 0)
    assert printed + blank == 12


def test_the_cover_sentence_is_not_confused_with_a_blank_page_marker():
    """Science hit this the other way round (CLAUDE.md section 1.3): the cover's
    own "and 1 blank page" marked the cover itself as blank. Here the count is
    parsed rather than the words, so the sentence is only ever a statement."""
    match = CONSISTS.search("This booklet consists of 11 printed pages and 1 blank page.")
    assert (match.group(1), match.group(2)) == ("11", "1")
