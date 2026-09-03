# PSLE Practice App

Local-only web app. A Primary 6 student is shown a real PSLE paper as its original
scan, answers it, and receives a mark plus specific feedback on what was missed and
how to fix it.

Single user (one child), runs on localhost, never deployed.

Two subjects, and they are less alike than they look:

| | Science | Chinese |
|---|---|---|
| Papers | Booklet A (MCQ) and Booklet B (open-ended), practised separately | Paper 2, loaded whole (both booklets where the year has two, §7.5) |
| Answering | spoken, transcribed locally | typed and chosen — never spoken, see §7.6 |
| Marking | chains of cause and effect, authored by hand (§3) | keypoints the publisher printed (§7.4) |
| Years built | 2012–2025 | 2012–2025 |

**Sections 1–6 are Science. Section 7 is Chinese.** The numbering is load-bearing:
code comments cite these sections by number, so nothing here may be renumbered.
Anything general enough to cover both subjects — the copyright constraint (§2.1),
the offline-degradation rule (§2.2), the child-facing tone (§2.3) — lives in §2 and
applies to both.

---

## 1. Science: verified findings about the source files

These were confirmed by direct inspection. Do not re-derive them, but **do** verify any
claim marked UNVERIFIED before relying on it.

### 1.1 The files are real PDFs containing page scans

**Corrected 2026-08-06 during Phase 0.** An earlier version of this document stated the
files were ZIP archives of `N.jpeg` / `N.txt` / `manifest.json` and that PDF tooling was
useless on them. That is wrong. All 14 files begin with `%PDF` and open normally in
PyMuPDF. (The ZIP-of-JPEGs description matches an intermediate form produced by a
file-reading tool, not the files on disk.)

Each is a scanned PDF: A4 pages, one full-page raster per page, no vector text.

- Resolution is **200–300 DPI**, not 924×1316. Embedded rasters run 1654×2338 (2024),
  ~2050×3200 (2025), up to 2488×3504 (2015–2017). Mostly grayscale.
- 2012–2014 are the lowest quality at 1683×1190 — landscape-ish and noticeably coarser.
- Most papers hold exactly one image per page. **2020 and 2023 do not** — they split
  pages across many image XObjects (2020 has 570 images over 40 pages). Render the
  composed page; do not assume one image per page.

Read them with PyMuPDF (`fitz`). `build/unpack.py` renders every page to PNG at a fixed
300 DPI, which also gives all papers a single coordinate space for segmentation.

**Five papers ship an embedded OCR text layer** — a better source than re-OCRing, and
worth checking before Phase 5 backfill:

| Paper | Text layer | Note |
|---|---|---|
| 2015, 2017, 2018, 2019 | 40–53k chars | clean, usable |
| 2016 | 55k chars | **garbled** — reads as mirrored/rotated text, do not trust |
| 2023 | 9.5k chars | partial only |
| 2012–2014, 2020–2022, 2024, 2025 | none | pure scans, OCR required |

Both Phase 0 target papers (2024, 2025) have no text layer, so OCR is required there
regardless.

### 1.2 Page counts vary by year

| Year | Pages | Year | Pages |
|---|---|---|---|
| 2012 | 49 | 2019 | 43 |
| 2013 | 45 | 2020 | 40 |
| 2014 | 49 | 2021 | 34 |
| 2015 | 53 | 2022 | 33 |
| 2016 | 52 | 2023 | 37 |
| 2017 | 43 | 2024 | 34 |
| 2018 | 46 | 2025 | 34 |

Note the extensions are inconsistent: 2015–2019 use uppercase `.PDF`, the rest lowercase.
Glob case-insensitively.

**Booklet boundaries must be detected per paper. Never hardcode them.**

### 1.3 Structure, verified for 2024 and 2025 only

| Pages | Contents |
|---|---|
| 1–16 | Booklet A |
| 17–28 | Booklet B |
| 29–34 | Answers |

Confirmed automatically by `build/detect_boundaries.py`, at `high` confidence on both
papers with all cross-checks passing, and confirmed by eye on the contact sheets.

**Do not anchor on the Booklet A cover's stated page count.** It is not a page range:
2024 states "16 printed pages" for a 16-page booklet, but 2025 states "15 printed pages
and 1 blank page" for one equally 16 pages long — its p16 is a `BLANK PAGE`. Trailing
blanks are inside the booklet and counted separately, or not at all.

The anchors that actually hold, in order of trust:

1. **The Booklet B cover** — the only page carrying "PASTE YOUR BARCODE LABEL HERE", and
   its footer's "consists of 12 printed pages" OCRs cleanly on both papers. This gives
   Booklet B's start and length.
2. **Booklet A = page 1 to the page before that cover.** Derived, never read off the
   A cover.
3. **Per-page paper codes** — Booklet A pages footer `0009/02(A)`, Booklet B pages
   `0009/2B`. An independent per-page vote, good as a cross-check.
4. **`(Go on to Booklet B)`** appears in the footer of the last content page of A.
5. **Answer pages** are headed `PSLE Yearly Science – Answers` / footed with the EPH
   copyright line.

One parsing trap, hit and fixed: the A cover's own sentence "...and 1 blank page" will
mark the cover itself as a blank page unless `BLANK PAGE` is matched as a standalone
line.

Boundaries for 2012–2023 are **UNVERIFIED**. Given the page-count spread (33–53), the
older papers almost certainly differ. Detect, then have a human confirm.

### 1.4 Booklet B question format

- Question numbering **continues from Booklet A**. In the 2024 paper, Booklet B contains
  questions numbered from roughly Q29 upward (Q31–Q34 confirmed by sight). Booklet B
  questions do not restart at 1.
- Sub-parts use `(a)`, `(b)`, `(c)` and nested `(i)`, `(ii)`.
- Mark allocation appears right-aligned in square brackets: `[1]`, `[2]`.
- Questions are **visually dense**. 2024 Q34 alone carries a three-column data table, a
  bar chart with a legend, and three sub-parts. Text transcription alone destroys the
  question — the app must display the original scan.

### 1.5 Booklet A question format

**Verified across all 14 papers** by `build/index_mcq.py`, which now indexes every one
of them completely (28 questions on 2017–2025, 30 on 2012–2016).

