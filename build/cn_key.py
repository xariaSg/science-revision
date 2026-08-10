"""Extract the answer key for a PSLE Chinese Paper 2.

The key is a far better source than Science's was, in one specific way: the
publisher prints a mark marker at every award point inside the model answer --
"贝贝的两个哥哥经常吵架（1）。因为二哥经常争做老大（1）" -- so the keypoint
decomposition that build/rubric.py leaves empty for a human to author arrives
already done, and it can be checked, because the markers must sum to the mark the
paper itself states.

Layout is single-column with left-margin question numbers, so none of the
two-column geometry that Science's key needed applies. Three things do:

* The key covers Paper 3 as well, and Paper 3 restarts at Q1. A bare QN match
  over the document collides with 语文应用, so numbering is scoped by the 試卷
  banner that precedes it.
* A model answer's first line is typeset level with its own question number but
  starts a few pixels higher. Sorting by `top` therefore puts the body BEFORE the
  anchor and every answer lands on the previous question -- a silent cascade that
  gives Q36 a 1-mark rubric instead of 3. Lines are banded into visual rows and
  ordered within the band instead.
* Mark markers count only inside the model answer. "故选（3）" in a 注解 is a
  reference to an option, not an award.

One systematic exception, present in both years: Q33's markers sum to 1.5 against
a stated 4, because half its marks are 语言 quality, which is holistic and has no
span to point at. That is the publisher's behaviour, not a parse failure, and it
is reported rather than repaired.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ocr_vision import page_lines  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"

LANGUAGES = ("zh-Hans", "en-US")

BOOKLET_BANNER = re.compile(r"[試试]卷([一二三])")
BOOKLET_OF = {"一": "paper1", "二": "paper2", "三": "paper3"}
SECTION_NAME = re.compile(
    r"(语文应用|短文填空|阅读理解一|完成对话|阅读理解二|听力测验)")

ANCHOR = re.compile(r"^Q\s*(\d+)")
# The same row with its "Q" misrecognised. 2013's Q29 comes back as "929" at
# confidence 0.30, and the answer to the first question of 阅读理解二 disappears
# from the key. Used only to CONFIRM a number the sequence has already fixed --
# it must be the very next question, one the paper says exists, and not yet
# seen -- never to discover one. Read the other way round it would turn any
# left-margin number into a question (CLAUDE.md sections 1.5.1 and 7.5).
DAMAGED_ANCHOR = re.compile(r"^([9OoDQ0])\s*(\d+)")
# Everything after the question number on its own row.
ENTRY = re.compile(r"^Q\s*(\d+)\s*(.*)$")
# Vision sometimes reads the key's plain "(2)" as a circled numeral. On 2024 it
# emits both forms at once -- Q7 is "（②2）" -- and on 2021 it drops the brackets
# entirely, giving a bare "Q1 ②". Both were checked against the scans, which
# print an ordinary (2) in the same type as their neighbours.
CIRCLED = {chr(0x2460 + i): str(i + 1) for i in range(20)}
CJK = re.compile(r"[一-鿿]")


def number_of(text: str, expected: set[int] | None = None) -> tuple[int | None, str]:
    """The question number on a key row, and whatever follows it.

    2023 loses the opening bracket on Q19, giving "Q194） 所有" -- read greedily
    that is question 194, and the real Q19 vanishes without leaving a gap anyone
    would notice. So the longest digit run that the paper actually contains wins,
    and the leftover digits fall through to the option. Same discipline as the
    question index: the sequence decides the number, the glyphs only confirm it.
    """
    match = ANCHOR.match(text)
    if match is None:
        return None, ""
    digits, rest = match.group(1), text[match.end():]
    for take in range(len(digits), 0, -1):
        number = int(digits[:take])
        if expected is None or number in expected:
            return number, digits[take:] + rest
    return int(digits), rest


def option_of(rest: str) -> tuple[int | None, str | None]:
    """Read a chosen answer's option from the text following its number.

    The option is a digit and nothing else, which is what separates "Q1 （2）"
    from the written "Q34 插嘴（2）" -- there the bracket holds a mark marker, not
    an option. But on 2021-2023 Vision runs the option together with the next
    column: Q16 arrives as "（4） |实现" and Q21 as "（2） 考生可以从文章…". So the
    option is taken from the run BEFORE any Chinese begins, and a row whose text
    starts in Chinese has no option at all.

    Every digit in that run must agree. Duplicated glyphs for one digit are the
    known artefact and are accepted; two different digits mean the read is
    unsafe, and refusing beats guessing -- a wrong option here tells a child they
    were wrong when they were right, with no partial credit to soften it
    (CLAUDE.md section 1.6.1).
    """
    cjk = CJK.search(rest)
    leading = (rest[:cjk.start()] if cjk else rest).strip()
    if not leading:
        return None, None
    digits = {CIRCLED.get(ch, ch) for ch in leading if CIRCLED.get(ch, ch).isdigit()}
    return (int(digits.pop()) if len(digits) == 1 else None), leading
MARKER = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*[）)]")
NOTE = re.compile(r"^[（(]\s*[注註]解")
MARK_SCHEME = re.compile(r"[（(]\s*评分标准\s*[：:]\s*(.+?)[）)]")
FREE_RESPONSE = re.compile(r"[（(]\s*答案合理即可\s*[）)]")
# A model answer printed as a table rather than prose -- 2012 Q31, 2014 Q32 and
# 2016 Q32, three in the whole corpus. Rows are read left to right, which is
# right for text and wrong here: the left cell's words end up threaded through
# the right cell's ("父亲有奇（a） 儿子的反应怪的举动感到丢脸…"). Three questions
# do not justify reconstructing table geometry, and all three are self-marked
# anyway, but a child comparing their answer against a scrambled one should be
# told to read it off the scan instead.
SUB_LABEL = re.compile(r"[（(]\s*[abc]\s*[）)]")
FOOTER = re.compile(r"Educational Publishing|历届会考|歷屆會考|參考答案|参考答案")
# Column and group headings, which belong to the section that follows rather than
# to the answer above them. Without this the last entry of every section trails
# the next one's headings -- 2012 Q16 ends "忘记：不记得。forgetA组注解/说明" --
# on all fourteen years. Matched only as a whole line, so the "（注解：…）" that
# opens a real note is untouched.
HEADING = re.compile(r"^(?:[注註]解\s*[/／]\s*[说說]明|[AB]\s*[组組])$")

# The vocabulary glosses on the MCQ sections read "锻炼 duàn liàn：通过身体活动…
# to exercise". The characters and the English survive OCR; the pinyin does not.
# Not one of the sixteen glosses on the 2025 key came back with correct tones, and
# nine were mangled into something that still looks like text -- 克服 kèfú as
# "KefG", 眉开眼笑 as "meikaiy8n xido". Wrong pinyin shown to a child teaches a
# wrong pronunciation with full confidence, so the romanisation between the
# headword and the definition is dropped rather than displayed.
# No leading-space anchor: the headword and the romanisation arrive as separate
# OCR lines and are joined without one, so "锻炼" + "duàn liàn：" becomes
# "锻炼duan Idn：" and a \s lookbehind would strip only the second syllable.
PINYIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\s]*(?=[：:])")

# A question number sits at the left margin of the single column; a "Q33" inside
# a model answer or a 注解 does not. Separating them by an absolute pixel limit
# only worked because every year it had been run on shared a margin: at 300 dpi
# the anchors sit at 183 on 2025 and at 619 on 2017, so a limit tuned to the
# newer papers silently dropped two thirds of 2017's key and the whole of its
# Booklet B. The margin is measured per page instead -- the leftmost anchor on
# the page, plus a tolerance for the wobble between one row and the next.
#
# The cap is what keeps a page whose only anchor is mid-text from defining its
# own margin. Every real margin in the corpus is under a quarter of the page
# width and every mid-text reference is past half of it, so a third separates
# them with room to spare either way.
ANCHOR_TOLERANCE = 60
ANCHOR_MAX_FRACTION = 0.33


def anchor_margin(lines, width: int) -> float | None:
    """The left margin of this page's question numbers, or None if it has none."""
    lefts = [ln.left for ln in lines
             if ANCHOR.match(ln.text.strip()) and ln.left < width * ANCHOR_MAX_FRACTION]
    return min(lefts) + ANCHOR_TOLERANCE if lefts else None


