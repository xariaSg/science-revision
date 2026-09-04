"use strict";

/* English Paper 2 practice, one booklet at a time.
 *
 * The same screen shape as Chinese and for the same reason: most of this paper's
 * questions are blanks *inside* a passage. Booklet A's vocabulary cloze puts
 * Q16-Q20 in one paragraph and its visual text section asks Q21-Q25 about a
 * poster printed three pages earlier; the whole of Booklet B is cloze, editing
 * and sentence work over passages. Cropping to a question would cut away what it
 * asks about, so the booklet scrolls on one side and every answer sits on the
 * other.
 *
 * Nothing is marked until the booklet is finished. A running total in the corner
 * invites watching the number instead of reading the passage, and marking each
 * blank as it is typed turns a 40-question booklet into 40 little tests — the
 * argument CLAUDE.md 7.6 makes for Chinese, which applies here unchanged.
 *
 * Four ways to answer, decided by the paper rather than by preference:
 *   choose     Booklet A Q1-Q25 — options 1 to 4, marked against the key.
 *   letter     Booklet B Q26-Q35 — a letter from the printed word bank. The key
 *              prints "F (had)", so the letter and the word both count.
 *   word       Booklet B Q36-Q60 — one word into a blank, compared with the key.
 *              Spelling counts here, unlike anywhere else in this project: these
 *              are editing and cloze questions, so the word IS the answer.
 *   sentence   Booklet B Q61-Q65 — the sentence rewritten, self-marked against
 *              the model answer. There is no rubric for it, and CLAUDE.md 3 is
 *              explicit that inventing one teaches wrong English confidently.
 *
 * Booklet B's comprehension (Q66-Q75) is not built. Its pages are shown so the
 * paper is whole and the passage can be read, and its questions carry no answer
 * box rather than a box that leads nowhere.
 */

