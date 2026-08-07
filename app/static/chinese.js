"use strict";

/* Chinese Paper 2 practice.
 *
 * Science shows one question at a time, because each Booklet B question is a
 * self-contained block on its own page. Chinese cannot work that way: 短文填空
 * and 完成对话 put their questions INSIDE a passage, so Q16 is a blank in the
 * middle of a paragraph that Q17-Q20 also live in. Cropping to a question would
 * cut away the text it asks about. So the whole paper loads, the pages scroll on
 * one side, and every question's answer box sits on the other -- selecting one
 * scrolls the paper to its page rather than replacing what is shown.
 *
 * Nothing is marked until the paper is finished. Marking each answer as it is
 * given turns a 40-question paper into 40 little tests, and a running total in
 * the corner invites watching the number instead of reading the passage. So
 * answers are collected as they are given, and the marks arrive once, at the
 * end -- which is also how the real paper works.
 *
 * Three ways to answer, decided by the paper rather than by preference:
 *   choose       Q1-Q32, marked against the key, no API key needed.
 *   typed        Q34-Q40. Spoken Chinese cannot distinguish 熟悉 from its
 *                homophones and these marks depend on the exact characters.
 *   self_marked  Q33, whose marks are half holistic 语言 quality that the
 *                printed rubric does not decompose.
 */

