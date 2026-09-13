"use strict";

/* Science Booklet A (multiple choice), the whole booklet at once.
 *
 * Options are printed on the scan beside each question -- sometimes as pictures
 * (2012 Q1's four options are drawings of birds' heads, 2015 Q12's are diagrams
 * of a germinating seed) -- so retyping them here would duplicate the paper
 * badly, the same reasoning CLAUDE.md 1.5 gives for Booklet B. The paper
 * scrolls on one side and every question's four-option card sits on the other,
 * the same shape as the Chinese and English Booklet A screens (chinese.js,
 * english.js): nothing is marked until the whole booklet is finished, so
 * picking an option is changing your mind rather than a second attempt, and a
 * running total in the corner would only invite watching the number instead of
 * working through the paper.
 */

const MCQ = (() => {
  const els = {};
  const state = {
    paper: null, label: null, questions: [], pageSizes: [], pages: 0,
    zoom: 100,
    answers: new Map(),   // question -> choice (1-4)
    results: new Map(),   // question -> marked result, once finished
    autoMarks: 0,
    available: 0,
    source: "",
    finished: false,
  };

  const SPLIT_KEY = "psle.mcqSplitPercent";
  const SPLIT_MIN = 25, SPLIT_MAX = 70, SPLIT_DEFAULT = 50;
  // In-progress answers survive a reload -- a 28-30 question booklet is a long
  // enough sitting to lose to a stray refresh, and none of it is submitted
  // until Finish.
  const answersKey = (paper) => `psle.mcq.${paper}.answers`;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function getJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail
      || `${res.status}`);
    return res.json();
  }

  const marksLabel = (n) => (n == null ? "marks unknown" : n === 1 ? "1 mark" : `${n} marks`);

  /* ------------------------------------------------------------------ pages */

  function renderPages() {
    els.pages.innerHTML = "";
    const sizes = new Map((state.pageSizes || []).map((p) => [p.page, p]));
    for (let page = 1; page <= state.pages; page += 1) {
      const wrap = document.createElement("div");
      wrap.className = "mcq-page";
      wrap.dataset.page = String(page);
      const img = new Image();
      // The intrinsic size must be set before the src, so the browser reserves
      // the page's height while the image is still unloaded. Without it every
      // lazy page is zero-high and "jump to page 12" lands near the top.
      const size = sizes.get(page);
      if (size) { img.width = size.width; img.height = size.height; }
      img.src = `/api/mcq/papers/${state.paper}/pages/${page}`;
      img.alt = `Page ${page}`;
      img.loading = "lazy";
      img.style.width = `${state.zoom}%`;
      wrap.append(img);
      els.pages.append(wrap);
    }
  }

  function setZoom(next) {
    state.zoom = Math.min(320, Math.max(60, next));
    els.zoomLabel.textContent = state.zoom === 100 ? "Fit" : `${state.zoom}%`;
    for (const img of els.pages.querySelectorAll("img")) {
      img.style.width = `${state.zoom}%`;
    }
  }

  function showPage(page) {
    const target = els.pages.querySelector(`.mcq-page[data-page="${page}"]`);
    if (!target) return;
    // Assigned rather than scrollTo({behavior:"smooth"}), which some engines
    // ignore entirely on a nested scroller -- the jump silently did nothing.
    els.pages.scrollTop = target.offsetTop - els.pages.offsetTop - 8;
  }

  function showCard(number) {
    const target = els.list.querySelector(`.mcq-card[data-question="${number}"]`);
    if (!target) return;
    els.answers.scrollTop = target.offsetTop - els.answers.offsetTop - 8;
  }

  /* ---------------------------------------------------------- stored answers */

  function saveAnswers() {
    try {
      localStorage.setItem(answersKey(state.paper),
        JSON.stringify([...state.answers]));
    } catch { /* private mode */ }
  }

  function loadAnswers() {
    try {
      const raw = localStorage.getItem(answersKey(state.paper));
      state.answers = new Map(raw ? JSON.parse(raw) : []);
    } catch { state.answers = new Map(); }
  }

  function clearAnswers() {
    try { localStorage.removeItem(answersKey(state.paper)); } catch { /* private */ }
  }

  /* ------------------------------------------------------------ answer cards */

  function card(question) {
    const el = document.createElement("article");
    el.className = "card mcq-card";
    el.dataset.question = String(question.question);
    el.dataset.page = String(question.pages[0]);

    const head = document.createElement("header");
    head.className = "mcq-card-head";
    const jumps = question.pages.map((page) =>
      `<button class="linkbtn tiny" type="button" data-goto="${page}">page ${page}</button>`
    ).join("");
    head.innerHTML = `<h3>Q${question.question}</h3>`
      + `<span class="marks">${marksLabel(question.marks)}</span>`
      + jumps;
    el.append(head);

    const body = document.createElement("div");
    body.className = "mcq-card-body";
    el.append(body);

    chooseWidget(question, body, el);
    body.append(feedbackSlot());

    el.addEventListener("click", (event) => {
      const goto = event.target.closest("[data-goto]");
      if (goto) { showPage(Number(goto.dataset.goto)); return; }
      select(question.question);
    });
    return el;
  }

  function chooseWidget(question, body, cardEl) {
    const options = document.createElement("div");
    options.className = "options";
    const saved = state.answers.get(question.question);
    // Every Booklet A question offers exactly four options (CLAUDE.md 1.5) --
    // fixed here rather than read off however many the indexer happened to spot,
    // since a picture option (2012 Q1's four bird drawings) still needs a button.
    for (let n = 1; n <= 4; n += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "option";
      button.dataset.choice = String(n);
      button.textContent = String(n);
      if (saved === n) button.classList.add("chosen");
      button.addEventListener("click", () => {
        if (state.finished) return;
        // Selection only. Nothing is marked until the booklet is finished, so
        // picking again is changing your mind, not a second attempt.
        state.answers.set(question.question, n);
        for (const other of options.querySelectorAll(".option")) {
          other.classList.toggle("chosen", other === button);
        }
        cardEl.classList.add("answered");
        saveAnswers();
        updateProgress();
      });
      options.append(button);
    }
    body.append(options);
    if (saved) cardEl.classList.add("answered");
  }

  function feedbackSlot() {
    const slot = document.createElement("div");
    slot.className = "mcq-feedback";
    return slot;
  }

  /* -------------------------------------------------------------- finishing */

  function answeredCount() {
    return state.questions.filter((q) => state.answers.has(q.question)).length;
  }

  function updateProgress() {
    if (state.finished) return;
    const done = answeredCount();
    const total = state.questions.length;
    els.progress.textContent = `${done} of ${total} answered`;
    els.header.textContent = `${done} of ${total} answered`;
    els.finish.disabled = done === 0;
  }

  async function finishPaper() {
    const left = state.questions.length - answeredCount();
    if (left && !window.confirm(
      `${left} question${left === 1 ? " is" : "s are"} still blank. `
      + "Finish and mark the paper anyway?")) return;

    state.finished = true;
    els.finish.disabled = true;
    els.root.classList.add("finished");

    const todo = state.questions.filter((q) => state.answers.has(q.question));
    let done = 0;
    for (const question of todo) {
      els.progress.textContent = `Marking… ${done} of ${todo.length}`;
      const choice = state.answers.get(question.question);
      try {
        const result = await postJSON(
          `/api/mcq/papers/${state.paper}/answer/${question.question}`, { choice });
        state.results.set(question.question, result);
        if (result.source) state.source = result.source;
      } catch (err) {
        state.results.set(question.question, { error: err.message });
      }
      done += 1;
    }

    els.progress.textContent = "";
    renderResults();
  }

  function renderResults() {
    let earned = 0, available = 0;
    for (const question of state.questions) {
      available += question.marks || 0;
      const result = state.results.get(question.question);
      const cardEl = els.list.querySelector(
        `.mcq-card[data-question="${question.question}"]`);
      if (!cardEl) continue;

      cardEl.classList.add("marked");
      const slot = cardEl.querySelector(".mcq-feedback");

      if (!result) {
        slot.innerHTML = `<p class="muted">Not answered.</p>`;
        continue;
      }
      if (result.error) {
        slot.innerHTML = `<p class="error">${esc(result.error)}</p>`;
        continue;
      }
      if (typeof result.marks === "number") earned += result.marks;
      renderChooseResult(cardEl, result);
    }
    // The paper total is summed from each question's own mark value, never from
    // a paper-level "stated total marks" -- some prelim scans OCR the bracket
    // around a mark total into a spurious leading digit (CLAUDE.md 10.3), so a
    // paper of 30 questions at 2 marks each can carry a printed-looking total
    // nowhere near the true 60. Summing what was actually marked is always right.
    state.autoMarks = earned;
    state.available = available;
    renderSummary();
  }

  function showTotal() {
    const line = els.summary.querySelector(".total");
    if (line) {
      line.innerHTML = `<strong>${state.autoMarks}</strong>`
        + `<span> of ${state.available} marks</span>`;
    }
    els.header.innerHTML =
      `<strong>${state.autoMarks}</strong> of ${state.available} marks`;
  }

  function renderSummary() {
    els.summary.hidden = false;
    els.summary.innerHTML = `
      <p class="label">${esc(state.label)} · Booklet A</p>
      <p class="total"></p>
      <p class="muted">Marked against ${esc(state.source || "the answer key")},
        not the official SEAB marking scheme.</p>`;
    const again = document.createElement("button");
    again.type = "button";
    again.textContent = "Try this booklet again";
    again.addEventListener("click", () => { clearAnswers(); start(state.paper, state.label); });
    els.summary.append(again);

    showTotal();
    els.finishBar.hidden = true;
    els.answers.scrollTop = 0;
  }

  function renderChooseResult(cardEl, result) {
    for (const button of cardEl.querySelectorAll(".option")) {
      const n = Number(button.dataset.choice);
      button.disabled = true;
      button.classList.toggle("correct", n === result.answer);
      button.classList.toggle("wrong", n === result.choice && !result.correct);
    }
    cardEl.classList.toggle("right", Boolean(result.correct));

    const why = result.explanation
      ? `<button class="why" type="button">Why?</button>
         <div class="explanation" hidden><h4>Why</h4><p>${esc(result.explanation)}</p></div>`
      : "";
    // A key the pipeline had to reconstruct is worth saying so about: it is
    // right far more often than not, but a confident "you were wrong" deserves
    // the caveat that the thing telling you so did not read the page cleanly.
    const caveat = result.answer_source
      ? `<div class="caveat">This answer was recovered from a poor scan rather
         than read cleanly. If you are sure you are right, check the answer page.</div>`
      : "";

    cardEl.querySelector(".mcq-feedback").innerHTML =
      `<p class="verdict ${result.correct ? "ok" : "no"}">`
      + `${result.correct ? "That's right!" : `The answer is option ${result.answer}`}`
      + ` <span class="muted">${result.marks}/${result.marks_total}</span></p>`
      + why + caveat;
    wireWhy(cardEl.querySelector(".mcq-feedback"));
  }

  function wireWhy(root) {
    const why = root.querySelector(".why");
    if (!why) return;
    why.addEventListener("click", () => {
      const box = root.querySelector(".explanation");
      box.hidden = !box.hidden;
      why.textContent = box.hidden ? "Why?" : "Hide why";
    });
  }

  /* ------------------------------------------------------------------ layout */

  function select(number) {
    for (const el of els.list.querySelectorAll(".mcq-card")) {
      el.classList.toggle("current", Number(el.dataset.question) === number);
    }
    els.jump.value = String(number);
  }

  function renderList() {
    els.list.innerHTML = "";
    for (const question of state.questions) {
      els.list.append(card(question));
    }
  }

  function applySplit(percent) {
    const value = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, percent));
    document.documentElement.style.setProperty("--mcq-split", `${value}%`);
    try { localStorage.setItem(SPLIT_KEY, String(value)); } catch { /* private */ }
  }

  function wireSplitter() {
    let saved = SPLIT_DEFAULT;
    try { saved = Number(localStorage.getItem(SPLIT_KEY)) || SPLIT_DEFAULT; }
    catch { /* private mode */ }
    applySplit(saved);

    let dragging = false;
    const main = els.splitter.parentElement;
    els.splitter.addEventListener("pointerdown", (event) => {
      dragging = true;
      els.splitter.setPointerCapture(event.pointerId);
    });
    els.splitter.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const rect = main.getBoundingClientRect();
      applySplit(((event.clientX - rect.left) / rect.width) * 100);
    });
    els.splitter.addEventListener("pointerup", () => { dragging = false; });
    els.splitter.addEventListener("dblclick", () => applySplit(SPLIT_DEFAULT));
    els.splitter.addEventListener("keydown", (event) => {
      const current = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--mcq-split"));
      if (event.key === "ArrowLeft") applySplit(current - 2);
      if (event.key === "ArrowRight") applySplit(current + 2);
    });
  }

  /* -------------------------------------------------------------------- boot */

  let wired = false;

  function wire() {
    if (wired) return;
    Object.assign(els, {
      root: document.getElementById("mcqPractice"),
      pages: document.getElementById("mcqPages"),
      paper: document.getElementById("mcqPaper"),
      answers: document.getElementById("mcqAnswers"),
      list: document.getElementById("mcqList"),
      summary: document.getElementById("mcqSummary"),
      title: document.getElementById("mcqTitle"),
      header: document.getElementById("mcqScore"),
      progress: document.getElementById("mcqProgress"),
      finish: document.getElementById("mcqFinish"),
      finishBar: document.getElementById("mcqFinishBar"),
      jump: document.getElementById("mcqJump"),
      zoomLabel: document.getElementById("mcqZoomLabel"),
      splitter: document.getElementById("mcqSplitter"),
    });
    els.jump.addEventListener("change", () => {
      const number = Number(els.jump.value);
      select(number);
      showCard(number);
      const entry = state.questions.find((q) => q.question === number);
      if (entry) showPage(entry.pages[0]);
    });
    els.finish.addEventListener("click", finishPaper);
    for (const button of document.querySelectorAll("[data-mcqzoom]")) {
      button.addEventListener("click", () =>
        setZoom(state.zoom + (button.dataset.mcqzoom === "in" ? 20 : -20)));
    }
    wireSplitter();
    wired = true;
  }

  async function start(paper, label) {
    wire();
    state.paper = paper;
    state.label = label || paper;
    state.results.clear();
    state.autoMarks = 0;
    state.source = "";
    state.finished = false;
    els.root.classList.remove("finished");
    els.summary.hidden = true;
    els.summary.innerHTML = "";
    els.finishBar.hidden = false;

    const data = await getJSON(`/api/mcq/papers/${paper}/questions`);
    state.questions = data.questions;
    state.pages = data.pages;
    state.pageSizes = data.page_sizes || [];
    loadAnswers();

    els.title.textContent = `Science ${state.label} · Booklet A`;
    els.jump.innerHTML = state.questions.map((q) =>
      `<option value="${q.question}">Q${q.question}</option>`
    ).join("");

    renderPages();
    renderList();
    setZoom(100);
    updateProgress();
    els.answers.scrollTop = 0;
    // No page jump on first paint: the images have no measured height yet, so it
    // would land near the top anyway. The cover is the right place to open.
    select(state.questions[0].question);
  }

  return { start };
})();