const EN = (() => {
  const els = {};
  const state = {
    paper: null, label: "", booklet: "A",
    questions: [], sections: [], pageSizes: [], first: 1, last: 1, zoom: 100,
    answers: new Map(),    // question -> { choice } | { text }
    results: new Map(),    // question -> marked result, once finished
    selfMarks: new Map(),  // question -> marks the student awarded themselves
    autoMarks: 0, available: 0, source: "", finished: false,
  };

  // What a section is called when the paper prints no name for it. Booklet A's
  // names come from the school's own key ("Grammar", "Vocab Cloze"); Booklet B
  // heads each section with an instruction and no title, so the mode names it.
  const MODE_LABEL = {
    choose: "Multiple choice",
    letter: "Cloze — choose a word from the list",
    word: "Fill in the blank",
    sentence: "Synthesis and transformation",
    not_built: "Comprehension",
  };
  const SPLIT_KEY = "psle.enSplitPercent";
  const SPLIT_MIN = 25, SPLIT_MAX = 70, SPLIT_DEFAULT = 50;
  // In-progress answers survive a reload: a booklet is a long sitting to lose to
  // a stray refresh, and none of it is submitted until the end.
  const answersKey = (paper, booklet) => `psle.en.${paper}.${booklet}.answers`;

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
  const apiRoot = () =>
    `/api/english/papers/${state.paper}/booklet-${state.booklet}`;
  const answerable = (question) => question.response_mode !== "not_built";

  /* ------------------------------------------------------------------ pages */

  function renderPages() {
    els.pages.innerHTML = "";
    const sizes = new Map((state.pageSizes || []).map((p) => [p.page, p]));
    for (let page = state.first; page <= state.last; page += 1) {
      const wrap = document.createElement("div");
      wrap.className = "en-page";
      wrap.dataset.page = String(page);
      const img = new Image();
      // The intrinsic size must be set before the src, so the browser reserves
      // the page's height while the image is unloaded. Without it every lazy
      // page is zero-high and "jump to Q21" lands near the top.
      const size = sizes.get(page);
      if (size) { img.width = size.width; img.height = size.height; }
      img.src = `${apiRoot()}/pages/${page}`;
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
    const target = els.pages.querySelector(`.en-page[data-page="${page}"]`);
    if (!target) return;
    // Assigned rather than animated: a booklet page can be 10,000px down and
    // smooth scrolling is both a long ride and silently ignored by some engines
    // on a nested scroller.
    els.pages.scrollTop = target.offsetTop - els.pages.offsetTop - 8;
  }

  // Jumping to a question from the dropdown is only half done if the paper
  // scrolls and the answer pane does not -- the student picked Q40 to see and
  // answer it, not just to see its page. #enAnswers is the scroller and
  // `position: relative` in the stylesheet makes it the card's offsetParent,
  // the same trick showPage() above uses for the paper pane.
  function showCard(number) {
    const target = els.list.querySelector(`.en-card[data-question="${number}"]`);
    if (!target) return;
    els.answers.scrollTop = target.offsetTop - els.answers.offsetTop - 8;
  }

  /* ---------------------------------------------------------- stored answers */

  function saveAnswers() {
    try {
      localStorage.setItem(answersKey(state.paper, state.booklet),
        JSON.stringify([...state.answers]));
    } catch { /* private mode */ }
  }

  function loadAnswers() {
    try {
      const raw = localStorage.getItem(answersKey(state.paper, state.booklet));
      state.answers = new Map(raw ? JSON.parse(raw) : []);
    } catch { state.answers = new Map(); }
  }

  function clearAnswers() {
    try { localStorage.removeItem(answersKey(state.paper, state.booklet)); }
    catch { /* private mode */ }
  }

  /* ------------------------------------------------------------ answer cards */

  function card(question) {
    const el = document.createElement("article");
    el.className = `card en-card mode-${question.response_mode}`;
    el.dataset.question = String(question.question);
    const pages = question.pages || [];
    el.dataset.page = String(pages[0] || state.first);

    // Every page this question needs, the stimulus first. Q21-Q25 are about a
    // poster and an article printed three pages before the questions, so a link
    // to the question's own page alone would send the student to a page they
    // cannot answer from.
    const jumps = [...(question.context_pages || []), ...pages]
      .map((page) => `<button class="linkbtn tiny" type="button" `
        + `data-goto="${page}">page ${page}</button>`).join("");

    const head = document.createElement("header");
    head.className = "en-card-head";
    head.innerHTML = `<h3>Q${question.question}</h3>`
      + (question.marks ? `<span class="marks">${marksLabel(question.marks)}</span>` : "")
      + jumps;
    el.append(head);

    const body = document.createElement("div");
    body.className = "en-card-body";
    el.append(body);

    if (question.response_mode === "choose") {
      chooseWidget(question, body, el);
    } else {
      typedWidget(question, body, el);
    }
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
        // Selection only. Nothing is marked until the booklet is finished, so
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

  function typedWidget(question, body, cardEl) {
    const sentence = question.response_mode === "sentence";
    // A one-word answer gets a one-line box and a sentence gets a textarea: the
    // shape of the box is the clearest thing on screen saying how much to write.
    const box = document.createElement(sentence ? "textarea" : "input");
    box.className = sentence ? "en-answer" : "en-answer one-line";
    if (sentence) box.rows = 3; else box.type = "text";
    box.setAttribute("autocapitalize", "off");
    box.setAttribute("spellcheck", "false");
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
    slot.className = "en-feedback";
    return slot;
  }

  /* -------------------------------------------------------------- finishing */

  const slots = () => state.questions.filter(answerable);

  function answeredCount() {
    return slots().filter((q) => state.answers.has(q.question)).length;
  }

  function updateProgress() {
    if (state.finished) return;
    const done = answeredCount();
    const total = slots().length;
    els.progress.textContent = `${done} of ${total} answered`;
    els.header.textContent = `${done} of ${total} answered`;
    els.finish.disabled = done === 0;
  }

  async function finishPaper() {
    const left = slots().length - answeredCount();
    if (left && !window.confirm(
      `${left} question${left === 1 ? " is" : "s are"} still blank. `
      + "Finish and mark the booklet anyway?")) return;

    state.finished = true;
    els.finish.disabled = true;
    els.root.classList.add("finished");
    els.progress.textContent = "Marking…";

    // One request for the whole booklet rather than one per question: the paper
    // is marked once at the end, and the attempt log should read the way the
    // sitting happened.
    const payload = {};
    for (const question of slots()) {
      const given = state.answers.get(question.question);
      if (!given) continue;
      payload[question.question] =
        question.response_mode === "choose" ? given.choice : given.text;
    }
    try {
      const marked = await postJSON(`${apiRoot()}/submit`, { answers: payload });
      state.source = marked.source || "";
      for (const row of marked.results) state.results.set(row.question, row);
    } catch (err) {
      els.progress.textContent = "";
      els.summary.hidden = false;
      els.summary.innerHTML = `<p class="label">Could not mark it</p>`
        + `<p class="muted">${esc(err.message)}</p>`;
      state.finished = false;
      els.finish.disabled = false;
      els.root.classList.remove("finished");
      return;
    }
    els.progress.textContent = "";
    renderResults();
  }

  function renderResults() {
    let earned = 0, available = 0;
    for (const question of slots()) {
      available += question.marks || 0;
      const cardEl = els.list.querySelector(
        `.en-card[data-question="${question.question}"]`);
      if (!cardEl) continue;
      for (const box of cardEl.querySelectorAll("input, textarea")) {
        box.readOnly = true;
      }
      cardEl.classList.add("marked");
      const slot = cardEl.querySelector(".en-feedback");
      const result = state.results.get(question.question);

      if (!result) {
        slot.innerHTML = `<p class="muted">Not answered.</p>`;
        continue;
      }
      if (typeof result.marks === "number") earned += result.marks;
      if (question.response_mode === "choose") renderChooseResult(cardEl, result);
      else renderTypedResult(question, cardEl, result);
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
      <p class="label">${esc(state.label)} · Booklet ${state.booklet}</p>
      <p class="total"></p>
      <p class="muted">Marked against ${esc(state.source || "the school's answer key")}
        — a school's own answers, not an official marking scheme.</p>`;
    const again = document.createElement("button");
    again.type = "button";
    again.textContent = "Try this booklet again";
    again.addEventListener("click", () => {
      clearAnswers();
      start(state.paper, state.booklet, state.label);
    });
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
      button.classList.toggle("wrong", n === result.chose && !result.correct);
    }
    cardEl.classList.toggle("right", Boolean(result.correct));
    cardEl.querySelector(".en-feedback").innerHTML =
      `<p class="verdict ${result.correct ? "ok" : "no"}">`
      + `${result.correct ? "That's right!" : `The answer is option ${result.answer}`}`
      + ` <span class="muted">${result.marks}/${result.marks_total}</span></p>`;
  }

  function renderTypedResult(question, cardEl, result) {
    const slot = cardEl.querySelector(".en-feedback");
    if (question.response_mode === "sentence") {
      // Self-marked: there is no rubric for a transformed sentence, so the model
      // answer is shown and the student awards the marks. The same footing every
      // un-authored written question in this project is on (CLAUDE.md 10.5).
      slot.innerHTML = `<p class="muted">Compare yours with the answer below, `
        + `then give yourself the marks.</p>`
        + `<div class="model open"><p class="label">Suggested answer</p>`
        + `<p>${esc(result.model_answer || "not extracted for this one")}</p></div>`;
      slot.append(selfMarkRow(question, cardEl));
      return;
    }
    const expected = (result.expected || []).map(esc).join("</b> or <b>");
    cardEl.classList.toggle("right", Boolean(result.correct));
    slot.innerHTML =
      `<p class="verdict ${result.correct ? "ok" : "no"}">`
      + `${result.correct ? "That's right!" : `The answer is <b>${expected}</b>`}`
      + ` <span class="muted">${result.marks}/${result.marks_total}</span></p>`
      + (result.note ? `<p class="note">${esc(result.note)}</p>` : "");
  }

  function selfMarkRow(question, cardEl) {
    const row = document.createElement("div");
    row.className = "selfmark";
    row.innerHTML = `<span>How many marks did you earn?</span>`;
    for (let n = 0; n <= (question.marks || 0); n += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = String(n);
      button.addEventListener("click", async () => {
        const given = state.answers.get(question.question);
        try {
          await postJSON(`${apiRoot()}/self-mark/${question.question}`,
            { marks: n, answer: given ? given.text || "" : "" });
          for (const other of row.querySelectorAll("button")) {
            other.classList.toggle("on", other === button);
          }
          cardEl.classList.toggle("right", n === question.marks);
          // This run's total is adjusted rather than re-read from the log, which
          // returns the best attempt across every sitting — on a retake that is
          // a different number from the one on screen.
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
    for (const el of els.list.querySelectorAll(".en-card")) {
      el.classList.toggle("current", Number(el.dataset.question) === number);
    }
    els.jump.value = String(number);
  }

  // The paper's own instruction, under the section's name. Booklet B has two
  // sections that are both "fill in a blank" — editing and comprehension cloze —
  // and nothing but their printed wording tells them apart, so the wording is
  // shown rather than replaced by a label of our own. Booklet A's names come
  // from the school's key; Booklet B prints none, so the mode names it.
  function sectionTitle(section) {
    const range = `Q${section.first}–${section.last}`;
    const name = section.name || MODE_LABEL[section.response_mode] || "";
    const marks = section.marks ? `${section.marks} marks` : "";
    // The instruction ends with its own mark total, which the header already
    // shows on its own; repeating it inside the sentence just crowds the line.
    const instruction = (section.instruction || "")
      .replace(/[([{]\s*\d{1,3}\s+marks?\s*[)\]}]/i, "").trim();
    return `<span>${esc(name || range)}</span>`
      + `<span class="grp">${esc(name ? range : "")}</span>`
      + (marks ? `<span class="hint">${esc(marks)}</span>` : "")
      + (instruction ? `<span class="instruction">${esc(instruction)}</span>` : "");
  }

  // Only the sections this app marks. Booklet B's comprehension is answered in
  // tables and explanations that nothing here can mark (build/en_index_b.py), and
  // a run of cards saying so is ten rows of apology between the student and the
  // work they can actually do. Its pages stay in the paper pane -- the booklet is
  // still the booklet, and the passage is worth reading -- but it is not offered
  // as something to answer here.
  function renderList() {
    els.list.innerHTML = "";
    let current = null;
    for (const question of slots()) {
      if (question.section !== current) {
        current = question.section;
        const section = state.sections[current];
        if (section) {
          const head = document.createElement("h2");
          head.className = "en-section";
          head.innerHTML = sectionTitle(section);
          els.list.append(head);
        }
      }
      els.list.append(card(question));
    }
    const skipped = state.sections.filter(
      (s) => s.response_mode === "not_built");
    if (skipped.length) {
      const note = document.createElement("p");
      note.className = "en-skipped";
      note.innerHTML = skipped.map((s) =>
        `Q${s.first}–${s.last} (${esc(s.name || MODE_LABEL[s.response_mode]
          || "")}, ${s.marks} marks) is not marked here — it is on `
        + `page${s.pages.length === 1 ? "" : "s"} `
        + s.pages.map((page) => `<button class="linkbtn tiny" type="button" `
          + `data-goto="${page}">${page}</button>`).join(", ")
        + ` to read and answer on paper.`).join("<br>");
      note.addEventListener("click", (event) => {
        const goto = event.target.closest("[data-goto]");
        if (goto) showPage(Number(goto.dataset.goto));
      });
      els.list.append(note);
    }
  }

  function applySplit(percent) {
    const value = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, percent));
    document.documentElement.style.setProperty("--en-split", `${value}%`);
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
        getComputedStyle(document.documentElement).getPropertyValue("--en-split"));
      if (event.key === "ArrowLeft") applySplit(current - 2);
      if (event.key === "ArrowRight") applySplit(current + 2);
    });
  }

  /* -------------------------------------------------------------------- boot */

  let wired = false;

  function wire() {
    if (wired) return;
    Object.assign(els, {
      root: document.getElementById("enPractice"),
      pages: document.getElementById("enPages"),
      paper: document.getElementById("enPaper"),
      answers: document.getElementById("enAnswers"),
      list: document.getElementById("enList"),
      summary: document.getElementById("enSummary"),
      title: document.getElementById("enTitle"),
      header: document.getElementById("enScore"),
      progress: document.getElementById("enProgress"),
      finish: document.getElementById("enFinish"),
      finishBar: document.getElementById("enFinishBar"),
      jump: document.getElementById("enJump"),
      zoomLabel: document.getElementById("enZoomLabel"),
      splitter: document.getElementById("enSplitter"),
    });
    els.jump.addEventListener("change", () => {
      const number = Number(els.jump.value);
      select(number);
      showCard(number);
      const entry = state.questions.find((q) => q.question === number);
      if (!entry) return;
      const pages = [...(entry.context_pages || []), ...(entry.pages || [])];
      if (pages.length) showPage(pages[0]);
    });
    els.finish.addEventListener("click", finishPaper);
    for (const button of document.querySelectorAll("[data-enzoom]")) {
      button.addEventListener("click", () =>
        setZoom(state.zoom + (button.dataset.enzoom === "in" ? 20 : -20)));
    }
    wireSplitter();
    wired = true;
  }

  async function start(paper, booklet, label) {
    wire();
    state.paper = paper;
    state.booklet = booklet;
    state.label = label || paper;
    state.results.clear();
    state.selfMarks.clear();
    state.autoMarks = 0;
    state.finished = false;
    els.root.classList.remove("finished");
    els.summary.hidden = true;
    els.summary.innerHTML = "";
    els.finishBar.hidden = false;

    const data = await getJSON(`${apiRoot()}/questions`);
    state.questions = data.questions;
    state.sections = data.sections;
    state.pageSizes = data.page_sizes || [];
    state.first = data.pages.first;
    state.last = data.pages.last;
    loadAnswers();

    els.title.textContent =
      `English ${state.label} · Paper 2 Booklet ${booklet}`;
    els.jump.innerHTML = slots().map((q) => {
      const section = state.sections[q.section] || {};
      const name = section.name || MODE_LABEL[q.response_mode] || "";
      return `<option value="${q.question}">Q${q.question} — ${esc(name)}</option>`;
    }).join("");

    renderPages();
    renderList();
    setZoom(100);
    updateProgress();
    els.answers.scrollTop = 0;
    // No page jump on first paint: the images have no measured height yet, so it
    // would land near the top anyway.
    const first = slots()[0];
    if (first) select(first.question);
  }

  return { start };
})();