def strip_pinyin(text: str) -> str:
    return PINYIN.sub("", text, count=1)


def rows(lines, overlap: float = 0.4) -> list[list]:
    """Cluster lines into visual rows, ordered left to right within each row."""
    out: list[list] = []
    for line in sorted(lines, key=lambda ln: ln.top):
        for row in out:
            top = max(min(ln.top for ln in row), line.top)
            bottom = min(max(ln.bottom for ln in row), line.bottom)
            height = min(max(ln.bottom - ln.top for ln in row),
                         line.bottom - line.top)
            if height and (bottom - top) / height > overlap:
                row.append(line)
                break
        else:
            out.append([line])
    return [sorted(row, key=lambda ln: ln.left) for row in out]


def answer_pages(year: int, work_dir: Path = WORK_DIR):
    pages_dir = work_dir / str(year) / "answer-pages"
    if not pages_dir.exists():
        raise SystemExit(f"no unpacked answers for {year}; run build/cn_unpack.py")
    manifest = json.loads((work_dir / str(year) / "manifest.json").read_text())
    widths = {p["page_number"]: p["width"] for p in manifest["answers"]["pages"]}
    for image in sorted(pages_dir.glob("answer-*.png")):
        number = int(image.stem.split("-")[1])
        yield number, page_lines(image, languages=LANGUAGES), widths[number]