Layout is single-column and uniform across both eras:

```
For each question from 1 to 28, four options are given. One of them is the correct answer.
                                                                          (56 marks)
1   Which is a characteristic of all living things?     <- number, left margin
      (1) They can reproduce.                           <- options, one indent in
```

- **The range statement is the anchor.** `For each question from N to M` appears on the
  first question page, worded identically on every paper. It fixes the numbering *and*
  separates real questions from the cover's own numbered instructions ("1. Write your
  Index No..."), which are otherwise indistinguishable left-margin numbers.
- Every question is worth **2 marks** — the stated total divided by the question count
  comes out exactly on all 14 papers. There are no sub-parts and no partial credit.
- Options are `(1)`–`(4)` and are sometimes **pictures**: 2012 Q1's four options are
  drawings of birds' heads, 2015 Q12's are diagrams of a germinating seed. Retyping
  options into the app is therefore not an option — same conclusion as Booklet B, for
  the same reason.
- Question numbers run **1..N with no gaps**, which is what makes the recovery in
  §1.5.1 safe.

#### 1.5.1 Both OCR engines drop question numbers, and they drop different ones

The single biggest surprise of this pass. Vision loses 2025's "10" and "11" entirely
while tesseract reads both; tesseract reads 2025 Q19's "19" as "49". Neither alone
indexes a paper completely — together with three recovery tiers, all 14 index fully:

1. **Union of both readers.** Vision returns the number joined to the question text;
   tesseract returns it as a standalone left-margin token. Where they disagree about a
   row, Vision wins — it read the number in context rather than alone.
2. **Position, ignoring the digits.** Since numbering is dense and the range is stated,
   a missing question's *number* is never in doubt — only where it starts. A left-margin
   number of any value, alone in the band between its two neighbours, settles it. This
   is what recovers 2025 Q19 from a token that reads "49".
3. **The option block.** 2017 Q4 and 2024 Q4 lose their number so completely that the
   question's first row starts at the body indent with nothing to its left. Every MCQ
   has options (1)–(4), so the row after the previous question's fourth option is the
   next question's first. Take the **first** complete run in the band, not the last —
   the missing question has options of its own further down, and on 2024 they are
   labels on a diagram.

