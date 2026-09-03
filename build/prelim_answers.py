"""Extract each school's Booklet B suggested answers, sub-part by sub-part.

Same job as extract_answers.py does for the PSLE corpus, against a source that is
far less uniform. Seven schools typed their answers and seven scanned them, and
the seven typed ones label their sub-parts six different ways:

    29a                      ACS Junior, Methodist Girls
    29  / a Reproduce...     Henry Park
    29  / (a) Concept:...    SCGS
    Q29) / a) Animal X...    Raffles Girls
    Q29 (a)                  Rosyth
    Q29(a)                   St Nicholas

So the label is parsed rather than matched against a known shape, and -- this is
what keeps it honest -- **a part label is only believed when the paper itself
asks for that part**. `index_questions.py` has already read Booklet B and knows
that question 29 has an (a), a (b) and a (c); a line beginning "a Reproduce by
seeds." is a label when 29(a) is expected and has not been seen, and is ordinary
prose otherwise. Without that check, body text opening with "a" or "(i)" starts a
new sub-part and every answer after it lands on the wrong question -- the silent
cascade CLAUDE.md section 7.4 describes, which produces a well-formed rubric
attached to the wrong prose.

These answers are shown to the student for self-marking and are the raw material
for authoring rubrics; they are never themselves a mark. That is why an
unreadable answer here is a gap to report rather than a failure to refuse over,
unlike the Booklet A key (section 1.6.1), where a misread digit is marked against
a child directly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

import corpus
import prelims
from ocr_vision import page_lines

REPO = Path(__file__).resolve().parent.parent
WORK_B = REPO / "work-b"
WORK_ANS = REPO / "work-ans"

WATERMARK_RE = re.compile(r"www\.sgexam\.com", re.I)

# A sub-part letter is only a label when something separates it from what follows:
# a closing bracket, a stop, a space, or the end of the line. Without that, the
# first letter of an ordinary word is a label -- "converted into sugar and oxygen"
# opens sub-part (c) and swallows the rest of the answer, which is how St Nicholas
# Q30 came out with its photosynthesis definition cut in half and the second half
# filed under (c). The paper's own part list cannot catch this on its own, because
# (c) is a part the paper really does ask for.
_ENDS = r"(?=[\s).:,]|$)"
# A question number, alone or carrying its sub-part: "29", "Q29)", "29a",
# "Q29 (a)", "Q29(a)", "30b(ii)". The brackets, the "Q" and the space are all
# optional because between them the fourteen schools use every combination.
LABEL_RE = re.compile(
    r"^Q?\s*(?P<question>\d{2})\s*[).]?\s*"
    r"(?:\(\s*(?P<part>[a-h])\s*\)|(?P<part2>[a-h])" + _ENDS + r")?\s*"
    r"(?:\(\s*(?P<roman>i{1,3}|iv|v)\s*\)|(?P<roman2>i{1,3}|iv|v)" + _ENDS + r")?\s*"
    r"(?P<rest>.*)$", re.I)
# A sub-part on its own, once a question is open: "(a)", "a)", "b ...", "a)i)".
PART_RE = re.compile(
    r"^(?:\(\s*(?P<part>[a-h])\s*\)|(?P<part2>[a-h])" + _ENDS + r")[.:]?\s*"
    r"(?:\(\s*(?P<roman>i{1,3}|iv|v)\s*\)|(?P<roman2>i{1,3}|iv|v)" + _ENDS + r")?[.:]?\s*"
    r"(?P<rest>.*)$", re.I)


def _group(match: re.Match, name: str) -> str | None:
    """Either spelling of a group: bracketed, or bare with a separator after."""
    return match.group(name) or match.group(f"{name}2")


# Booklet B never starts below this in either corpus, so a two-digit number under
# it is a quantity in the prose rather than a question number.
MIN_QUESTION = 29


def part_label(part: str | None, roman: str | None) -> str | None:
    """"b" + "ii" -> "b(ii)", the form index_questions.py records."""
    if part and roman:
        return f"{part.lower()}({roman.lower()})"
    return (part or roman or "").lower() or None


def expected_parts(paper: str) -> dict[int, list[str | None]]:
    """What Booklet B asks for, read from the paper rather than the answers.

    The answer key is checked against this, not the other way round: the paper is
    the thing being sat.
    """
    path = WORK_B / paper / "questions.json"
    if not path.exists():
        raise FileNotFoundError(f"{paper}: run build/index_questions.py first")
    data = json.loads(path.read_text())
    return {q["question"]: [p["part"] for p in q["parts"] if not p.get("is_parent")]
            for q in data["questions"]}


def typed_lines(paper: str) -> list[str]:
    """The answer document's text layer, watermark removed."""
    src = prelims.part_path(paper, "Answers")
    with fitz.open(src) as doc:
        return [line.strip()
                for page in doc
                for line in WATERMARK_RE.sub("", page.get_text()).splitlines()
                if line.strip()]