const CN = (() => {
  const els = {};
  const state = {
    year: null, questions: [], sections: [], pageSizes: [], pages: 0, zoom: 100,
    answers: new Map(),   // question -> { choice } | { text }
    results: new Map(),     // question -> marked result, once finished
    selfMarks: new Map(),   // question -> marks the student awarded themselves
    autoMarks: 0,           // this run's computed total, before self-marks
    available: 0,
    finished: false,
  };

  const SECTION_HINT = {
    "语文应用": "Language use",
    "短文填空": "Cloze passage",
    "阅读理解一": "Comprehension 1",
    "完成对话": "Complete the dialogue",
    "阅读理解二": "Comprehension 2",
  };
  const GROUP_HINT = { A: "A组", B: "B组" };

  const SPLIT_KEY = "psle.cnSplitPercent";
  const SPLIT_MIN = 25, SPLIT_MAX = 70, SPLIT_DEFAULT = 50;
  // In-progress answers survive a reload. Forty questions is a long sitting to
  // lose to a stray refresh, and none of it is submitted until the end.
  const answersKey = (year) => `psle.cn.${year}.answers`;

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
      img.src = `/api/chinese/papers/${state.year}/pages/${page}`;
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

  /* ---------------------------------------------------------- stored answers */

  function saveAnswers() {
    try {
      localStorage.setItem(answersKey(state.year),
        JSON.stringify([...state.answers]));
    } catch { /* private mode */ }
  }

  function loadAnswers() {
    try {
      const raw = localStorage.getItem(answersKey(state.year));
      state.answers = new Map(raw ? JSON.parse(raw) : []);
    } catch { state.answers = new Map(); }
  }

  function clearAnswers() {
    try { localStorage.removeItem(answersKey(state.year)); } catch { /* private */ }
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

    if (question.response_mode === "choose") chooseWidget(question, body, el);
    else writtenWidget(question, body, el);
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

  function writtenWidget(question, body, cardEl) {
    const box = document.createElement("textarea");
    box.className = "cn-answer";
    box.rows = question.marks >= 4 ? 5 : 3;
    box.setAttribute("lang", "zh");
    box.placeholder = "用中文写下你的答案…";
    const saved = state.answers.get(question.question);
    if (saved && saved.text) {
      box.value = saved.text;
      cardEl.classList.add("answered");
    }
    box.addEventListener("input", () => {
      if (state.finished) return;
      const text = box.value.trim();
      if (text) state.answers.set(question.question, { text });
      else state.answers.delete(question.question);
      cardEl.classList.toggle("answered", Boolean(text));
      saveAnswers();
      updateProgress();
    });
    body.append(box);
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
        if (question.response_mode === "choose") {
          state.results.set(question.question, await postJSON(
            `/api/chinese/papers/${state.year}/answer/${question.question}`,
            { choice: given.choice }));
        } else if (question.response_mode === "typed") {
          state.results.set(question.question, await postJSON(
            `/api/chinese/papers/${state.year}/written/${question.question}`,
            { answer: given.text }));
        } else {
          // Self-marked: nothing to compute, only the model answer to show.
          state.results.set(question.question, { graded: false });
        }
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

      for (const box of cardEl.querySelectorAll("textarea")) box.readOnly = true;
      cardEl.classList.add("marked");
      const slot = cardEl.querySelector(".cn-feedback");

      if (!result) {
        slot.innerHTML = `<p class="muted">Not answered.</p>`;
        await showModel(question, cardEl);
        continue;
      }
      if (result.error) {
        slot.innerHTML = `<p class="error">${esc(result.error)}</p>`;
        continue;
      }
      if (typeof result.marks === "number") earned += result.marks;

      if (question.response_mode === "choose") renderChooseResult(cardEl, result);
      else await renderWrittenResult(question, cardEl, result);
    }
    state.autoMarks = earned;
    state.available = available;
    renderSummary();
  }

  function total() {
    let sum = state.autoMarks;
    for (const marks of state.selfMarks.values()) sum += marks;
    return sum;
  }

  function showTotal() {
    const line = els.summary.querySelector(".total");
    if (line) {
      line.innerHTML = `<strong>${total()}</strong>`
        + `<span> of ${state.available} marks</span>`;
    }
    els.header.innerHTML = `<strong>${total()}</strong> of ${state.available} marks`;
  }

  function renderSummary() {
    els.summary.hidden = false;
    els.summary.innerHTML = `
      <p class="label">${state.year} 试卷二</p>
      <p class="total"></p>
      <p class="muted">Marked against the EPH suggested answers — not the
        official SEAB marking scheme.</p>`;
    const again = document.createElement("button");
    again.type = "button";
    again.textContent = "Try this paper again";
    again.addEventListener("click", () => { clearAnswers(); start(state.year); });
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

  async function renderWrittenResult(question, cardEl, result) {
    const slot = cardEl.querySelector(".cn-feedback");
    if (!result.graded) {
      // Either self-marked by design (Q33) or the grader was unavailable. Both
      // end the same way: show the model answer and let the student award it.
      slot.innerHTML = result.reason
        ? `<p class="muted">Not marked automatically (${esc(result.reason)}).</p>`
        : `<p class="muted">Mark this one yourself against the answer below.</p>`;
      await showModel(question, cardEl, { selfMark: true });
      return;
    }
    const verdicts = result.verdicts || [];
    const hit = verdicts.filter((v) => v.status === "hit").length;
    const rows = verdicts.map((v) => `<li class="kp ${v.status}">`
      + `<span class="dot"></span>`
      + `<span>${esc(v.evidence || v.missing || "")}</span></li>`).join("");
    cardEl.classList.toggle("right", result.marks === result.marks_total);
    slot.innerHTML =
      `<p class="verdict ${result.marks === result.marks_total ? "ok" : "part"}">`
      + `${result.marks}/${result.marks_total}`
      + `<span class="muted"> · ${hit} of ${verdicts.length} points</span></p>`
      + (result.feedback ? `<p class="note">${esc(result.feedback)}</p>` : "")
      + (rows ? `<ul class="kps">${rows}</ul>` : "")
      + (result.model_answer
        ? `<details class="model"><summary>参考答案</summary>`
          + `<p>${esc(result.model_answer)}</p>`
          + (result.note ? `<p class="muted">${esc(result.note)}</p>` : "")
          + `</details>` : "");
  }

  async function showModel(question, cardEl, { selfMark = false } = {}) {
    if (question.response_mode === "choose") return;
    const slot = cardEl.querySelector(".cn-feedback");
    try {
      const model = await getJSON(
        `/api/chinese/papers/${state.year}/model/${question.question}`);
      const points = (model.keypoints || []).map((k) =>
        `<li><span class="kpmark">${k.marks}</span> ${esc(k.statement)}</li>`).join("");
      slot.insertAdjacentHTML("beforeend", `<div class="model open">`
        + `<p class="label">参考答案</p><p>${esc(model.model_answer)}</p>`
        + (model.note ? `<p class="muted">${esc(model.note)}</p>` : "")
        + (points ? `<ul class="kps points">${points}</ul>` : "")
        + (model.free_response
          ? `<p class="muted">这题答案合理即可 — your own view is fine if you explain it.</p>`
          : "")
        + (model.mark_scheme
          ? `<p class="muted">评分标准：${esc(model.mark_scheme)}</p>` : "")
        + `</div>`);
      if (selfMark) slot.append(selfMarkRow(question, cardEl));
    } catch (err) {
      slot.insertAdjacentHTML("beforeend", `<p class="error">${esc(err.message)}</p>`);
    }
  }

  function selfMarkRow(question, cardEl) {
    const row = document.createElement("div");
    row.className = "selfmark";
    row.innerHTML = `<span>How many marks did you earn?</span>`;
    for (let n = 0; n <= question.marks; n += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = String(n);
      button.addEventListener("click", async () => {
        const given = state.answers.get(question.question);
        try {
          await postJSON(
            `/api/chinese/papers/${state.year}/self-mark/${question.question}`,
            { marks: n, answer: given ? given.text || "" : "" });
          for (const other of row.querySelectorAll("button")) {
            other.classList.toggle("on", other === button);
          }
          cardEl.classList.toggle("right", n === question.marks);
          // Adjust this run's total rather than re-reading the log, which
          // returns the best attempt at each question across every sitting --
          // on a retake that is a different number from what is on screen.
          state.selfMarks.set(question.question, n);
          showTotal();
        } catch (err) {
          row.insertAdjacentHTML("beforeend",
            `<span class="error">${esc(err.message)}</span>`);
        }
      });
      row.append(button);
    }
    return row;
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
    let section = null, group = null;
    for (const question of state.questions) {
      if (question.section !== section || question.group !== group) {
        section = question.section;
        group = question.group;
        const head = document.createElement("h2");
        head.className = "cn-section";
        const hint = SECTION_HINT[section] || "";
        head.innerHTML = `${esc(section || "")}`
          + (group ? ` <span class="grp">${GROUP_HINT[group]}</span>` : "")
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

  async function start(year) {
    wire();
    state.year = year;
    state.results.clear();
    state.selfMarks.clear();
    state.autoMarks = 0;
    state.finished = false;
    els.root.classList.remove("finished");
    els.summary.hidden = true;
    els.summary.innerHTML = "";
    els.finishBar.hidden = false;

    const data = await getJSON(`/api/chinese/papers/${year}/questions`);
    state.questions = data.questions;
    state.pages = data.pages;
    state.pageSizes = data.page_sizes || [];
    state.sections = data.sections;
    loadAnswers();

    els.title.textContent = `华文 ${year} · 试卷二`;
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