def parse_key(year: int, work_dir: Path = WORK_DIR,
              expected: set[int] | None = None) -> dict:
    entries: dict[tuple[str, int], dict] = {}
    booklet = "paper2"
    section = None
    current = None
    repairs: list[str] = []
    last_seen: dict[str, int] = {}

    for page, lines, width in answer_pages(year, work_dir):
        margin = anchor_margin(lines, width)
        for row in rows(lines):
            at_margin = [ln for ln in row
                         if margin is not None and ln.left <= margin]
            anchor_line = next(
                (ln for ln in at_margin if ANCHOR.match(ln.text.strip())), None)
            anchor_text = anchor_line.text.strip() if anchor_line else ""

            if anchor_line is None and booklet == "paper2" and expected:
                wanted = last_seen.get(booklet, 0) + 1
                for ln in at_margin:
                    m = DAMAGED_ANCHOR.match(ln.text.strip())
                    if (m and m.group(1) != "Q" and int(m.group(2)) == wanted
                            and wanted in expected
                            and (booklet, wanted) not in entries):
                        anchor_line = ln
                        anchor_text = "Q" + ln.text.strip()[len(m.group(1)):]
                        repairs.append(
                            f"Q{wanted}: read from '{ln.text.strip()}' on "
                            f"answer p{page}; the next question in sequence")
                        break

            for line in row:
                text = line.text.strip()
                if (m := BOOKLET_BANNER.search(text)) and line.left < 700:
                    booklet, current = BOOKLET_OF[m.group(1)], None
                if (m := SECTION_NAME.search(text)) and line.left < 800:
                    section = m.group(1)

            if anchor_line is not None:
                # Only Paper 2's numbering is known; Paper 3 restarts and is not
                # served by the app, so it is read as-is.
                number, rest = number_of(
                    anchor_text, expected if booklet == "paper2" else None)
                last_seen[booklet] = number
                option, option_raw = option_of(rest)
                current = entries.setdefault(
                    (booklet, number),
                    {"booklet": booklet, "question": number, "section": section,
                     "page": page, "option": option, "option_raw": option_raw,
                     "body": [], "notes": [], "rest": rest},
                )

            if current is None:
                continue

            for line in row:
                text = line.text.strip()
                if line is anchor_line:
                    text = current["rest"].strip()
                    if current["option"] is not None or not text:
                        continue
                elif (BOOKLET_BANNER.search(text) or SECTION_NAME.search(text)
                        or FOOTER.search(text) or HEADING.match(text)
                        or text.isdigit()):
                    continue
                if NOTE.match(text) or current["notes"]:
                    current["notes"].append(text)
                else:
                    current["body"].append(text)

    out = []
    for entry in entries.values():
        body, notes = "".join(entry["body"]), "".join(entry["notes"])
        if entry["option"] is not None:
            # Only the vocabulary glosses carry a romanisation; a written model
            # answer never does, and must not be touched.
            body, notes = strip_pinyin(body), strip_pinyin(notes)
        markers = [float(v) for v in MARKER.findall(body)]
        scheme = MARK_SCHEME.search(body + notes)
        out.append({
            "booklet": entry["booklet"],
            "question": entry["question"],
            "section": entry["section"],
            "page": entry["page"],
            "option": entry["option"],
            "option_raw": entry.get("option_raw"),
            "model_answer": body,
            "note": notes,
            "markers": markers,
            "marker_total": round(sum(markers), 2),
            "free_response": bool(FREE_RESPONSE.search(body + notes)),
            "mark_scheme": scheme.group(1) if scheme else None,
            "table_layout": entry["option"] is None and bool(SUB_LABEL.search(body)),
        })
    out.sort(key=lambda e: (e["booklet"], e["question"]))
    return {"year": year, "subject": "chinese",
            "source": "EPH suggested answer", "authoritative": False,
            "ocr": "macos-vision", "repairs": repairs, "entries": out}


