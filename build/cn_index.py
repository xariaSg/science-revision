"""Index a PSLE Chinese Paper 2: questions, pages, sections, marks, answer mode.

The paper states its own structure at every level, and that is what makes this
checkable without a human reading it. Every section header carries a question
count and a mark total ("五 阅读理解二（11題32分）"), the two range statements fix
where the MCQ answers stop and the written ones begin, and every written question
prints its own allocation. Nothing here is hardcoded per year; the validator
compares what was found against what the paper says about itself.

Four question layouts, which is the thing to know before reading the parser:

* 语文应用 (Q1-15), 阅读理解一 (Q21-25), A組 (Q30-32) -- blocks, number at the
  left margin, four options beneath.
* 短文填空 (Q16-20) -- a cloze. The number sits INLINE, mid-sentence, with its
  options in parentheses beside it: "帮助大卫 Q16（1 控制 2 管理 ...）了这个困难".
* 完成对话 (Q26-29) -- blanks inside a dialogue, answered from a shared bank of
  numbered phrases printed above it. The bank is longer than four, so these
  questions have more options than the rest; the size is read off the page.
* B組 (Q34-40) plus Q33 -- written answers, no options.

Anchoring on the left margin finds only the first group, which is why questions
are matched anywhere on a line.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ocr_vision import page_lines  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WORK_DIR = REPO / "work-cn"

LANGUAGES = ("zh-Hans", "en-US")

# "一 语文应用（15題30分）" -- count and marks. Both are needed: the count checks
# how many questions were found, the total supplies per-question marks for the
# MCQ sections, which never print their own.
SECTION_COUNTS = re.compile(r"[（(]\s*(\d+)\s*[題题]\s*(\d+)\s*分\s*[）)]")
# Matched on a stem rather than the full name, because the leading character is
# the one that fails: 2017 p16 reads "五 阔读理解二（Q30-Q33，4题10分）", with 阅
# misrecognised as 阔. That one glyph kept the section from ever opening, and
# 完成对话 silently absorbed Q30-Q40 -- the same failure as the bare-header case
# in CLAUDE.md section 7.5, reached a different way. "读理解一" and "读理解二"
# are still distinct from each other and from everything else on the page, so
# dropping the first character loosens nothing that matters.
SECTION_STEMS = {"语文应用": "语文应用", "短文填空": "短文填空",
                 "读理解一": "阅读理解一", "完成对话": "完成对话",
                 "读理解二": "阅读理解二",
                 # A school prelim can drop the numeral outright rather than
                 # mis-OCR it, or wrap it in its own brackets: one 2026 prelim
                 # prints "三 阅读理解（5题10分）" with no "一" anywhere, another
                 # "三阅读理解（一）（5題10分）". Tried after the two explicit
                 # stems above, so a bare "读理解" only ever resolves to
                 # 阅读理解一 when the text does not already say "二".
                 "读理解（一）": "阅读理解一", "读理解（二）": "阅读理解二",
                 "读理解": "阅读理解一",
                 # 对 misread as 时: a 2026 prelim's "四 完成对话（4題8分）"
                 # OCRs as "四 完成时话（4題8分）". With no stem covering it the
                 # section never opened at all, so Q26-28 were silently filed
                 # under 阅读理解一 -- the previous section's name, still set
                 # from before -- rather than flagged as unreadable.
                 "完成时话": "完成对话",
                 # 语 misread as 诗: a 2026 prelim's very first header, "一 语文
                 # 应用（15題30分）", OCRs as "一 诗文应用（15題30分）". With no
                 # section ever recorded, the derived MCQ range (this module,
                 # below) could not sum the first three sections' counts either,
                 # so Q1-Q15 fell back to being counted by their option markers
                 # alone -- and several came back short a marker and were
                 # misclassified as typed questions instead of chosen ones.
                 "诗文应用": "语文应用"}
SECTION_NAME = re.compile("(" + "|".join(SECTION_STEMS) + ")")
# The counts are optional: 2012-2016 print "A组（Q17-Q20）" with a range and
# nothing else, leaving the totals to the parent section header. Requiring them
# meant no group was recorded at all on those years, so every written question
# in 阅读理解二 fell through to the modern era's rules and came back as `choose`
# -- four option buttons under a question that prints ruled answer lines.
GROUP = re.compile(
    r"([AB])\s*[組组]\s*[（(]\s*Q(\d+)\s*[-—–]\s*Q?(\d+)"
    r"(?:\s*[，,]?\s*(\d+)\s*[題题]\s*(\d+)\s*分)?")
QUESTION = re.compile(r"Q\s*(\d+)(?![0-9OZSBGIlD])")
# "Q1—Q2", "（Q21-Q25）" and "A組（Q30-Q33" name ranges in instruction text rather
# than questions. A line joining two numbers that way is furniture.
QUESTION_RANGE = re.compile(r"Q\s*\d+\s*[-—–]\s*Q?\s*\d+")
# A label whose digits did not all survive OCR. 2025 Q17 comes back as "Q1Z",
# which a plain digit match reads as Q1 -- a phantom reference to a question that
# already exists, rather than a visible failure. Hence the lookahead above.
QUESTION_LOOSE = re.compile(r"Q\s*([0-9OZSBGIlD]{1,2})(?![0-9])")
# The "Q" itself can misread as a bare digit -- rather than one of the digits
# *inside* a "Q..." match, which is all CONFUSABLE repairs elsewhere in this
# module. A 2026 prelim's "Q18" and "Q19" both come back as "918"/"919" inline
# in a cloze passage, and another's "Q17" as "017". Scoped to a token
# immediately followed by an option opener ("（1" through "（4"), because that
# is the one place in this layout a bare number can appear that always means
# a damaged question label, never a date, a price, or any other digit run in
# the surrounding prose.
QUESTION_DAMAGED = re.compile(r"(?<![0-9])[9O0](\d{1,2})(?=\s*[（(]\s*[1-4])")
MARKS = re.compile(r"[（(]\s*(\d+)\s*分\s*[）)]")
WRITTEN_FROM = re.compile(r"从第\s*(\d+)\s*[題题]到第\s*(\d+)\s*[題题].{0,12}写在作答簿")
MCQ_RANGE = re.compile(r"从第\s*(\d+)\s*[題题]到第\s*(\d+)\s*[題题].{0,60}电脑作答卷")
# A line in the 完成对话 answer bank: a number, then the phrase. Three forms
# across the corpus -- bare on 2017-2025 ("1 我们都很开心"), parenthesised on
# 2012 ("（1）你放心好了"), and dotted on 2013-2016 ("1. 太没有爱心了", and
# without even a space in "7.巴士在繁忙时间挤满了搭客"). Reading only the bare
# form left the bank size unknown on five years, and the fallback assumed four
# entries where the paper prints eight -- half the bank invisible to a child who
# has to choose from it. The bare form's own spacing is not reliable either --
# a 2026 prelim reads seven of its eight entries with a space and the eighth,
# "7他们知道了又怎么样", with none at all -- so the space after a bare number
# is optional. Nothing is lost by that: the page number sitting alone at the
# top of the page still cannot match, since there is no \S left on the line
# for the trailing requirement to consume.
#
# The bare form is capped at a single digit 1-9 -- every bank in the corpus
# tops out at eight entries (CLAUDE.md section 7.3) -- because a school
# prelim's Q28 once lost its "Q" outright, OCRing as bare "928" on a page
# whose current section genuinely is the answer bank. Uncapped, that satisfies
# this same alternative and is captured as bank entry 92; `max(entries)` then
# treats it as the bank's own size and reports every number below it as
# "missing", drowning the real, useful "Q28 is missing" signal in a
# manufactured one.
BANK_ENTRY = re.compile(r"^(?:[（(]\s*(\d+)\s*[）)]|(\d+)\s*[.．、]|([1-9])\s*)\s*\S")
# An option marker beneath a question: "（1）", "(2)".
OPTION = re.compile(r"[（(]\s*([1-4])\s*[）)]")
# The opening bracket, not a digit inside it, is what a school prelim's option
# line drops -- "（2）邀请居民们参加屋顶农场讲座" comes back "12） 邀请...",
# "（4）到民众俱乐部..." comes back "14）...", and "（1）能够加强..." comes
# back "（1.）能够加强...", each losing (or gaining) a different character
# right around the bracket. What survives every time is the option digit
# immediately before the closing bracket, optionally through a stray leading
# digit or a stray period -- so that is all this checks for, scoped to
# where OPTION itself found too few. It never matches a mark allocation
# ("2分）") because a Chinese character, not the bracket, follows that digit.
OPTION_LOOSE = re.compile(r"([1-4])[.．]?\s*[）)]")
# Booklet B's cover, in 2012-2020 where Paper 2 is two physical booklets. It is
# printed in English and reads perfectly at 300 dpi, which makes it a better
# anchor than anything Chinese on the page.
BOOKLET_B_COVER = re.compile(r"BOOKLET\s*\(?\s*B", re.IGNORECASE)
CHINESE_PAPER_2 = re.compile(r"CHINESE\s+PAPER\s+2", re.IGNORECASE)

# Glyphs Vision confuses for digits in this typeface. Used ONLY to confirm a
# number the contiguous sequence has already predicted -- never to discover one.
# Used the other way round it would invent question numbers freely.
CONFUSABLE = {"O": "0", "D": "0", "I": "1", "l": "1", "Z": "7",
              "S": "5", "B": "8", "G": "6"}

DEFAULT_OPTIONS = 4
CLOZE_SECTION = "短文填空"
BANK_SECTION = "完成对话"

# How each question is answered. Q1-Q32 are chosen from options and marked against
# the key. Q34-Q40 are typed -- spoken Chinese cannot distinguish 熟悉 from its
# homophones, and those marks depend on the exact characters. Q33 is a writing
# task whose marks are half holistic 语言 quality, which the printed rubric does
# not decompose, so it is shown with its model answer and self-marked.
MODE_CHOOSE = "choose"
MODE_TYPED = "typed"
MODE_SELF_MARKED = "self_marked"

READING_TWO = "阅读理解二"


def _as_number(raw: str) -> int | None:
    digits = "".join(CONFUSABLE.get(ch, ch) for ch in raw)
    return int(digits) if digits.isdigit() else None


@dataclass
class Question:
    number: int
    page: int
    section: str | None = None
    group: str | None = None
    marks: int | None = None
    marks_source: str = ""
    options: int | None = None
    response_mode: str = MODE_CHOOSE
    tops: list[int] = field(default_factory=list)


def paper_pages(year: int, work_dir: Path = WORK_DIR):
    pages_dir = work_dir / str(year) / "pages"
    if not pages_dir.exists():
        raise SystemExit(f"no unpacked pages for {year}; run build/cn_unpack.py")
    for image in sorted(pages_dir.glob("page-*.png")):
        yield int(image.stem.split("-")[1]), page_lines(image, languages=LANGUAGES)


def index_paper(year: int, work_dir: Path = WORK_DIR) -> dict:
    questions: dict[int, Question] = {}
    sections: list[dict] = []
    groups: list[dict] = []
    garbled: list[dict] = []
    loose_marks: list[dict] = []
    bank_entries: dict[int, set[int]] = {}
    repairs: list[str] = []
    warnings: list[str] = []
    mcq_range = written_range = None
    section = group = None
    current = None
    booklet_b_page: int | None = None
    page_lines_by_number: dict[int, list] = {}

    for page, lines in paper_pages(year, work_dir):
        page_lines_by_number[page] = lines
        # The range statements wrap across OCR lines ("...请选出答案（1，" then
        # "2，3或4），然后把电脑作答卷"), so match them against the whole page.
        joined = "".join(line.text.strip() for line in lines)
        if m := MCQ_RANGE.search(joined):
            mcq_range = (int(m.group(1)), int(m.group(2)))
        if m := WRITTEN_FROM.search(joined):
            written_range = (int(m.group(1)), int(m.group(2)))
        # 2012-2020 split Paper 2 into two physical booklets: A is answered on
        # the OAS, B is written in the booklet itself. Neither booklet prints the
        # 电脑作答卷 / 写在作答簿 sentences that fix those ranges on 2021-2025 --
        # Booklet B just says "Write all your answers in this booklet", in
        # English -- so the cover is where that boundary is stated.
        if booklet_b_page is None and CHINESE_PAPER_2.search(joined) \
                and BOOKLET_B_COVER.search(joined):
            booklet_b_page = page

        for line in lines:
            text = line.text.strip()

            if m := GROUP.search(text):
                group = m.group(1)
                groups.append({"group": group, "page": page, "section": section,
                               "start": int(m.group(2)), "end": int(m.group(3)),
                               "count": int(m.group(4)) if m.group(4) else None,
                               "marks": int(m.group(5)) if m.group(5) else None})
                continue

            name, counts = SECTION_NAME.search(text), SECTION_COUNTS.search(text)
            # 2021-2023 print the 阅读理解二 header bare -- "五阅读理解二", with no
            # "（11題32分）" after it. Only 2024-2025 state the parent total; the
            # earlier papers leave it to the A組/B組 sub-headers, which carry their
            # own counts. Requiring both meant the section never opened on those
            # years and 完成对话 silently swallowed the remaining fifteen
            # questions.
            #
            # A section name alone is not a header -- a passage may mention one.
            # What marks the line as a header is that it also states the
            # section's shape: a count and total, or the range it covers. Only
            # when it states neither does the geometry have to decide, and the
            # length guard is for that case alone. 2017 needed the range arm:
            # "五 阅读理解二（Q30-Q33，4题10分）" is 22 characters, just over a
            # limit that had only ever seen the bare "五 阅读理解二".
            scoped = bool(QUESTION_RANGE.search(text))
            looks_like_header = counts or scoped or (line.left < 800
                                                     and len(text) <= 20)
            if name and looks_like_header:
                section, group = SECTION_STEMS[name.group(1)], None
                # 2017 restates A組's range and totals on the parent header --
                # "五 阅读理解二（Q30-Q33，4题10分）" describes four of the
                # section's eleven questions. Taking that as the section's own
                # count fails validation against a paper that is not wrong. A
                # header that names a range is describing that range, so the
                # section opens without a count and the A組/B組 headers supply
                # the totals instead.
                sections.append({
                    "section": section, "page": page,
                    "count": int(counts.group(1)) if counts and not scoped else None,
                    "marks": int(counts.group(2)) if counts and not scoped else None,
                })
                continue

            if section == BANK_SECTION and (m := BANK_ENTRY.match(text)):
                entry = next(g for g in m.groups() if g is not None)
                bank_entries.setdefault(page, set()).add(int(entry))

            if QUESTION_RANGE.search(text):
                continue

            exact = QUESTION.findall(text)
            for raw in exact:
                number = int(raw)
                current = questions.setdefault(
                    number, Question(number=number, page=page,
                                     section=section, group=group))
                # A number that resurfaces on a LATER page -- a school prelim's
                # "作答簿" reprints the written questions' bare numbers a second
                # time for the student to write beside -- must not add a `top`
                # here. `_count_options` bands by `min(q.tops)` on `q.page`
                # alone; a reprint page's coordinate is unrelated to the
                # original page's geometry, and picking it up once turned
                # TaoNan's Q33 -- a writing task -- into a false 4-option
                # "choose" question, because the reprint page's own Q30-32
                # placeholders sit at a `top` smaller than anything on Q33's
                # real page.
                if page == current.page:
                    current.tops.append(line.top)

            # Hold damaged labels; they are resolved by position once the sequence
            # is known, never by guessing at the glyphs.
            if not exact:
                for raw in QUESTION_LOOSE.findall(text):
                    if not raw.isdigit():
                        garbled.append({"page": page, "top": line.top, "raw": raw,
                                        "section": section, "group": group})
                for raw in QUESTION_DAMAGED.findall(text):
                    garbled.append({"page": page, "top": line.top, "raw": raw,
                                    "section": section, "group": group})

            marks = MARKS.findall(text)
            if not marks:
                continue
            total = sum(int(v) for v in marks)
            if exact:
                current.marks = total
                current.marks_source = "printed"
            else:
                # A bare "（2分）" on its own line. 2024 prints Q30's ABOVE the
                # question, and Q36/Q39 state one allocation per sub-part so the
                # second wraps onto its own line. Attaching either to whatever was
                # last seen credits the wrong question -- defer and place by
                # vertical position instead.
                loose_marks.append({"page": page, "top": line.top, "marks": total})

    for entry in loose_marks:
        same_page = [q for q in questions.values() if q.page == entry["page"]]
        if not same_page:
            warnings.append(f"[{entry['marks']}] on p{entry['page']} matched no question")
            continue
        nearest = min(same_page, key=lambda q: min(
            (abs(entry["top"] - t) for t in q.tops), default=10 ** 9))
        nearest.marks = (nearest.marks or 0) + entry["marks"]
        nearest.marks_source = "printed nearby"
        repairs.append(f"Q{nearest.number}: took [{entry['marks']}] from a bare "
                       f"marks line on p{entry['page']}")

    # Where the paper does not state its own ranges, they are recovered from the
    # structure it does state: the booklet boundary for where chosen answers
    # stop, and the group headers' own end for where the questions run out. Both
    # are printed facts, not inferences from what happened to be found -- an end
    # taken from "the highest number seen" would move when a question was missed,
    # which is the failure that leaves no gap to notice (CLAUDE.md 1.6.1).
    if mcq_range is None and booklet_b_page is not None:
        before = [q.number for q in questions.values() if q.page < booklet_b_page]
        if before:
            mcq_range = (min(before), max(before))
            repairs.append(f"MCQ range Q{mcq_range[0]}-Q{mcq_range[1]} taken from "
                           f"Booklet B's cover on p{booklet_b_page}")
    if mcq_range is None:
        # A school prelim can omit the "从第1题到第25题...电脑作答卷" sentence
        # entirely rather than mis-OCR it -- several 2026 prelims print nothing
        # of the kind anywhere on the cover. The first three sections always
        # state their own count regardless, so their sum states the same fact
        # a different way.
        MCQ_SECTIONS = ("语文应用", "短文填空", "阅读理解一")
        counted = [s["count"] for name in MCQ_SECTIONS for s in sections
                  if s["section"] == name and s["count"]]
        if len(counted) == len(MCQ_SECTIONS):
            mcq_range = (1, sum(counted))
            repairs.append(f"MCQ range Q1-Q{mcq_range[1]} derived from the "
                           f"first three sections' own stated counts")
    if written_range is None and mcq_range:
        # A group's own range can be as damaged as its digits get ("Q3-933"
        # for "Q30-Q33") while its count survives intact -- the same failure
        # `validate` refuses to walk. Taking the highest such `end` here would
        # feed the same garbage into the written range, so a group is only a
        # candidate when its range and count agree.
        stated_end = max((g["end"] for g in groups
                          if g["count"] is None
                          or g["end"] - g["start"] + 1 == g["count"]), default=None)
        counted = sum(s["count"] for s in sections if s["count"])
        end = stated_end
        if end is None and counted and all(s["count"] for s in sections):
            end = counted
        if end is not None and end <= mcq_range[1]:
            # `sections` held only the MCQ ones -- the paper's written pages
            # were never found at all (2026 AiTong's Paper 2 scan stops after
            # the MCQ section, though its own answer key covers Q26-Q40), so
            # `counted` summed to the MCQ range's own end and "derived" a
            # written range that runs backwards. Nothing genuine to derive
            # from beats a range that does not make sense.
            end = None
        if end is None:
            warnings.append("no stated end for the written range; the last "
                            "question is unchecked")
        else:
            written_range = (mcq_range[1] + 1, end)
            repairs.append(f"written range Q{written_range[0]}-Q{written_range[1]} "
                           f"derived from the booklet split and the group headers")

    # Numbering is contiguous and both ends are stated, so a missing number is
    # never in doubt -- only which damaged label belongs to it. A paper whose
    # written section could not even be found at all (2026 AiTong's Paper 2
    # scan stops after the MCQ section) still has a real, known end for the
    # part that IS there, so recovery within the MCQ range should not wait on
    # a written range that may never come.
    recovery_end = written_range[1] if written_range else (
        mcq_range[1] if mcq_range else None)
    if mcq_range and recovery_end is not None:
        for number in range(mcq_range[0], recovery_end + 1):
            if number in questions:
                continue
            before, after = questions.get(number - 1), questions.get(number + 1)
            for cand in list(garbled):
                if _as_number(cand["raw"]) != number:
                    continue
                if before and (cand["page"], cand["top"]) < (before.page, before.tops[0]):
                    continue
                if after and (cand["page"], cand["top"]) > (after.page, after.tops[0]):
                    continue
                questions[number] = Question(
                    number=number, page=cand["page"], section=cand["section"],
                    group=cand["group"], tops=[cand["top"]])
                repairs.append(
                    f"Q{number}: read from '{cand['raw']}' on p{cand['page']}, "
                    f"placed between Q{number - 1} and Q{number + 1}")
                garbled.remove(cand)
                break

    # MCQ marks are never printed per question; the section states count and total.
    for entry in sections:
        if not entry["count"] or entry["marks"] is None:
            continue
        per = entry["marks"] / entry["count"]
        for q in questions.values():
            if q.section == entry["section"] and q.marks is None and per.is_integer():
                q.marks = int(per)
                q.marks_source = "section total / count"

    # The bank is numbered from 1 with no gaps, so its size is its highest entry
    # only when everything below that was also read. Trusting the maximum alone
    # would let one stray number set the size and leave the child choosing from
    # a bank the paper never printed.
    bank_sizes: dict[int, int] = {}
    for page, entries in bank_entries.items():
        top = max(entries)
        if entries == set(range(1, top + 1)):
            bank_sizes[page] = top
        else:
            missing = sorted(set(range(1, top + 1)) - entries)
            warnings.append(f"answer bank on p{page} is missing entries "
                            f"{missing}; size not taken from it")

    option_counts = _count_options(questions, page_lines_by_number)
    for q in questions.values():
        q.response_mode, q.options = _mode_for(
            q, mcq_range, bank_sizes, option_counts, warnings)

    return {
        "year": year,
        "subject": "chinese",
        "paper": "2",
        "num_pages": len(list((work_dir / str(year) / "pages").glob("page-*.png"))),
        "mcq_range": list(mcq_range) if mcq_range else None,
        "written_range": list(written_range) if written_range else None,
        "sections": sections,
        "groups": groups,
        "repairs": repairs,
        "unresolved": [{k: v for k, v in g.items() if k != "top"} for g in garbled],
        "warnings": warnings,
        "questions": [
            {"question": q.number, "page": q.page, "section": q.section,
             "group": q.group, "marks": q.marks, "marks_source": q.marks_source,
             "options": q.options, "response_mode": q.response_mode}
            for q in sorted(questions.values(), key=lambda q: q.number)
        ],
    }


def _count_options(questions: dict[int, Question],
                   page_lines: dict[int, list]) -> dict[int, int]:
    """How many distinct option markers each question prints beneath itself.

    This is the one thing that separates the eras past the OAS boundary, and it
    has to be measured rather than assumed. 2017-2025 print three more option
    questions after it (阅读理解二 A組 Q30-Q32, four options each); 2012-2016
    print none at all -- their whole 阅读理解二 is ruled answer lines and a 得分
    box. Read off the page the split is unambiguous: those questions come back
    with exactly {1,2,3,4} and every written question with nothing.
    """
    counts: dict[int, int] = {}
    for q in questions.values():
        lines = page_lines.get(q.page, [])
        if not q.tops:
            continue
        top = min(q.tops)
        # The band runs to the next question's anchor on the same page; a
        # question that is last on its page owns the rest of it.
        later = [t for other in questions.values() if other.page == q.page
                 for t in other.tops if t > top]
        bottom = min(later) if later else float("inf")
        seen = set()
        for line in lines:
            if top - 20 <= line.top < bottom:
                seen |= {m.group(1) for m in OPTION.finditer(line.text)}
        if len(seen) < DEFAULT_OPTIONS:
            # The strict read came up short -- try the same band again,
            # allowing a digit whose opening bracket did not survive OCR.
            for line in lines:
                if top - 20 <= line.top < bottom:
                    seen |= {m.group(1) for m in OPTION_LOOSE.finditer(line.text)}
        counts[q.number] = len(seen)
    return counts


def _mode_for(q: Question, mcq_range, bank_sizes: dict[int, int],
              option_counts: dict[int, int],
              warnings: list[str]) -> tuple[str, int | None]:
    # 完成对话 is chosen from a shared bank whichever booklet prints it, so it is
    # settled before the OAS boundary is consulted.
    if q.section == BANK_SECTION:
        size = bank_sizes.get(q.page) or max(bank_sizes.values(), default=0)
        if not size:
            warnings.append(f"Q{q.number}: answer bank size not read; assuming "
                            f"{DEFAULT_OPTIONS}")
            size = DEFAULT_OPTIONS
        return MODE_CHOOSE, size
    # Everything up to the OAS boundary is a four-option question in every year
    # of the corpus.
    if mcq_range and q.number <= mcq_range[1]:
        return MODE_CHOOSE, DEFAULT_OPTIONS
    if option_counts.get(q.number, 0) >= DEFAULT_OPTIONS:
        return MODE_CHOOSE, DEFAULT_OPTIONS
    if q.section == READING_TWO and q.group != "B" and q.marks == 4:
        # The writing task -- Q33 on 2017-2025. Half its marks are for 语言
        # quality, which the printed rubric does not decompose, so it is shown
        # with the model answer and self-marked (CLAUDE.md section 7.4).
        return MODE_SELF_MARKED, None
    return MODE_TYPED, None


def validate(paper: dict) -> list[str]:
    """Check what was found against what the paper says about itself."""
    problems: list[str] = []
    questions = {q["question"]: q for q in paper["questions"]}

    for entry in paper["sections"]:
        if entry["count"] is None:
            continue
        got = [q for q in paper["questions"] if q["section"] == entry["section"]]
        if len(got) != entry["count"]:
            problems.append(f"{entry['section']}: found {len(got)} questions, "
                            f"header states {entry['count']}")
        total = sum(q["marks"] or 0 for q in got)
        if total != entry["marks"]:
            problems.append(f"{entry['section']}: marks sum to {total}, header "
                            f"states {entry['marks']}")

    for entry in paper["groups"]:
        wanted = range(entry["start"], entry["end"] + 1)
        # The header states a range and a count together ("A组（Q30-Q33，4题
        #10分）"), and the two are independent OCR reads of the same fact --
        # a school prelim once misread that whole run as "A组（Q3-933,4題
        # 10分）", count intact, range destroyed. A range that disagrees with
        # its own stated count cannot be walked for missing questions without
        # inventing hundreds of them, so it is reported and skipped rather
        # than trusted -- the same "refuse rather than guess" rule CLAUDE.md
        # section 1.6.1 applies to a single digit applies here to a whole run.
        if entry["count"] is not None and len(wanted) != entry["count"]:
            problems.append(
                f"{entry['group']}組: header range Q{entry['start']}-"
                f"Q{entry['end']} does not match its own stated count "
                f"({entry['count']}); range not checked")
            continue
        missing = [n for n in wanted if n not in questions]
        if missing:
            problems.append(f"{entry['group']}組: missing Q{missing}")
        # 2012-2016 print the group headers as a bare range, leaving the totals
        # to the parent section. There is nothing to check them against.
        if entry["marks"] is None:
            continue
        total = sum(questions[n]["marks"] or 0 for n in wanted if n in questions)
        if total != entry["marks"]:
            problems.append(f"{entry['group']}組: marks sum to {total}, header "
                            f"states {entry['marks']}")

    complete = False
    if paper["mcq_range"] and paper["written_range"]:
        lo, hi = paper["mcq_range"][0], paper["written_range"][1]
        gaps = [n for n in range(lo, hi + 1) if n not in questions]
        if gaps:
            problems.append(f"missing questions {gaps}")
        complete = not gaps
    else:
        problems.append("could not read the paper's own question ranges")

    # A damaged label matters only while a question is still missing. 完成对话
    # prints each number twice -- once inline in the dialogue and once in the
    # answer column beside it -- and it is the inline copy that gets clipped
    # ("妈妈告诉过我，Q2Z。"). The column copy reads cleanly, so the question is
    # already indexed and the leftover is the same number a second time, not a
    # discovery. With the numbering complete there is nothing for it to be.
    if not complete:
        for entry in paper["unresolved"]:
            problems.append(
                f"unplaced damaged label '{entry['raw']}' on p{entry['page']}")
    return problems


def index_year(year: int, work_dir: Path = WORK_DIR) -> dict:
    paper = index_paper(year, work_dir)
    problems = validate(paper)
    paper["problems"] = problems
    paper["needs_review"] = bool(problems)
    (work_dir / str(year) / "questions.json").write_text(
        json.dumps(paper, indent=1, ensure_ascii=False))
    return paper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args(argv)

    years = args.years or sorted(
        int(p.name) for p in WORK_DIR.iterdir()
        if p.is_dir() and p.name.isdigit())
    failed = False
    for year in years:
        paper = index_year(year)
        counts = {}
        for q in paper["questions"]:
            counts[q["response_mode"]] = counts.get(q["response_mode"], 0) + 1
        modes = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        total = sum(q["marks"] or 0 for q in paper["questions"])
        print(f"{year}: {len(paper['questions'])} questions, {total} marks "
              f"({modes})")
        for line in paper["repairs"]:
            print(f"   repair: {line}")
        for line in paper["warnings"]:
            print(f"   warning: {line}")
        for line in paper["problems"]:
            print(f"   ! {line}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
