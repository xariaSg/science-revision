# PSLE Science Booklet B — Voice Practice App

Local-only web app. A Primary 6 student is shown a real PSLE Booklet B (open-ended)
question, speaks their answer aloud, and receives a mark plus specific feedback on
what was missed and how to fix it.

Single user (one child), runs on localhost, never deployed.

---

## 1. Verified findings about the source files

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

### 1.5 The answer pages

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