def validate(key: dict, paper: dict) -> list[str]:
    """Cross-check the key against the indexed paper.

    The paper is the authority on how many questions there are and what each is
    worth; the key must cover all of them, and every written question's printed
    markers must sum to the stated mark.
    """
    problems: list[str] = []
    by_number = {e["question"]: e for e in key["entries"]
                 if e["booklet"] == "paper2"}
    questions = {q["question"]: q for q in paper["questions"]}

    missing = [n for n in questions if n not in by_number]
    if missing:
        problems.append(f"no key entry for Q{missing}")

    for number, entry in sorted(by_number.items()):
        if entry.get("table_layout"):
            key.setdefault("notes", []).append(
                f"Q{number}: the model answer is printed as a table and does not "
                f"read in order; compare against the scan")

    for number, question in sorted(questions.items()):
        entry = by_number.get(number)
        if entry is None:
            continue
        chooses = question["response_mode"] == "choose"
        if chooses and entry["option"] is None:
            raw = entry.get("option_raw")
            problems.append(
                f"Q{number}: option unreadable, key shows '{raw}'" if raw
                else f"Q{number}: chosen-answer question has no option in the key")
        if chooses and entry["option"] is not None and question["options"]:
            if not 1 <= entry["option"] <= question["options"]:
                problems.append(f"Q{number}: key option ({entry['option']}) is "
                                f"outside 1-{question['options']}")
        if chooses or entry["option"] is not None:
            continue
        stated = question["marks"]
        if stated is None or entry["marker_total"] == stated:
            continue
        if not entry["markers"] and entry["model_answer"]:
            # 2021 and 2022 print no award markers anywhere -- the publisher
            # introduced them in 2023. A model answer with none at all is that
            # era, not a bad read; a model answer with SOME whose total is wrong
            # is a bad read, and still fails below.
            key.setdefault("notes", []).append(
                f"Q{number}: no mark markers printed; not auto-marked")
            continue
        if question["response_mode"] == "self_marked":
            # Expected, and the reason this question is self-marked: half its
            # marks are holistic 语言 quality with no span to award them against,
            # so the printed markers cannot sum to the stated total.
            key.setdefault("notes", []).append(
                f"Q{number}: markers cover {entry['marker_total']} of {stated} "
                f"marks; the rest is holistic and is not auto-marked")
            continue
        problems.append(
            f"Q{number}: key markers sum to {entry['marker_total']}, "
            f"paper states {stated}")
    return problems


def build_year(year: int, work_dir: Path = WORK_DIR) -> dict:
    questions_path = work_dir / str(year) / "questions.json"
    if not questions_path.exists():
        raise SystemExit(f"no question index for {year}; run build/cn_index.py")
    paper = json.loads(questions_path.read_text())

    key = parse_key(year, work_dir,
                    expected={q["question"] for q in paper["questions"]})
    problems = validate(key, paper)
    key["problems"] = problems
    key["needs_review"] = bool(problems)
    (work_dir / str(year) / "key.json").write_text(
        json.dumps(key, indent=1, ensure_ascii=False))
    return key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args(argv)

    years = args.years or sorted(
        int(p.name) for p in WORK_DIR.iterdir()
        if p.is_dir() and p.name.isdigit())
    failed = False
    for year in years:
        key = build_year(year)
        paper2 = [e for e in key["entries"] if e["booklet"] == "paper2"]
        chosen = [e for e in paper2 if e["option"] is not None]
        written = [e for e in paper2 if e["option"] is None]
        print(f"{year}: {len(chosen)} chosen, {len(written)} written "
              f"(Q{min(e['question'] for e in written)}-"
              f"Q{max(e['question'] for e in written)})")
        for line in key.get("repairs", []):
            print(f"   repair: {line}")
        for line in key.get("notes", []):
            print(f"   note: {line}")
        for line in key["problems"]:
            print(f"   ! {line}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