def scanned_lines(paper: str) -> list[str]:
    """The answer pages as Vision reads them."""
    out: list[str] = []
    for image in sorted((WORK_ANS / paper / "pages").glob("answer-*.png")):
        out.extend(line.text.strip() for line in page_lines(image)
                   if line.text.strip() and "sgexam" not in line.text.lower())
    return out


def read_answers(lines: list[str],
                 wanted: dict[int, list[str | None]]) -> dict[int, dict]:
    """Walk the document, opening a sub-part only where the paper asks for one."""
    answers: dict[int, dict[str | None, list[str]]] = {}
    question: int | None = None
    part: str | None = None

    def open_slot(number: int, label: str | None) -> bool:
        if number not in wanted:
            return False
        if label is not None and label not in wanted[number]:
            return False
        if label is None and wanted[number] and wanted[number] != [None]:
            # The question has named sub-parts, so a bare number is its heading;
            # the labels follow on the lines beneath it.
            answers.setdefault(number, {})
            return False
        if label in answers.get(number, {}):
            return False        # already filled: this is prose, not a label
        answers.setdefault(number, {})[label] = []
        return True

    for line in lines:
        match = LABEL_RE.match(line)
        if match and int(match.group("question")) >= MIN_QUESTION:
            number = int(match.group("question"))
            label = part_label(_group(match, "part"), _group(match, "roman"))
            if number in wanted:
                if open_slot(number, label):
                    question, part = number, label
                    rest = match.group("rest").strip()
                    if rest:
                        answers[number][label].append(rest)
                    continue
                if label is None:
                    question, part = number, None
                    continue

        if question is not None:
            match = PART_RE.match(line)
            if match:
                label = part_label(_group(match, "part"), _group(match, "roman"))
                if open_slot(question, label):
                    part = label
                    rest = match.group("rest").strip()
                    if rest:
                        answers[question][label].append(rest)
                    continue

        if question is not None and part in answers.get(question, {}):
            answers[question][part].append(line)
    return answers


def extract(paper: str, school: str | None = None) -> dict:
    wanted = expected_parts(paper)
    warnings: list[str] = []

    # Which source to read is decided by what each one actually yields, not by how
    # much text it holds. Four schools typed their Booklet A key and scanned their
    # Booklet B answers, so the document has a healthy text layer that contains
    # none of what is wanted here -- choosing on size picked it and returned
    # nothing for the whole booklet.
    def score(answers: dict) -> int:
        return sum(1 for parts in answers.values() for text in parts.values()
                   if " ".join(text).strip())

    answers = read_answers(typed_lines(paper), wanted)
    read_from = "pdf text layer"
    if score(answers) < len(wanted):
        from_scan = read_answers(scanned_lines(paper), wanted)
        if score(from_scan) > score(answers):
            answers, read_from = from_scan, "scan (macos-vision)"

    out = []
    for number in sorted(answers):
        parts = [{"part": label,
                  "model_answer": " ".join(text).strip(),
                  "explanation": ""}
                 for label, text in answers[number].items()
                 if " ".join(text).strip()]
        if parts:
            out.append({"question": number, "parts": parts})

    found = {(q["question"], p["part"]) for q in out for p in q["parts"]}
    asked = {(number, label) for number, labels in wanted.items()
             for label in labels}
    # A question with no sub-parts records its label as None, which will not
    # sort against a string.
    missing = sorted(asked - found, key=lambda x: (x[0], x[1] or ""))
    if missing:
        warnings.append(
            f"no suggested answer found for {len(missing)} of {len(asked)} "
            f"sub-parts: {['Q%d%s' % (q, f'({p})' if p else '') for q, p in missing[:8]]}"
            + (" ..." if len(missing) > 8 else ""))

    return {
        "paper": paper,
        "school": school,
        "source": f"{school or paper} suggested answers",
        "read_from": read_from,
        "authoritative": False,
        "questions": out,
        "sub_parts_found": len(found),
        "sub_parts_asked": len(asked),
        "warnings": warnings,
        "needs_review": bool(warnings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", nargs="*")
    args = parser.parse_args(argv)

    registry = {p["paper"]: p for p in prelims.load_registry()}
    papers = args.papers or sorted(registry, key=corpus.sort_key)
    for paper in papers:
        try:
            result = extract(paper, (registry.get(paper) or {}).get("school"))
        except FileNotFoundError as err:
            print(f"{paper}: {err}", file=sys.stderr)
            continue
        out = WORK_ANS / paper / "answers.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2))
        print(f"{result['school'] or paper:16s} "
              f"{result['sub_parts_found']:3d}/{result['sub_parts_asked']:3d} "
              f"sub-parts  [{result['read_from']}]")
        for warning in result["warnings"]:
            print(f"    NOTE {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