Two traps in tier 3, both hit: page furniture (footer, then the next page's number)
sits between the last option and the next question, and must be stepped over; and when
the next question is overleaf it owns that page **from the top**, because its own first
row is often unreadable (2015 Q12 and 2021 Q27 are near-solid diagrams whose stem Vision
never returns). Anchoring on the first readable row instead left the page looking as
though it belonged to the question before.

### 1.6 The answer pages

Headed `PSLE Yearly Science – Answers`, footed `© Educational Publishing House Pte Ltd`.

**These are a commercial publisher's suggested answers, not the official SEAB marking
scheme.** Treat them as well-informed but not authoritative. Surface this in the UI.

Format is consistent and useful — each answer has two parts:

1. The model answer itself.
2. An underlined `Explanation:` block giving the underlying scientific principle.

Keep these as separate fields. The model answer drives marking; the Explanation drives
teaching, and should be revealed after the mark, not with it.

Answer-page internal pagination appears to belong to a multi-year compilation (the 2025
answers begin on a page numbered 8). Do not rely on printed page numbers for indexing;
use the archive's own image ordering.

**Layout, verified for 2024 and 2025.** Booklet B's answers do not start on a page
boundary — a page range is not enough to find them. On 2024 they begin partway down
p31's *right* column, directly under a `Booklet B` header, while the left column of that
same page is still finishing Booklet A's MCQ answers. `build/segment_answers.py` handles
this; the properties it relies on:

- Two columns, left read fully before right. The gutter can be as narrow as **5px** at
  300 dpi (2025 p33), and a page number printed inside it will hide it completely.
- Indentation encodes role within a column: question numbers at the left edge, sub-part
  labels one indent in, body text further right. This is what keys an answer to its
  sub-part.
- Tesseract's block ordering **cannot** be trusted here — it merges lines across the
  gutter, producing blocks like "Chemical potential energy in the 29. (a) Roots absorb
  water..." Work from word boxes and assign columns yourself.
- The dotted rule between columns OCRs as isolated `:` `|` `;` `}` and lands *left* of
  the right column's question numbers. Strip it before measuring any geometry.
- Booklet B's first page states its own range ("For questions 29 to 40"). Parse it and
  use it to check answer coverage, rather than assuming Q29–Q40.

**Segmentation is not fully reliable and is not expected to be.** 2024 segments to 12/12
questions; 2025 to 9/12. Q31, Q35 and Q39 fail because tesseract never emits those
number glyphs at any confidence — an OCR dropout, not a geometry bug, so no amount of
tuning recovers them. When a question number is dropped its sub-parts are silently
absorbed by the previous question, which is the most dangerous failure this pipeline
has; it is detected by watching for sub-part labels running backwards
(`a, b, ... a`) and reported. **Treat the OCR text as a draft for review only** — it
contains real errors ("predotors", `Explanation:` clipped to `ion:`). Authoritative text
must come from the vision pass, per plan §1b.

#### 1.6.1 The Booklet A answer key

The MCQ answers sit in the **left column of the same pages**, before Booklet B's, in the
form `1. (3)` followed by an `Explanation:` block. `build/extract_mcq_key.py` reads all
14 papers completely — every question, cross-checked against the booklet's own count.

Two era differences, both handled: 2012–2014 print `2012 Booklet A` on one line (later
papers split the year and the booklet onto two) and use bullet points where later papers
use an `Explanation:` heading. The 2012–2014 papers also run the first line of the
explanation onto the marker's own row, so text after the marker must be kept — dropping
the row wholesale lost the opening line of 2012 Q1's explanation.

**A misread digit here is worse than a misread anything in Booklet B.** There is no
partial credit to soften it: the child is simply told they were wrong when they were
right. So the extractor is built to refuse rather than to guess, and every reconstructed
answer is tagged `answer_source` and surfaced in the UI as such.

Nine markers across the corpus are dropped by Vision at page scale (2020 alone loses
four). They are recovered by re-reading the band between the neighbouring answers, and
the recovered digit is accepted **only when two independent readers agree**: Vision on a
3× crop of the band locates the option, then tesseract re-reads that one row with
`--psm 7` and must report both the same option digit *and* the question number the
sequence predicts. All 13 reconstructions were then checked by eye against the scans and
all 13 are correct.

Four things that broke this and are worth not rediscovering:

- **Crop from the previous marker's own row, not from the end of its text.** When a
  marker is dropped, its explanation is absorbed by the question before, so that entry's
  text now runs *past* the very line being searched for.
- **Confirm by searching, not matching.** A single-row crop picks up debris from the
  dotted rule beside it — 2018 Q21 comes back from `--psm 7` as `oe 2 21. (1)`.
- **Clamp the confirming crop to its column.** Reaching left for the question number
  otherwise pulls in the neighbouring column and hides the marker.
- **Allow confusable glyphs when testing a predicted number.** 2020's smudged `10.`
  reads as `1D.`. Safe only because it answers yes/no about a number the sequence has
  already fixed; used to *discover* numbers it would invent them freely.

A key that is short at the **end** leaves no gap in the sequence to notice — 2021 loses
Q28 silently. Only the Booklet A inventory's question count reveals it, which is why
`build/index_mcq.py` must run before `build/extract_mcq_key.py`.

---

## 2. Hard constraints

### 2.1 Copyright — local only

Question papers are © MOE / SEAB. Answers are © Educational Publishing House.
Building a personal study tool from materials already owned is a different thing from
redistribution.

- The generated content bundle is **never** committed to a public repo, published, or
  shared.
- Add the papers directory and the built bundle to `.gitignore` from the first commit.
- Display original scan crops rather than re-typing question text into project files.
  This is both better pedagogy (diagrams survive) and the cleaner position.

### 2.2 No network dependency for core loop

Speech-to-text runs locally. The only outbound call is to the Anthropic API for grading.
The app must degrade gracefully — if grading is unavailable, the student can still
practise, self-check against the model answer, and log the attempt.

### 2.3 Child-facing tone

The user is 11 or 12. Feedback is specific and encouraging. Never sarcastic, never
"you failed to". Frame gaps as the next step: "you had the temperature — now link it to
why the species survives".

---

## 3. Marking model (this is the core of the app)

Four principles from Singapore primary science marking practice govern everything below.

### 3.1 Cause-and-effect chains

Marks are awarded link by link. A student must connect the scientific variable, the
action, and the resulting outcome. A gap in the chain loses the mark even when both
endpoints are correct.

Therefore keypoints are **ordered links within named chains**, not an unordered set.
Some questions have two parallel chains reaching the same conclusion — 2024 Q32(c) runs
one chain through food availability and a second through dissolved oxygen. A student
who completes one chain and omits the other has a different failure from one who states
both endpoints with no middle, and the feedback must differ accordingly.

Each keypoint carries: chain id, position in chain, and facet role
(`variable` | `action` | `result`).

### 3.2 No penalty for grammar or spelling

Markers ignore phrasing as long as the science is clear. **An LLM judge will not do this
by default** — it rewards fluency. Since the input is speech, transcripts will be full
of filler and false starts, and a naive grader will systematically underscore a correct
but rambling answer.

Mitigation is architectural, not a prompt instruction: split grading into two stages.

- **Stage A — normalise.** Extract the scientific claims from the transcript into clean
  bullet form. Discard filler, repetition, grammar. Award nothing.
- **Stage B — judge.** Match normalised claims against the rubric. Stage B never sees
  the raw transcript.

Two spoken-language rules for Stage A: on self-correction, take the final stated
position and discard the abandoned one; a transcript trailing off mid-sentence is an
incomplete attempt to flag, not a wrong answer to mark.

The grader must also never mention spelling or grammar in its feedback text, even when
not deducting — commenting on it is as demoralising as docking for it.

### 3.3 Contextual matching is a gate, not a keypoint

Reciting a textbook definition that does not answer the specific scenario earns **zero**,
regardless of how much correct science it contains. If this were merely one keypoint
among several, a memorised recital would still collect partial credit from keyword
overlap. It must run **before** keypoint scoring.

Mechanism: each question stores **scenario anchors** — the specific labelled entities
from the prompt (`tube A/B/C`, `substance X`, `plant G`, `animal Y`, `26–34 °C`). The
gate asks whether the answer operates on those anchors or merely restates a general
process.

Do not hard-zero silently. Award the zero, but surface it as a distinct, prominent
message: "this reads as a textbook definition — a marker would give zero even though the
science is right". The zero is the correct mark; the explanation is the teaching.

2024 Q33(c) is a clean example: the answer must isolate pollutant S as the only changed
variable and explicitly rule out heat from the sun. "It's a fair test" is a template
answer and earns nothing.

### 3.4 Mark allocation maps to keypoint count

- 1 mark → exactly one direct, accurate point.
- 2–3 marks → that many structured statements addressing **different facets**
  (identify the change / cite the evidence / state the consequence).

Both rules are mechanically checkable at build time and should be enforced as rubric
validation:

- keypoint count must equal the mark allocation; a mismatch is a rubric bug;
- for multi-mark questions, flag rubrics whose keypoints share a facet — two `result`
  keypoints on a 2-mark question usually means one point was split in half rather than
  two genuine points found.

### 3.5 Runtime grading sequence

1. Transcribe. Show the transcript. Let the student correct mis-heard content words.
2. Normalise (Stage A).
3. Contextual gate against scenario anchors.
4. Chain match: per-link `hit` / `partial` / `broken`, with facet coverage.
5. Conventions pass — comparative language ("faster **than**"), "gains/loses heat" rather
   than "loses energy", pronoun ambiguity. These are **coaching notes only** and never
   change the mark.

---

## 4. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python + FastAPI | Whisper, Pillow, and all ingestion tooling are Python. One process serves API and static files. |
| Frontend | Vanilla HTML/CSS/JS, no build step | Small app, single user. A toolchain adds friction for no benefit. |
| Audio capture | `MediaRecorder` (browser native) | No library. Records webm/opus, POSTs the blob. |
| Speech-to-text | `faster-whisper`, `small.en`, local | See below. |
| Grading | Anthropic API, Sonnet-class, JSON output | Only viable option for judging free-text reasoning. |
| Storage | SQLite + JSON content bundle + PNG crops | No server process, single-file backup. |
| Images | Pillow | Cropping and page rendering. |

### On speech-to-text

The browser Web Speech API is the tempting choice — zero install. Avoid it as the primary
path: it is not actually offline (Chrome ships audio to Google), Safari support is poor,
and it mishandles Singapore-accented child speech on exactly the words that matter —
"evaporation", "condensation", "photosynthesise", "upthrust".

Local Whisper fixes both. `faster-whisper` accepts an `initial_prompt`; seed it with a
PSLE science glossary to bias recognition toward domain terms.

Benchmark on the target machine before committing to a model size. A few seconds for a
20-second answer on a modern laptop is the rough expectation, but this is an estimate,
not a measured figure — measure it in Phase 2 and drop to `base.en` if `small.en` is too
slow.

**Always show the transcript for correction before grading.** A mis-transcription
becoming a wrong mark destroys the child's trust in the app on first contact.

---

## 5. Environment gotchas

- Use PyMuPDF (`fitz`). `zipfile` will not open these — see §1.1 for the correction.
- 9 of 14 papers have no text layer at all, so `pdftotext`-style extraction returns
  nothing on them and OCR is the only route. Tesseract at 300 DPI is accurate enough for
  the structural markers boundary detection relies on.
- OCR the full page and regex over the result. Cropping to a footer band and OCRing that
  in isolation reads *worse*, not better — a 14%-tall bottom crop turned a line tesseract
  read perfectly in context into `CONSISKS OF TO PHIMea pages`.
- Extensions are mixed case (`.pdf` and `.PDF`). Glob case-insensitively.
- 2012–2022 papers predate the 2023 Primary Science syllabus. They remain excellent
  reasoning practice but some content is outside current scope. Tag each paper with a
  syllabus era and let the student filter, rather than silently mixing them.

---

## 6. Open questions

1. **Rubric calibration.** The four marking principles are consistent with how Singapore
   primary science marking is generally described and with what the EPH answers
   demonstrate, but they have not been checked against an official SEAB marking scheme
   with mark annotations. If one becomes available, calibrate a handful of rubrics
   against it during Phase 1 — everything downstream inherits those assumptions.
2. **Segmentation reliability.** Automatic question segmentation of scanned pages is where
   projects like this stall. The plan assumes semi-automatic with human review. If
   detection proves better than expected, the review step can be thinned.
3. **Grader consistency.** Run the same student answer through grading several times and
   measure mark variance before trusting it. If variance is high, tighten the rubric
   schema rather than the prompt.

---

## 7. Chinese Paper 2

Built for **2012–2025**, all fourteen. Everything below was confirmed by direct
inspection unless marked otherwise. Where a claim holds for only some years, the
years are named — the era differences in §7.5 are the whole reason this section is
long, and there are **three** eras, not two.

### 7.1 The source files

The corpus mirrors Science's: 14 papers, 2012–2025, same EPH compilation, same
mixed-case extensions. But the compilation is **not** what is ingested.

Each compilation holds four things — Paper 1 (作文, composition), Paper 2, Paper 3
(听力, listening, *with its transcript printed*), and the answers for all three.
Only Paper 2 and its answers are wanted, so the pipeline reads a split pair:

```
papers/chinese/Compilation/<year> PSLE Chinese Language.pdf   38–57 pages
papers/chinese/Paper2/<year> PSLE Chinese Language.pdf        15–24 pages
papers/chinese/Answer/<year> PSLE Chinese Language.pdf         5–13 pages
```

**`build/cn_split.py` does the splitting, from the compilation's own footers.**
It used to be a manual step outside the repo, and eight years of hand-split files
disagreed with each other badly enough to be worth automating: 2017's Paper 2 held
two pages (Booklet A's cover and Booklet B's last page), 2018's began at Booklet B
with Booklet A missing entirely, and 2016's ran to 28. None of that is visible
downstream — a short paper simply indexes fewer questions and still validates —
which is exactly why it is derived rather than trusted.

The anchor is the per-page paper code, Latin and therefore readable by the cheap
English OCR pass even though the body is Chinese: `0005/1`, `0005/2(A)`,
`0005/2(B)`, `0005/3`. Answers carry no code at all, and that is what identifies
them — they are the pages after the last coded one. Each booklet cover states its
own length and is used as a cross-check; unlike Science's Booklet A cover (§1.3)
these agree on every year, counting the cover itself among the printed pages.

Two traps, both hit: 2013 p17's code OCRs as `000512 (B)` with the slash gone, so
covers are found by their English title (`CHINESE PAPER 2` / `BOOKLET B`) rather
than by their code; and 2016 p23's reads `0005/2(В)/2016` with a **Cyrillic** Ve,
which a plain `[AB]` misses and which silently splits the run in two.

The 2021–2025 pairs were split by hand before this existed. `cn_split.py`
reproduces them page for page on content, differing only by a trailing `BLANK
PAGE` on 2024/2025 and two Paper 1 answer pages, so they are left alone; writing
over an existing pair takes `--force`.

- Pure scans, no usable text layer on any of them. Where the compilations *do*
  carry embedded text it is a **Latin-only OCR pass**: 2018 p20 comes back as
  `011-411,4*-=---`, with the English intact and every Chinese character
  destroyed. Never read it — Vision is the only source.
- Resolution varies: 2021–2023 render 2409×3437, 2025 2092×3344, 2024 1654×2338.
  2024 is the coarsest and still reads cleanly.
- 2021–2023 Paper 2 is 16 pages; 2024–2025 is 15.

`build/cn_unpack.py` renders both files to `work-cn/<year>/`, the paper into
`pages/` and the key into `answer-pages/`. **They are separate directories on
purpose**: no route reads the second, so there is no URL that reaches the answers
(§2.1). The two use different filename stems (`page-001` / `answer-001`) because
the OCR cache is keyed on the stem, and two directories of `page-001.png` would
otherwise share one cache entry.

### 7.2 OCR: Vision reads Chinese, but not pinyin

`build/ocr_vision.py` takes a `languages` tuple; Chinese is
`("zh-Hans", "en-US")`. The cache path is tagged for anything other than the
English default, so the existing Science caches stay valid.

Accuracy on Chinese characters is high enough to work from directly. **Pinyin is
not.** Of the sixteen vocabulary glosses on the 2025 key, **not one** came back
with correct tone marks, and nine were mangled into something that still reads as
text:

| printed | read as |
|---|---|
| 锻炼 duàn liàn | `duan Idn` |
| 克服 kèfú | `KefG` |
| 眉开眼笑 méi kāi yǎn xiào | `meikaiy8n xido` |
| 意外 yìwài | `viwai！` |

Tone marks are lost at 600 dpi as well, so this is not a resolution problem.
Wrong pinyin shown to a child teaches a wrong pronunciation with full confidence,
so `build/cn_key.py` **strips the romanisation** out of the glosses; the
characters, the definition and the English survive. If pinyin is ever wanted in
the UI it must come from a dictionary lookup keyed on the characters.

This is also why no part of the app is built on transcribed option text: the
pinyin questions (Q1–Q2, 请选出画线词语的汉语拼音) have four options differing
*only* by tone, and OCR flattens all four to the same string. The scan is
displayed instead — the same conclusion as §1.4, for a different reason.

### 7.3 Paper 2 structure

90 marks and five sections in every year of the corpus. The **question count is
not** constant: 2017–2025 have 40, and 2012–2016 have **41**.

| § | Section | 2017–2025 | Marks | 2012–2016 | Marks | Answered on |
|---|---|---|---|---|---|---|
| 一 | 语文应用 | Q1–15 | 30 | Q1–10 | 20 | OAS |
| 二 | 短文填空 | Q16–20 | 10 | Q11–16 | 12 | OAS |
| 三 | 阅读理解一 | Q21–25 | 10 | Q17–23 | 14 | OAS |
| 四 | 完成对话 | Q26–29 | 8 | Q24–28 | 10 | booklet / 作答簿 |
| 五 | 阅读理解二 A组 | Q30–33 | 10 | Q29–34 | — | booklet / 作答簿 |
| 五 | 阅读理解二 B组 | Q34–40 | 22 | Q35–41 | — | booklet / 作答簿 |

2012–2016 state 13 questions and 34 marks for 阅读理解二 as a whole and leave the
A/B split without totals of its own, which is why those two cells are empty here
and `None` in `questions.json`. 2012–2016 also group 阅读理解一 into A组/B组; only
2017 onward reserves grouping for 阅读理解二.

**The paper states its own structure, and that is what makes the index checkable
without a human reading it.** Section headers carry a count and a total
(`语文应用（15题30分）`), the group headers usually carry their own
(`B组（Q34-Q40，7题22分）`), and on 2021–2025 two range statements fix where the
chosen answers stop and the written ones begin (`从第1题到第25题…电脑作答卷`,
`从第26题到第40题…写在作答簿`). `build/cn_index.py` validates what it found
against all of these. Nothing is hardcoded per year.

Where a statement is missing the structure still supplies it, and the substitute
is a printed fact rather than an inference from what happened to be found:

- **The OAS boundary** comes from Booklet B's cover on 2012–2020, which print no
  range statements at all (Booklet B just says "Write all your answers in this
  booklet", in English). Booklet A is the OAS half by construction.
- **The last question number** comes from the A組/B組 headers' own stated end, or
  from the section counts when every section states one. Taking it from the
  highest number seen would move when a question was missed — the failure that
  leaves no gap for anyone to notice (§1.6.1).

**Four question layouts, and only the first is what you would expect:**

1. **Block** — 语文应用, 阅读理解一, A组 Q30–32. Number at the left margin, four
   options beneath.
2. **Inline cloze** — 短文填空. The number sits *mid-sentence* with its options
   beside it: `帮助大卫 Q16（1 控制 2 管理 3 阻拦 4 克服）了这个困难`.
3. **Inline dialogue blanks** — 完成对话. Blanks inside a conversation, answered
   from a shared bank of numbered phrases printed above it. **The bank holds
   eight, not four**, in all fourteen years, which is why `options` is read off
   the page rather than assumed; 2025's key has `Q27 (6)` and `Q28 (8)`.
   The bank is numbered three different ways — bare on 2017–2025
   (`1 我们都很开心`), parenthesised on 2012 (`（1）你放心好了`), dotted on
   2013–2016 (`1. 太没有爱心了`, and without even a space in
   `7.巴士在繁忙时间挤满了搭客`). Its size is its highest entry **only when
   everything below that was also read**; one stray number would otherwise set it.
4. **Written** — Q33 and B组 on 2017–2025; the whole of 阅读理解二 on 2012–2016.

Anchoring question numbers to the left margin finds only layout 1 and silently
loses ten questions, so they are matched anywhere on a line. The cost is that
instruction text naming a *range* (`［Q1—Q2 请选出…］`, `（Q21-Q25）`,
`A组（Q30-Q33`) must be excluded, or it invents questions.

Because layouts 2 and 3 put questions *inside* a passage, **the page is the unit
of display, not the question**. Cropping to Q16 would cut away the paragraph it
asks about. This is why the Chinese UI loads the whole paper and scrolls, where
Science shows one question at a time.

### 7.4 The answer key

Single column, question numbers at the left margin, `Q1 (2)`. None of the
two-column geometry §1.6 needed applies.

**The key is a better source than Science's in one specific way: from 2023 it
prints a mark marker at every award point inside the model answer.**

```
贝贝的两个哥哥经常吵架（1）。因为二哥经常争做老大（1），大哥也不相让（1）。
```

That is the keypoint decomposition `build/rubric.py` deliberately leaves empty for
a human to author, arriving already done — *and* checkable, because the markers
must sum to the mark the paper states. `build/cn_rubric.py` splits on them and
refuses to auto-mark any question where the total disagrees.

Other fields worth knowing:

- `（注解：…）` is **not** Science's `Explanation:`. It mostly says *where in the
  passage to find the answer* (`见第二段第三句`) rather than giving an underlying
  principle. Different pedagogy — it teaches evidence-locating, not theory.
- `（答案合理即可）` marks an open-response question (2025 Q40). Any defensible
  view earns the marks if it is supported.
- `（评分标准：内容2分；语言2分）` appears on Q33 and splits its marks between
  content and language quality.
- The key also covers Paper 1 and Paper 3, **and Paper 3 restarts at Q1**. A bare
  `QN` match over the document collides with 语文应用, so numbering is scoped by
  the 试卷 banner that precedes it.

Three traps, all hit:

- **A model answer's first line is typeset level with its own question number but
  starts a few pixels higher.** Ordering by `top` therefore puts the body *before*
  the anchor, and every answer lands on the previous question — a silent cascade
  that gave Q36 a 1-mark rubric instead of 3 and still looked like a well-formed
  rubric. Lines are banded into visual rows and ordered within the band instead.
  Same lesson as §1.6's column ordering, one axis over.
- **Mark markers count only inside the model answer.** `故选（3）` in a 注解 is a
  reference to an option, not an award.
- **Q33 never totals.** Its markers cover 1.5 of 4 marks on 2025 and 2 of 4 on
  2024, because the `语言` half is holistic and has no span to award it against.
  This is the publisher's behaviour, identical in every year, and is why Q33 is
  self-marked rather than auto-marked.

### 7.5 Era differences

There are **three eras**, and the boundary that matters most is not the one you
would guess from the dates:

| | 2012–2016 | 2017–2020 | 2021–2025 |
|---|---|---|---|
| Physical form | two booklets, A + B | two booklets, A + B | one booklet |
| Questions | 41 | 40 | 40 |
| Written answers go | in Booklet B | in Booklet B | in a separate 作答簿 |
| Range statements | OAS only | neither | both |
| 阅读理解二 A组 | written | 3 chosen + 1 written | 3 chosen + 1 written |
| Mark markers in the key | none | none | 2023 on |
| Paper 2 pages | 20 | 24 | 15–16 |

The 2024/2025 assumptions did not survive contact with 2021–2023, and the
2021–2025 assumptions did not survive contact with 2012–2020. Every one of these
failed **silently**:

0. **2012–2020 bind Paper 2 as two physical booklets** — `0005/2(A)`, answered on
   the OAS, and `0005/2(B)`, written in the booklet itself. Covers, blank pages
   and a closing copyright page sit inside each, so the built paper is 20 or 24
   pages against 2021–2025's 15–16. Neither booklet prints the 电脑作答卷 /
   写在作答簿 sentences, so the OAS boundary comes from Booklet B's cover (§7.3).
1. **2021–2023 print the 阅读理解二 header bare** — `五阅读理解二`, with no
   `（11题32分）` after it. Only 2024–2025 state the parent total; the earlier
   papers leave it to the A组/B组 sub-headers. Requiring a name *and* a count
   meant the section never opened, and 完成对话 quietly absorbed the remaining
   fifteen questions.

   The same section then failed twice more, differently. **2017 states A組's range
   and totals on the parent header** — `五 阅读理解二（Q30-Q33，4题10分）`
   describes four of the section's eleven questions, so taking it as the section's
   own count fails validation against a paper that is not wrong; a header naming a
   range is now read as describing that range. And that header is 22 characters,
   just over a length guard that had only ever seen the bare form. What marks a
   line as a header is that it states the section's *shape* — a count and total,
   or the range it covers — with geometry deciding only when it states neither.

   **2017 also loses the first character of the name**: Vision reads
   `五 阔读理解二`, 阅 as 阔. Section names are matched on the stem (`读理解二`)
   for that reason; the stems stay distinct from each other and from everything
   else on the page.
2. **Mark markers exist only from 2023.** Every model answer from 2012 to 2022 is
   complete prose with no `（1）` anywhere. Those years' written questions
   therefore **cannot** be auto-marked and fall through to self-marking against
   the model answer. *No* markers is that era; *some* markers that do not total
   correctly is a bad read and is still a hard failure. Do not paper over the
   difference by splitting the prose on sentence boundaries — that is exactly the
   trap §3 documents, and a wrong rubric teaches a child wrong Chinese with full
   confidence.
3. **Option brackets are unreliable.** 2021 drops them entirely (`Q1 ②`, a bare
   circled numeral); 2024 emits both forms at once (`Q7 （②2）`); 2021–2023 run
   the option together with the next column (`Q16（4） |实现`,
   `Q21（2） 考生可以从文章…`). Option reading is therefore **structural** — the
   run before any Chinese begins — not bracket-dependent. Every digit in that run
   must agree, or the read is refused.
4. **2023 Q19 lost its opening bracket**: `Q194） 所有`. Read greedily that is
   *question 194*, and the real Q19 disappears without leaving a gap in the
   sequence for anyone to notice. Question numbers are now confirmed against the
   paper's own question set, longest plausible prefix winning, and the leftover
   digits fall through to the option — the same discipline as §1.5.1, applied to
   the key. 2013's Q29 fails the same way from the other end — its `Q` reads as a
   `9`, giving `929` at confidence 0.30 — and is recovered only because the
   sequence had already fixed which number was missing.
5. **The key's left margin is not a constant.** Question numbers sit at 183px on
   2025 and at 619px on 2017, at the same 300 dpi. An absolute cut-off tuned to
   the newer papers dropped two thirds of 2017's key and the whole of its Booklet
   B — and, being a *missing* entry rather than a wrong one, it showed up only as
   a coverage failure. The margin is measured per page now, capped at a third of
   the page width so a page whose only `Q…` is mid-text cannot define its own.

Items 3 and 4 are the dangerous ones, for §1.6.1's reason: **a misread option is
worse than any other failure here.** There is no partial credit to soften it — the
child is simply told they were wrong when they were right. Both the extractor and
the index refuse rather than guess, and every refusal is reported.

**What separates a chosen question from a written one is measured, not assumed.**
Past the OAS boundary the eras diverge — 2017–2025 print three more option
questions (阅读理解二 A组 Q30–Q32), 2012–2016 print none, their whole 阅读理解二
being ruled answer lines and a 得分 box. Counting the option markers under each
question splits them cleanly: those three come back with exactly `{1,2,3,4}` and
every written question with nothing at all, in all fourteen years. Inferring it
from the group headers instead would have worked by coincidence and broken the
first time a header changed shape.

### 7.6 Marking model — how Chinese differs from §3

§3 is Science's, and most of it does **not** transfer.

- **§3.1 cause-and-effect chains: does not apply.** A Chinese comprehension answer
  is an unordered *set* of retrievable points, not a chain — 2025 Q38's four marks
  are four separate observations about the brothers, and omitting the second
  breaks nothing. Keypoints are flat, with no chain id and no facet role.
  Ordering them would invent structure the source does not have.
- **§3.2 ignore phrasing: inverts in principle, holds in practice.** In a language
  paper the language *is* the assessed object, so Science's normalise-then-judge
  split would discard the very thing being marked. But the marks that actually
  reward language quality appear only on Q33, which is self-marked — so the
  grader marks content only, and never comments on 错别字, handwriting or style.
- **§3.3 the contextual gate: does not apply.** The gate exists to catch a
  memorised definition recited at a scenario it does not fit. A comprehension
  answer is already tied to its passage; there is no general-principle recital to
  guard against.
- **§3.4 marks map to keypoint count: holds, and is printed** (§7.4). Keypoints
  carry their own values — 2025 Q39's first point is worth 2 and its other two are
  worth 1 each — so the total cannot be recovered by counting hits.

**Answers are typed, never spoken.** This was a deliberate reversal of the app's
original premise and it is worth not relitigating:

- Q34–Q35 ask for one word lifted from the passage (`文中表示"…"的词语是____`).
  Spoken, 熟悉 is `shúxī` — indistinguishable from its homophones, so the mark
  would hinge on which characters Whisper picked rather than on what the child
  knew. Those two are marked by **string comparison**, which needs no API and is
  more reliable than asking a model.
- Q33 is a writing task.
- `small.en` is English-only; Chinese would need the multilingual model, and its
  error rate on L2/heritage child Mandarin is a much larger risk than the English
  case ever was. Unmeasured, and not worth measuring unless the premise changes.

Three response modes, decided by the paper rather than by preference, and recorded
per question in `questions.json`:

| mode | questions | marked by |
|---|---|---|
| `choose` | Q1–Q32 | the key — no API key, never fails |
| `typed` | Q34–Q40 | keypoints (2023+), else self-marked |
| `self_marked` | Q33 | the student, against the model answer |

**Nothing is marked until the paper is finished.** Marking each answer as it is
given turns a 40-question paper into 40 little tests, and a running total invites
watching the number instead of reading the passage. Answers are collected — and
persisted to `localStorage`, because 40 questions is a long sitting to lose to a
stray refresh — and the marks arrive once, at the end.

### 7.7 Build order and coverage

```bash
build/cn_split.py    # compilation -> Paper2/, Answer/    (--dry-run to inspect)
build/cn_unpack.py   # PDFs        -> work-cn/<year>/pages, answer-pages
build/cn_index.py    # pages       -> questions.json   (validates against the paper)
build/cn_key.py      # answers     -> key.json         (validates against questions.json)
build/cn_rubric.py   # key         -> rubrics.json     (refuses what does not total)
```

`cn_key.py` must run after `cn_index.py`: it needs the paper's question set to
resolve damaged numbers (§7.5 items 4), exactly as `extract_mcq_key.py` needs
`index_mcq.py` in §1.6.1.

All fourteen years index and key with **no problems reported** — every section
count, group total and mark sum agrees with what the paper states about itself,
and every year totals 90 marks.

| Year | chosen | auto-marked written | self-marked |
|---|---|---|---|
| 2012–2016 | 28q / 56m | — | 13q / 34m |
| 2017–2020 | 32q / 64m | — | 8q / 26m |
| 2021 | 32q / 64m | — | 8q / 26m |
| 2022 | 32q / 64m | — | 8q / 26m |
| 2023–2025 | 32q / 64m | 7q / 22m | 1q / 4m |

Options were checked against the scans by eye for 2012, 2017 and 2020 — 67
questions, all correct, including bank answers above 4 (`Q27 (8)`) and pages whose
注解 text is full of `（2）`-shaped references that are *not* the answer. No year
produced a refused option read.

### 7.8 Not built

- **Table-shaped model answers** — 2012 Q31, 2014 Q32, 2016 Q32, three in the
  whole corpus. Rows are read left to right, which is right for prose and wrong
  for a table: the left cell's words end up threaded through the right cell's
  (`父亲有奇（a） 儿子的反应怪的举动感到丢脸…`). Three questions do not justify
  reconstructing table geometry and all three are self-marked anyway, so the key
  flags them `table_layout` and says to read the answer off the scan instead.
- **Pinyin in the glosses** is dropped, not fixed (§7.2). A dictionary lookup keyed
  on the characters would restore it.
- **Paper 1 (作文)** and **Paper 3 (听力)**. Paper 3 is the interesting one: the
  compilations print its full transcript, so it could be spoken aloud by TTS
  rather than needing the original audio.
- **The oral exam (口试)** — the natural home for a voice app in Chinese, and
  absent from these files entirely.
- **The review page** is Science-only. Progress is not — see §8.
- **Grader consistency (§6.3) is unmeasured for Chinese**, as it is for Science.

---

## 8. The progress report

Covers both subjects, which is why it is here rather than inside §1–6 or §7.
It is a parent's view, and it answers three questions: is she improving, what is
she weakest at, and how much is left.

**One subject at a time, never both at once.** `/api/progress` is Science and
`/api/chinese/progress` is Chinese; the front end has a subject picker and the
year picker is scoped to it. A single endpoint taking `?subject=` was the obvious
design and it is wrong, because the two reports share only the attempt log and
the chart. A Science weakness is a syllabus topic and a broken link in a chain; a
Chinese one is a section of the paper. Averaging them produces a number that
describes neither, and a union schema would have half its fields null on every
request.

### 8.1 The chart

One bar per paper per day: x is the date, y is marks, and each bar is labelled
with the paper it came from. Two things about it were decided rather than fallen
into:

- **The rollup keeps the paper, not just the day.** `db.by_paper_and_day()`
  exists for this. Collapsing to the date alone is the natural rollup and it
  destroys the only thing the bar is labelled with — a morning on 2022 and an
  afternoon on 2024 are two results, not one average.
- **Bar height is the marks that were on offer in that sitting, and the fill is
  what was earned.** Plotting earned marks alone makes a three-question warm-up
  look like a collapse next to a full paper; plotting percentage alone makes one
  lucky question a full-height bar. Both readings are visible at once this way.

Science's bar counts **both booklets** — a Booklet A morning is marks on that
paper. The topic, theme, facet and gate rollups underneath it stay Booklet B
only, because they are keyed to its rubrics and the MCQ log has none of them.

### 8.1.1 The bar is split by how the marks were answered for

A bar that sums the whole sitting says which morning was good without saying
which *half* of it was, and a full-marks Booklet A will hide a weak Booklet B
inside the same column. So each bar stacks one block per kind of answering —
`db.by_paper_and_day()` takes the kinds and a `kind_of(row)`, and every block
carries its own fill, so a green base under a red cap is the whole finding.

- **Science splits by booklet**, MCQ then written (`main.SCIENCE_KINDS`). They
  are marked by different machinery and behave differently under it: an MCQ is
  right or wrong, a written sub-part is usually partly right.
- **Chinese splits by response mode** (`chinese.CN_KINDS`), which is the same
  distinction drawn from what the paper asks for rather than from how it is
  bound — Paper 2 is one sitting whichever era printed it (§7.5).
- **The rollup under the chart is per booklet too**, and so is coverage: 28 MCQs
  and forty-odd written sub-parts are different work, and one combined "still to
  try" cannot say which half is untouched. `/api/progress` therefore spans the
  union of both inventories, not Booklet B's alone.

Three things about the drawing were got wrong first and are worth keeping:

- **Stacked, not side by side.** Two bars per paper would show the same numbers
  and cost the click its meaning — one bar has to be one paper on one day, or
  §8.4 has nothing to open.
- **A kind with nothing in it does not appear.** A Booklet A morning draws as one
  block, and the key names only the kinds actually on the chart.
- **The key is ordered from the declaration, not from the data.** First-seen
  order is the order the *days* happened to fall in, which put Booklet B ahead of
  Booklet A in the key while the chart stacked them the other way round.
  `db.kinds_present()` exists for this.

The block's letter (`A`/`B`, 选/写/自) is **drawn hidden and then measured**. Its
height is a percentage of a percentage of a CSS variable, less whatever the row
of year labels takes, so only the laid-out page knows whether the letter fits;
predicting it from a pixel constant copied out of the stylesheet was over by a
tenth.

### 8.2 Coverage is a count, not a list

The report used to name every untouched sub-part as a row of question-number
chips. It is gone. It said nothing the count does not, it grew without bound as
papers were backfilled, and a wall of numbers reads as a list of failures rather
than of work remaining.

### 8.3 `list_attempts` caps at 200 rows, and the report must opt out

The cap is right for "show me recent attempts" and silently wrong here: rows come
back newest first, so a truncated read drops the **oldest** days — the left-hand
end of the trend and the half of the comparison that shows improvement. A Chinese
paper is 40 questions, so two sittings of one year already reach it. Every
progress and score query passes `limit=None`.

### 8.4 Clicking a bar opens what it is made of

`/api/papers/{year}/attempts/{date}` and `/api/chinese/papers/{year}/attempts/
{date}`. The bar says a morning on the 2021 paper earned 56 of 70; the panel says
which questions those were and what she actually put down — for a chosen answer
the option she picked against the option that was right, for a written one the
answer as submitted and the marks it drew. It is the question a parent asks next,
and it turns 82% back into something to talk about.

- **The bucket is `db.day_of()`, used by both.** The chart files a row under a
  day and the panel re-selects rows by it. A bar whose click cannot reproduce it
  is worse than no drill-down at all, so the two never compute it separately.
- **Every attempt is listed, not the best one.** A second try at a question is
  the interesting row here; the rollups elsewhere already take the best.
- **The correct option appears, and that is not a leak of the kind §2.1 guards
  against.** Only questions attempted that day come back, and marking an answer
  shows its key at the time of answering — nothing here was not already seen.
- **Chosen answers pack into a grid and written ones get a list.** 28 MCQs fit
  without scrolling; a written answer's text is the point of the panel, because
  the mark alone does not say what she wrote and what she wrote is what a parent
  can help with. A cell that wraps makes its whole row taller and the grid stops
  reading as one sweep of ticks, so the cells do not wrap.

The panel sits under the chart rather than in a dialog: it is a reading of the
bar above it, and both should be visible at once.

---

## 9. The container

`Dockerfile` and `docker-compose.yml` build one image holding the app, both
subjects' papers and the Whisper weights. `docs/DOCKER.md` is the operational
note; three things about it are load-bearing rather than incidental.

- **`requirements-app.txt` is what the image installs**, not `requirements.txt`.
  The ingestion half of `requirements.txt` cannot install on Linux at all — the
  OCR pass is macOS Vision, and pyobjc has no Linux wheels. A new *runtime*
  dependency must be added to **both** files, or it resolves locally and the
  container fails on import.
- **The image carries no answer renders.** `work-ans/*/pages` and
  `work-cn/*/answer-pages` are excluded by `.dockerignore`, and `work/`'s two
  full-paper unpacks are pruned at build time to their Booklet B range. The routes
  already refuse to serve outside it (§1.6, §7.1); this makes the filesystem agree,
  so a later routing mistake cannot expose a page that is not there.
- **Nothing is fetched at run time.** The Whisper weights are baked in and
  `HF_HUB_OFFLINE=1` holds the container to them, so §2.2 survives being hosted.
  Changing `PSLE_WHISPER_MODEL` therefore needs a rebuild
  (`--build-arg WHISPER_MODEL=…`), not an edit to `.env`.

One thing hosting cannot fix: browsers grant microphone access only on `https://`
or `localhost`, so Science's spoken answers do not work over plain HTTP to a LAN
address and fall back to typing. Chinese is unaffected — it is typed and chosen by
design (§7.6).
