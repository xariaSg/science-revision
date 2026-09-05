"""Read an English answer key straight from its PDF text layer, when it has one.

Nan Hua and Tao Nan's 2025 prelim keys are typed documents, not scans -- zero
embedded images on every page -- so the text layer is not OCR of anything; it
*is* the source. That makes it a better read than any image-based extraction
could ever be, the same logic CLAUDE.md 1.1 applies to Science's five papers
with a genuine text layer, with one difference: those are an OCR pass over a
scan and this is native text, so there is nothing here to corroborate the way
`en_key.py`'s grid reader has to corroborate an OCR'd page.

The schools ingested so far print this key in one of two shapes, and both
reduce to the same walk over the page's lines: a run of *many* consecutive "QN"
labels is a block -- the Booklet A grid (25) and the Q26-35 letter bank (10) --
and its answers are that many single-line values immediately following, in
order. A label on its own opens an itemized entry instead, and its value runs
until the next label and is rejoined into one line -- the shape a wrapped
sentence answer (Q61-65) needs and a one-word answer never triggers.

Methodist Girls' itemized table (Q36-60, three columns) surfaces a PDF quirk
none of the ruled or single-column keys hit: a label is sometimes emitted
*twice* in the text stream -- once with nothing before the next label (a
phantom, no value ever follows it there) and once properly, later, immediately
before its real value. Two phantom labels in a row look exactly like the start
of a block to a naive reader -- "Q46) / Q39)" is indistinguishable from the
first two entries of a 25-item grid until the values fail to show up -- which
is why a run only ever becomes a block at BLOCK_RUN or more: nothing in this
corpus prints a genuine block shorter than 10, and nothing prints a phantom run
longer than one extra label, so a wide gap separates the two. Short runs fall
back to itemized mode on their *first* label only; the label(s) the run-check
swallowed along the way are re-offered to the very next iteration rather than
consumed, so a phantom is simply skipped -- it is not recorded with an empty
value -- and its real pairing further down still lands correctly.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

# "Q1", "Q 1", "Q29)" -- the space after Q and the trailing ")" are both seen,
# inconsistently, on the same page. St Nicholas drops the "Q" entirely from
# Q26 onward -- "26", "27", ... printed bare -- while keeping it for Q1-25 on
# the same page, so the prefix is optional. It cannot be optional for a single
# digit too: Booklet A's own values are bare single digits (the option 1-4 an
# "QN" label is paired with), and treating "4" as a label as readily as "46"
# would stop the block reader from ever telling a label row from a value row.
# Two schools' worth of "Q"-prefixed single digits (Q1-Q9) never need the bare
# form, so nothing is lost by requiring it only from double digits up.
LABEL_RE = re.compile(r"^(?:Q\s*(?P<number>\d{1,3})|(?P<bare>\d{2,3}))\s*\)?$")


def _label_number(match: re.Match) -> int:
    return int(match.group("number") or match.group("bare"))


# The shortest genuine block anywhere in this corpus is the 10-entry letter
# bank; the longest observed phantom-label run is 2. BLOCK_RUN sits between
# the two so neither is mistaken for the other.
BLOCK_RUN = 5


# The watermark every page carries, top and bottom. Dropped before pairing rather
# than left to be swept into whichever value happens to end a page -- otherwise
# the last itemized entry on a page picks up "www.sgexam.com" as part of its own
# answer, which is exactly what happened to Q65's sentence on the first paper
# this was run against.
WATERMARK_RE = re.compile(r"^www\.sgexam\.com$", re.I)


def has_native_text(pdf: Path) -> bool:
    """True when every page is typed text rather than a scan.

    Zero embedded images is the test, not a character count: a scanned page can
    carry thousands of characters of watermark text and still be a scan (every
    Booklet A page in this corpus does), and a short typed page can legitimately
    have few characters of its own.
    """
    doc = fitz.open(pdf)
    return all(not page.get_images(full=True) for page in doc)


def read_lines(pdf: Path) -> list[str]:
    doc = fitz.open(pdf)
    lines: list[str] = []
    for page in doc:
        lines.extend(line for line in page.get_text().splitlines()
                     if not WATERMARK_RE.match(line.strip()))
    return lines


def extract_pairs(lines: list[str]) -> dict[int, str]:
    """Every "QN" / value pair the key states, keyed on the question number.

    A pair with no value line before the text runs out, or a block whose value
    lines run short, is simply not recorded -- there is no partial line to guess
    from, and CLAUDE.md 1.6.1's rule applies here as everywhere else in this
    project: refuse rather than invent.
    """
    pairs: dict[int, str] = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        match = LABEL_RE.match(line)
        if not match:
            i += 1
            continue

        labels = [_label_number(match)]
        j = i + 1
        while j < n:
            candidate = lines[j].strip()
            if not candidate:
                j += 1
                continue
            follow = LABEL_RE.match(candidate)
            if not follow:
                break
            labels.append(_label_number(follow))
            j += 1

        if len(labels) >= BLOCK_RUN:
            # Block mode: the grid and the letter bank. Each label's value is
            # exactly one line, in the same order the labels were printed.
            values: list[str] = []
            k = j
            while k < n and len(values) < len(labels):
                candidate = lines[k].strip()
                if candidate:
                    values.append(candidate)
                k += 1
            if len(values) == len(labels):
                pairs.update(zip(labels, values))
            i = k
        else:
            # Itemized mode, on this label alone -- any further labels the run
            # check above swallowed are phantoms or belong to their own turn,
            # never to this one, so they are not consumed here. Value
            # collection starts right after this single label rather than at
            # `j`, which may have run past them.
            number = labels[0]
            collected: list[str] = []
            k = i + 1
            while k < n:
                candidate = lines[k].strip()
                if candidate and LABEL_RE.match(candidate):
                    break
                if candidate:
                    collected.append(candidate)
                k += 1
            if collected:
                pairs[number] = " ".join(collected)
            # An empty `collected` means the very next line was itself a label
            # -- this occurrence was a phantom with nothing following it, and
            # is left unrecorded rather than set to "" so a later, real
            # occurrence of the same label can still fill it in.
            i = k
    return pairs


def read_key(pdf: Path) -> dict[int, str]:
    return extract_pairs(read_lines(pdf))
