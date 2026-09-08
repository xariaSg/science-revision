"use strict";

/* Chinese Paper 2 practice, scoped to Booklet A.
 *
 * Science shows one question at a time, because each Booklet B question is a
 * self-contained block on its own page. Chinese cannot work that way: 短文填空
 * puts its questions INSIDE a passage, so Q16 is a blank in the middle of a
 * paragraph that Q17-Q20 also live in. Cropping to a question would cut away
 * the text it asks about. So the paper loads, the pages scroll on one side,
 * and every question's answer box sits on the other -- selecting one scrolls
 * the paper to its page rather than replacing what is shown.
 *
 * Nothing is marked until the paper is finished. Marking each answer as it is
 * given turns a 20-odd-question paper into 20 little tests, and a running
 * total in the corner invites watching the number instead of reading the
 * passage. So answers are collected as they are given, and the marks arrive
 * once, at the end -- which is also how the real paper works.
 *
 * Every question here is `choose`: the server (app/chinese.py) only ever
 * serves Booklet A, the paper's own OAS-answered sections (语文应用, 短文填空,
 * 阅读理解一) -- marked against the key, no API key needed. 完成对话 and
 * 阅读理解二 are past that seam and are never sent to this screen.
 */

const CN = (() => {
  const els = {};
  const state = {
    paper: null, label: null, questions: [], sections: [], pageSizes: [], pages: 0,
    zoom: 100,
    answers: new Map(),   // question -> { choice }
    results: new Map(),     // question -> marked result, once finished
    autoMarks: 0,           // this run's computed total
    available: 0,
    finished: false,
  };

  const SECTION_HINT = {
    "语文应用": "Language use",
    "短文填空": "Cloze passage",
    "阅读理解一": "Comprehension 1",
  };

  const SPLIT_KEY = "psle.cnSplitPercent";
  const SPLIT_MIN = 25, SPLIT_MAX = 70, SPLIT_DEFAULT = 50;
  // In-progress answers survive a reload. A stray refresh mid-booklet
  // shouldn't cost the sitting, and none of it is submitted until the end.
  const answersKey = (paper) => `psle.cn.${paper}.answers`;

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

  const marksLabel = (n) => (n === 1 ? "1 mark" : `${n} marks`);

  /* ------------------------------------------------------------------ pages */

  function renderPages() {
    els.pages.innerHTML = "";
    const sizes = new Map((state.pageSizes || []).map((p) => [p.page, p]));
    for (let page = 1; page <= state.pages; page += 1) {
      const wrap = document.createElement("div");
      wrap.className = "cn-page";
      wrap.dataset.page = String(page);
      const img = new Image();
      // The intrinsic size must be set before the src, so the browser reserves
      // the page's height while the image is still unloaded. Without it every
      // lazy page is zero-high and "jump to page 15" lands near the top.
      const size = sizes.get(page);
      if (size) { img.width = size.width; img.height = size.height; }
      img.src = `/api/chinese/papers/${state.paper}/pages/${page}`;
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
    const target = els.pages.querySelector(`.cn-page[data-page="${page}"]`);
    if (!target) return;
    // #cnPages is the scroller, but #cnPaper is the positioned ancestor both
    // offsetTops are measured from, so the difference is the offset within the
    // scroller. Scrolling #cnPaper instead does nothing -- it never overflows.
    //
    // Assigned rather than scrollTo({behavior:"smooth"}), which some engines
    // ignore entirely on a nested scroller -- the jump silently did nothing. A
    // paper jump is better instant regardless: page 15 is 12,000px down, and
    // animating that is a long ride past fourteen pages of answers.
    els.pages.scrollTop = target.offsetTop - els.pages.offsetTop - 8;
  }

  // Jumping to a question from the dropdown is only half done if the paper
  // scrolls and the answer pane does not -- the student picked Q40 to see and
  // answer it, not just to see its page. #cnAnswers is the scroller and
  // `position: relative` in the stylesheet makes it the card's offsetParent,
  // the same trick showPage() above uses for the paper pane's #cnPaper.
  function showCard(number) {
    const target = els.list.querySelector(`.cn-card[data-question="${number}"]`);
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
    el.className = `card cn-card mode-${question.response_mode}`;
    el.dataset.question = String(question.question);
    el.dataset.page = String(question.page);

    const head = document.createElement("header");
    head.className = "cn-card-head";
    // The allocation stays visible: it is printed on the scan right beside this,
    // and it is what tells the student how much to write. It is the *score* that
    // is held back until the end, not the question's own shape.
    head.innerHTML = `<h3>Q${question.question}</h3>`
      + `<span class="marks">${marksLabel(question.marks)}</span>`
      + `<button class="linkbtn tiny" type="button" data-goto="${question.page}">`
      + `page ${question.page}</button>`;
    el.append(head);

    const body = document.createElement("div");
    body.className = "cn-card-body";
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
    for (let n = 1; n <= (question.options || 4); n += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "option";
      button.dataset.choice = String(n);
      button.textContent = String(n);
      if (saved && saved.choice === n) button.classList.add("chosen");
      button.addEventListener("click", () => {
        if (state.finished) return;
        // Selection only. Nothing is marked until the paper is finished, so
        // picking again is changing your mind, not a second attempt.
        state.answers.set(question.question, { choice: n });
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
    slot.className = "cn-feedback";
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
      const given = state.answers.get(question.question);
      try {
        state.results.set(question.question, await postJSON(
          `/api/chinese/papers/${state.paper}/answer/${question.question}`,
          { choice: given.choice }));
      } catch (err) {
        state.results.set(question.question, { error: err.message });
      }
      done += 1;
    }

    els.progress.textContent = "";
    await renderResults();
  }

  async function renderResults() {
    let earned = 0, available = 0;
    for (const question of state.questions) {
      available += question.marks || 0;
      const result = state.results.get(question.question);
      const cardEl = els.list.querySelector(
        `.cn-card[data-question="${question.question}"]`);
      if (!cardEl) continue;

      cardEl.classList.add("marked");
      const slot = cardEl.querySelector(".cn-feedback");

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
      <p class="label">${esc(state.label)} 试卷二</p>
      <p class="total"></p>
      <p class="muted">Marked against the EPH suggested answers — not the
        official SEAB marking scheme.</p>`;
    const again = document.createElement("button");
    again.type = "button";
    again.textContent = "Try this paper again";
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
    cardEl.querySelector(".cn-feedback").innerHTML =
      `<p class="verdict ${result.correct ? "ok" : "no"}">`
      + `${result.correct ? "对了！" : `答案是（${result.answer}）`}`
      + ` <span class="muted">${result.marks}/${result.marks_total}</span></p>`
      + (result.note ? `<p class="note">${esc(result.note)}</p>` : "");
  }

  /* ------------------------------------------------------------------ layout */

  function select(number) {
    for (const el of els.list.querySelectorAll(".cn-card")) {
      el.classList.toggle("current", Number(el.dataset.question) === number);
    }
    els.jump.value = String(number);
  }

  function renderList() {
    els.list.innerHTML = "";
    // Booklet A never groups a section (that's 阅读理解二's A组/B组, past the
    // seam this screen never sees), so the section name alone marks a new head.
    let section = null;
    for (const question of state.questions) {
      if (question.section !== section) {
        section = question.section;
        const head = document.createElement("h2");
        head.className = "cn-section";
        const hint = SECTION_HINT[section] || "";
        head.innerHTML = `${esc(section || "")}`
          + (hint ? `<span class="hint">${esc(hint)}</span>` : "");
        els.list.append(head);
      }
      els.list.append(card(question));
    }
  }

  function applySplit(percent) {
    const value = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, percent));
    document.documentElement.style.setProperty("--cn-split", `${value}%`);
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
        getComputedStyle(document.documentElement).getPropertyValue("--cn-split"));
      if (event.key === "ArrowLeft") applySplit(current - 2);
      if (event.key === "ArrowRight") applySplit(current + 2);
    });
  }

  /* -------------------------------------------------------------------- boot */

  let wired = false;

  function wire() {
    if (wired) return;
    Object.assign(els, {
      root: document.getElementById("cnPractice"),
      pages: document.getElementById("cnPages"),
      paper: document.getElementById("cnPaper"),
      answers: document.getElementById("cnAnswers"),
      list: document.getElementById("cnList"),
      summary: document.getElementById("cnSummary"),
      title: document.getElementById("cnTitle"),
      header: document.getElementById("cnScore"),
      progress: document.getElementById("cnProgress"),
      finish: document.getElementById("cnFinish"),
      finishBar: document.getElementById("cnFinishBar"),
      jump: document.getElementById("cnJump"),
      zoomLabel: document.getElementById("cnZoomLabel"),
      splitter: document.getElementById("cnSplitter"),
    });
    els.jump.addEventListener("change", () => {
      const number = Number(els.jump.value);
      select(number);
      showCard(number);
      const entry = state.questions.find((q) => q.question === number);
      if (entry) showPage(entry.page);
    });
    els.finish.addEventListener("click", finishPaper);
    for (const button of document.querySelectorAll("[data-cnzoom]")) {
      button.addEventListener("click", () =>
        setZoom(state.zoom + (button.dataset.cnzoom === "in" ? 20 : -20)));
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
    state.finished = false;
    els.root.classList.remove("finished");
    els.summary.hidden = true;
    els.summary.innerHTML = "";
    els.finishBar.hidden = false;

    const data = await getJSON(`/api/chinese/papers/${paper}/questions`);
    state.questions = data.questions;
    state.pages = data.pages;
    state.pageSizes = data.page_sizes || [];
    state.sections = data.sections;
    loadAnswers();

    els.title.textContent = `华文 ${state.label} · 试卷二`;
    els.jump.innerHTML = state.questions.map((q) =>
      `<option value="${q.question}">Q${q.question} — ${q.section || ""}</option>`
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
