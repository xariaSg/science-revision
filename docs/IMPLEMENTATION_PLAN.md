# Implementation plan

Read `CLAUDE.md` first — it holds the verified facts about the source files and the
marking model. This document is the build order.

Two tracks. **Track 1** is an offline pipeline run once per paper that turns page scans
into a reviewed content bundle. **Track 2** is the runtime app that serves it. Almost all
the difficulty is in Track 1; once the bundle is good, the app is straightforward.

Build Track 1 for two papers only (2024, 2025) before writing any of Track 2.

---

## Proposed layout

```
psle-booklet-b/
  CLAUDE.md
  IMPLEMENTATION_PLAN.md
  papers/                     source archives — GITIGNORED
  build/
    unpack.py                 archive -> page JPEGs
    detect_boundaries.py      find Booklet A / B / answers
    segment.py                page -> per-question crops
    extract.py                vision extraction of text, marks, answers
    rubric.py                 model answer -> rubric JSON
    validate.py               rubric validity checks
  review/                     local crop + rubric review UI
  bundle/                     generated content — GITIGNORED
    questions.json
    crops/
  app/
    main.py                   FastAPI
    stt.py                    faster-whisper wrapper
    grade.py                  two-stage grading
    static/
  data/
    attempts.db               SQLite
  tests/
```

---

## Phase 0 — Ingestion spike

**Goal:** prove the archives can be unpacked and booklet boundaries found automatically.
Two papers only.

Tasks:

- `unpack.py` — read a `.pdf`/`.PDF` archive with `zipfile`, parse `manifest.json`,
  extract page JPEGs to a working directory in page order. Assert the `.txt` files are
  empty and warn loudly if any paper ever has content in them (that would be a better
  source than OCR).
- `detect_boundaries.py` — locate the Booklet A cover and Booklet B cover, read the
  stated printed-page count from each footer, derive page ranges, treat the remainder as
  answers. Emit a boundaries JSON per paper with a confidence flag.
- A contact-sheet dump so a human can eyeball the detected boundaries in one image.

**Acceptance:** boundaries for 2024 and 2025 match the known truth in `CLAUDE.md`
(A 1–16, B 17–28, answers 29–34) with no manual input.

**Risk:** if footer OCR is unreliable at 924×1316, fall back to detecting the distinctive
Booklet B cover ("PASTE YOUR BARCODE LABEL HERE" occupies the top third of the page) as a
layout signature rather than as text.

---

## Phase 1 — Content bundle

**Goal:** a reviewed, validated `questions.json` plus crops for 2024 and 2025.

### 1a. Segmentation

Question numbers sit in the left margin in bold. Detect candidate y-positions of margin
numbers, propose question boundaries, crop.

Do not aim for full automation. Build a **crop review UI** in `review/` — a local page
showing each proposed crop over the source page with draggable boundaries. Two papers is
roughly 24 Booklet B pages; a human pass is minutes, and it removes the single largest
source of downstream garbage.

Crops needed per question: the whole question (stem + all sub-parts + any table, graph,
or diagram), and optionally per-sub-part crops for focused display.

### 1b. Vision extraction

For each question crop, extract: question number, sub-part labels, stem text, mark
allocation per sub-part, and a description of any figure. Text is for search, tagging,
and grading context — **the app displays the crop, not the text**.

For each answer-page region, extract the model answer and the `Explanation:` block as
separate fields, keyed to question and sub-part.

### 1c. Topic tagging

Tag each sub-part with a primary and secondary topic from the 2023 syllabus themes.
Booklet B questions are usually multi-topic. Do this now — retrofitting it later means
reprocessing everything.

### 1d. Rubric generation

Generate the rubric from the model answer plus the Explanation block. Schema:

```json
{
  "question_id": "2024_Q32",
  "part": "c",
  "marks": 3,
  "syllabus_era": "2023",
  "topics": ["interactions_within_environment", "photosynthesis"],
  "scenario_anchors": ["plant G", "bird B", "fish C", "pond"],
  "chains": [
    {
      "chain_id": "food",
      "keypoints": [
        { "kp_id": "food_1", "position": 1, "facet": "variable",
          "statement": "fewer plant G means less food available for bird B",
          "accepts": ["bird B has less to eat", "food source for bird B decreases"] },
        { "kp_id": "food_2", "position": 2, "facet": "action",
          "statement": "bird B eats more fish C to meet the same food need",
          "accepts": ["bird B turns to fish C", "bird B preys on fish C instead"] },
        { "kp_id": "food_3", "position": 3, "facet": "result",
          "statement": "the number of fish C decreases",
          "accepts": ["fish C population drops"] }
      ]
    },
    {
      "chain_id": "oxygen",
      "keypoints": [
        { "kp_id": "oxy_1", "position": 1, "facet": "variable",
          "statement": "fewer plant G means less photosynthesis takes place",
          "accepts": [] },
        { "kp_id": "oxy_2", "position": 2, "facet": "action",
          "statement": "less oxygen is produced and dissolved in the pond water",
          "accepts": ["less dissolved oxygen available"] },
        { "kp_id": "oxy_3", "position": 3, "facet": "result",
          "statement": "the number of fish C decreases",
          "accepts": [] }
      ]
    }
  ],
  "traps": [
    "stating that fish C decreases without naming a mechanism",
    "answering only via food and omitting the oxygen route"
  ],
  "model_answer": "...",
  "explanation": "...",
  "source": "EPH suggested answer",
  "reviewed": false
}
```

Note the chain/mark relationship: keypoint count across chains need not equal marks when
parallel chains reach the same conclusion — record how many chains are required for full
marks in a `chains_required` field if the answer demands both.

### 1e. Validation

`validate.py` enforces the mechanical rules:

- keypoint count matches mark allocation (accounting for parallel chains);
- multi-mark questions do not have all keypoints sharing one facet;
- every question has at least one scenario anchor;
- `accepts` lists contain no near-duplicates of the `statement`;
- every rubric references a crop file that exists.

Failures go to a review queue, not to the bundle.

### 1f. Human review

A second review UI pass over generated rubrics. Nothing enters the bundle with
`reviewed: false`. **This is the quality gate for the entire project** — a wrong rubric
teaches a child the wrong thing with full confidence.

**Acceptance:** every Booklet B sub-part in 2024 and 2025 has a reviewed rubric, a valid
crop, marks, topics, and anchors.

---

## Phase 2 — App shell, no grading

**Goal:** the voice loop feels good before anything depends on it.

- FastAPI serving `questions.json`, crops, and the static frontend.
- Question browser: filter by year, topic, marks, syllabus era.
- Question view: crop displayed at readable size, zoomable. Marks shown.
- Record via `MediaRecorder`, POST the blob, transcribe with `faster-whisper`
  (`initial_prompt` seeded with a PSLE science glossary).
- Transcript shown in an editable field. The student fixes mis-heard words before
  anything else happens.
- "Reveal model answer" as a manual self-check.
- Typed-answer mode as an alternative to voice — some days speaking aloud is the wrong
  tool, and it also gives a clean baseline for testing the grader without audio.

**Benchmark here:** transcription latency on the real machine. If `small.en` is slow,
drop to `base.en` and compare accuracy on ten real spoken answers.

**Acceptance:** the child can practise end to end, unassisted, with self-marking.

---

## Phase 3 — Grading and feedback

Implement the five-step sequence from `CLAUDE.md` §3.5.

Two separate API calls, Stage A and Stage B. Stage B receives only the normalised claims,
the rubric, and the anchors — **never the raw transcript**. This is what protects a
rambling but correct answer.

Grading response shape:

```json
{
  "context_gate": {
    "passed": true,
    "anchors_used": ["plant G", "fish C"],
    "note": null
  },
  "marks_awarded": 2,
  "marks_total": 3,
  "chains": [
    {
      "chain_id": "food",
      "links": [
        { "kp_id": "food_1", "status": "hit" },
        { "kp_id": "food_2", "status": "broken",
          "note": "you jumped from less food straight to fish C dropping" },
        { "kp_id": "food_3", "status": "hit" }
      ]
    }
  ],
  "missed_summary": ["the oxygen route was not mentioned at all"],
  "improved_answer": "...",
  "convention_notes": ["say 'fewer than' rather than just 'fewer'"],
  "incomplete_attempt": false
}
```

Feedback UI:

- Chain visualisation — the student's chain rendered against the model chain, with the
  gap shown at the exact link where reasoning stopped. Seeing your own arrow stop short
  teaches the habit better than any prose comment.
- Context-gate failure rendered as its own prominent message, distinct from a low mark.
- Model answer, then the `Explanation:` block revealed separately below it.
- Convention notes visually subordinate — clearly labelled as coaching, not deductions.

**Acceptance:** ten hand-marked answers of varying quality produce marks a human agrees
with. Run each three times and check mark variance; if it is high, tighten the rubric
schema rather than the prompt.

---

## Phase 4 — Progress

- SQLite attempt log: question, sub-part, transcript, normalised claims, per-keypoint
  outcome, mark, timestamp.
- Weak-keypoint tracking: which facets and topics are repeatedly missed.
- Re-serve previously missed questions after a delay.
- A simple parent view: marks over time, weakest topics, questions never attempted.

---

## Phase 5 — Backfill 2012–2023

Mechanical once the pipeline is proven, with two caveats:

- Boundary detection is unverified for these years and page counts vary widely — expect
  to handle format drift, especially in the 2012–2016 papers.
- Tag pre-2023 papers with their syllabus era so the student can exclude out-of-scope
  content.

---

## Build order rationale

Track 1 before Track 2, and two papers before fourteen, because the failure mode that
kills this project is building a polished app on top of a bundle full of bad crops and
invented rubrics. Segmentation quality and rubric quality are the whole product; the
recording button is not.
