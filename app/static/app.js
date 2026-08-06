"use strict";

const els = {
  year: document.getElementById("year"),
  question: document.getElementById("question"),
  prev: document.getElementById("prev"),
  next: document.getElementById("next"),
  pages: document.getElementById("pages"),
  parts: document.getElementById("parts"),
  answerHead: document.getElementById("answerHead"),
  zoomLabel: document.getElementById("zoomLabel"),
  splitter: document.getElementById("splitter"),
};

const state = { year: null, questions: [], index: 0, zoom: 100, grading: false };

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const current = () => state.questions[state.index];

function marksLabel(part) {
  if (part.marks === null) return "marks unknown";
  return part.marks === 1 ? "1 mark" : `${part.marks} marks`;
}

/* ---------------------------------------------------------------- rendering */

function renderPages() {
  const question = current();
  els.pages.innerHTML = "";
  if (!question) return;
  for (const page of question.pages) {
    const img = new Image();
    img.src = `/api/papers/${state.year}/pages/${page}`;
    img.alt = `Page ${page}`;
    img.style.width = `${state.zoom}%`;
    els.pages.append(img);
  }
  els.pages.scrollTop = 0;
}

function setZoom(next) {
  state.zoom = Math.min(320, Math.max(60, next));
  els.zoomLabel.textContent = state.zoom === 100 ? "Fit" : `${state.zoom}%`;
  for (const img of els.pages.querySelectorAll("img")) {
    img.style.width = `${state.zoom}%`;
  }
}

function renderQuestion() {
  const question = current();
  els.parts.innerHTML = "";
  if (!question) {
    els.answerHead.innerHTML = "";
    els.parts.innerHTML = `<p class="empty">No questions indexed for this paper.</p>`;
    return;
  }

  const total = question.total_marks;
  els.answerHead.innerHTML = `
    <h2>Question ${question.question}</h2>
    <div class="meta">${question.parts.length} part${question.parts.length === 1 ? "" : "s"}
      &middot; ${total} mark${total === 1 ? "" : "s"} total
      &middot; page ${question.pages.join(", ")}</div>`;

  question.parts.forEach((part, i) => els.parts.append(partCard(question, part, i)));

  const totalCard = document.createElement("div");
  totalCard.className = "papertotal";
  totalCard.id = "papertotal";
  els.parts.append(totalCard);
  refreshScore();
}

// Paper total, from the attempt log rather than this session, so it survives a
// reload and reflects the best attempt at each sub-part.
async function refreshScore() {
  const el = document.getElementById("papertotal");
  if (!el || !state.year) return;
  try {
    const s = await getJSON(`/api/papers/${state.year}/score`);
    const pct = s.available ? Math.round((s.earned / s.available) * 100) : 0;
    const done = s.slots ? Math.round((s.attempted / s.slots) * 100) : 0;
    el.innerHTML = `
      <div class="pt-head">${state.year} paper total</div>
      <div class="pt-score">${s.earned} <span>/ ${s.available}</span></div>
      <div class="pt-bar"><div class="pt-fill" style="width:${pct}%"></div></div>
      <div class="pt-meta">${s.attempted} of ${s.slots} parts attempted (${done}%)</div>`;
  } catch {
    el.innerHTML = "";
  }
}

function partCard(question, part, index) {
  const card = document.createElement("div");
  card.className = "part";

  // Parts are stored flat ("a", "b(i)"); print them as the paper does.
  const label = !part.part ? "Answer"
    : part.part.includes("(") ? `(${part.part.replace("(", ")(")}`
    : `(${part.part})`;
  card.innerHTML = `
    <div class="part-head">
      <span class="part-label">${label}</span>
      <span class="marks${part.uncertain ? " uncertain" : ""}">${marksLabel(part)}${
        part.uncertain ? " — check the page" : ""}</span>
    </div>
    <div class="controls">
      <button class="rec" type="button" data-state="idle">Record</button>
      <span class="status"></span>
    </div>
    <textarea placeholder="Say your answer, or type it here."></textarea>
    <p class="hint">Whisper can mishear science words — read the transcript and fix it before you mark yourself.</p>
    <div class="controls" style="margin-top:10px">
      ${state.grading && !part.drawn
        ? `<button class="mark" type="button">Mark my answer</button>` : ""}
      <button class="save" type="button">Save attempt</button>
      <button class="reveal" type="button">Reveal model answer</button>
      <span class="saved status"></span>
    </div>
    <div class="feedback" hidden></div>
    <div class="model" hidden></div>`;

  const feedback = card.querySelector(".feedback");
  const rec = card.querySelector(".rec");
  const status = card.querySelector(".status");
  const box = card.querySelector("textarea");
  const model = card.querySelector(".model");
  const saved = card.querySelector(".saved");
  let rawTranscript = null;
  let selfMark = null;

  wireRecorder(rec, status, box, (text) => { rawTranscript = text; });

  card.querySelector(".reveal").addEventListener("click", async () => {
    if (!model.hidden) { model.hidden = true; return; }
    model.hidden = false;
    model.innerHTML = `<h4>Suggested answer</h4><p>Loading…</p>`;
    try {
      const data = await getJSON(
        `/api/papers/${state.year}/answers/${question.question}`);
      const match = data.parts.find((p) => p.part === part.part)
        || data.parts[index] || null;
      if (!match) {
        model.innerHTML = `<h4>Suggested answer</h4>
          <p>No answer was extracted for this part — check the answer pages yourself.</p>`;
        return;
      }
      // Text, not a crop of the answer page. The crop was right while the OCR
      // text was an unreliable draft; the Vision extraction that replaced it is
      // accurate, and text reflows, is selectable, and separates the two fields.
      model.innerHTML = `<h4>Suggested answer</h4>
        <p class="answer-text">${match.text || "<em>none extracted</em>"}</p>
        ${match.flagged
          ? `<div class="caveat">This answer is flagged as doubtful${
              match.flag_reason ? `: ${match.flag_reason}` : ""}.</div>`
          : ""}
        ${match.explanation
          ? `<button class="why" type="button">Why?</button>
             <div class="explanation" hidden>
               <h4>Why</h4><p>${match.explanation}</p>
             </div>` : ""}
        <div class="caveat">This is a publisher's suggested answer, not the official
        SEAB marking scheme. If your wording differs but your science is right,
        you may still have the mark.</div>`;

      // The explanation teaches the principle; it is held back so the student
      // reads the answer and marks themselves first (CLAUDE.md 1.5).
      const why = model.querySelector(".why");
      if (why) {
        why.addEventListener("click", () => {
          const box = model.querySelector(".explanation");
          box.hidden = !box.hidden;
          why.textContent = box.hidden ? "Why?" : "Hide why";
        });
      }
      model.append(selfMarkRow(part, (value) => { selfMark = value; }, card));
      model.append(flagRow(question, part));
      card.classList.add("done");
    } catch (err) {
      model.innerHTML = `<h4>Suggested answer</h4><p>Could not load it: ${err.message}</p>`;
    }
  });

  const markBtn = card.querySelector(".mark");
  if (markBtn) {
    markBtn.addEventListener("click", async () => {
      const answer = box.value.trim();
      if (!answer) { saved.textContent = "Say or type your answer first."; return; }
      markBtn.disabled = true;
      feedback.hidden = false;
      feedback.innerHTML = `<p class="marking">Marking…</p>`;
      try {
        const res = await fetch(
          `/api/grade/${state.year}/${question.question}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ part: part.part, answer }),
          });
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
        const result = await res.json();
        selfMark = result.marks_awarded;
        feedback.innerHTML = feedbackHTML(result);
        markCorrect(card, result.marks_awarded, result.marks_total);
        wireCollapse(feedback);
        refreshScore();
      } catch (err) {
        feedback.innerHTML =
          `<p class="caveat">Could not mark it: ${err.message}. ` +
          `You can still reveal the answer and mark yourself.</p>`;
      } finally {
        markBtn.disabled = false;
      }
    });
  }

  card.querySelector(".save").addEventListener("click", async () => {
    const answer = box.value.trim();
    if (!answer) { saved.textContent = "Nothing to save yet."; return; }
    saved.textContent = "Saving…";
    try {
      await fetch("/api/attempts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          year: state.year, question: question.question, part: part.part,
          mode: rawTranscript ? "voice" : "typed",
          answer, transcript: rawTranscript,
          marks: selfMark, marks_total: part.marks,
        }),
      });
      saved.textContent = "Saved.";
    } catch (err) {
      saved.textContent = `Could not save: ${err.message}`;
    }
  });

  return card;
}

// A full-marks answer gets a tick on the card itself, so a scan down the column
// shows what is done without opening each one.
function markCorrect(card, awarded, total) {
  const correct = total > 0 && awarded === total;
  card.classList.toggle("correct", correct);
  let badge = card.querySelector(".part-head .tickbadge");
  if (correct && !badge) {
    badge = document.createElement("span");
    badge.className = "tickbadge";
    badge.textContent = "✓";
    badge.title = "Full marks";
    card.querySelector(".part-head").append(badge);
  } else if (!correct && badge) {
    badge.remove();
  }
}

function wireCollapse(feedback) {
  const toggle = feedback.querySelector(".fbtoggle");
  const body = feedback.querySelector(".fbbody");
  if (!toggle || !body) return;
  toggle.addEventListener("click", () => {
    body.hidden = !body.hidden;
    toggle.textContent = body.hidden ? "Show details" : "Hide details";
  });
}

// The chain rendered against the student's own reasoning, with the break shown at
// the exact link where it stopped. Seeing your own arrow stop short teaches the
// habit better than any prose comment does.
function feedbackHTML(result) {
  const gateFailed = !result.context_gate.passed;

  const gate = gateFailed
    ? `<div class="gate">
         <strong>This reads as a textbook answer.</strong>
         <p>The science is fine, but a marker would give zero because it does not
         answer <em>this</em> question — it never uses
         ${result.context_gate.anchors_used.length
            ? result.context_gate.anchors_used.map((a) => `<code>${a}</code>`).join(", ")
            : "the specific things this question is about"}.
         That is the mark, and it is worth knowing now.</p>
         ${result.context_gate.note ? `<p>${result.context_gate.note}</p>` : ""}
       </div>`
    : "";

  const chains = result.chains.map((chain) => `
    <div class="fchain">
      <div class="fchain-head">${chain.chain_id}</div>
      <ol class="flinks">
        ${chain.links.map((link) => `
          <li class="link-${link.status}">
            <span class="dot"></span>
            <span class="lstatus">${link.status}</span>
            ${link.note ? `<span class="lnote">${link.note}</span>` : ""}
          </li>`).join("")}
      </ol>
    </div>`).join("");

  const missed = result.missed_summary.length
    ? `<div class="missed"><strong>Next step</strong><ul>${
        result.missed_summary.map((m) => `<li>${m}</li>`).join("")}</ul></div>`
    : "";

  // Coaching, visually subordinate and explicitly not part of the mark.
  const conventions = result.convention_notes.length
    ? `<div class="conventions"><strong>Wording tips</strong>
       — these did not change your mark
       <ul>${result.convention_notes.map((c) => `<li>${c}</li>`).join("")}</ul></div>`
    : "";

  const incomplete = result.incomplete_attempt
    ? `<p class="caveat">That answer trailed off — it looks unfinished rather than
       wrong. Have another go at saying the whole thing.</p>` : "";

  const full = result.marks_total > 0 &&
               result.marks_awarded === result.marks_total;

  return `
    <div class="fbhead">
      <div class="score${gateFailed ? " zero" : full ? " full" : ""}">
        ${full ? "<span class=\"tick\">✓</span> " : ""}${result.marks_awarded} / ${result.marks_total}
      </div>
      <button class="fbtoggle" type="button">Hide details</button>
    </div>
    <div class="fbbody">
    ${gate}${incomplete}${chains}${missed}${conventions}</div>`;
}

// Raising a doubt is most useful at the moment it appears — with the answer in
// front of you and your own attempt beside it. Asking for it later, out of
// context, is how a wrong model answer survives.
function flagRow(question, part) {
  const row = document.createElement("div");
  row.className = "flagrow";
  row.innerHTML = `
    <button class="flag" type="button">Something looks wrong with this answer</button>
    <input class="flagreason" type="text" placeholder="What looks wrong?" hidden>
    <button class="flagsend" type="button" hidden>Send</button>
    <span class="flagsaved status"></span>`;

  const open = row.querySelector(".flag");
  const reason = row.querySelector(".flagreason");
  const send = row.querySelector(".flagsend");
  const saved = row.querySelector(".flagsaved");

  open.addEventListener("click", () => {
    reason.hidden = send.hidden = false;
    open.hidden = true;
    reason.focus();
  });

  send.addEventListener("click", async () => {
    if (!reason.value.trim()) { reason.focus(); return; }
    saved.textContent = "Sending…";
    try {
      const res = await fetch(`/api/flags/${state.year}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.question, part: part.part, flagged: true,
          reason: reason.value, source: "practice",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      reason.hidden = send.hidden = true;
      saved.textContent = "Flagged — it will show up on the review page.";
    } catch (err) {
      saved.textContent = `Could not send: ${err.message}`;
    }
  });
  return row;
}

function selfMarkRow(part, onPick, card) {
  const row = document.createElement("div");
  row.className = "selfmark";
  row.innerHTML = `<span>How many marks would you give yourself?</span>`;
  const max = part.marks || 3;
  for (let value = 0; value <= max; value += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = value;
    button.addEventListener("click", () => {
      for (const other of row.querySelectorAll("button")) other.classList.remove("picked");
      button.classList.add("picked");
      onPick(value);
      if (card) markCorrect(card, value, part.marks || 0);
      refreshScore();
    });
    row.append(button);
  }
  return row;
}

/* ---------------------------------------------------------------- recording */

function wireRecorder(button, status, box, onTranscript) {
  let recorder = null;
  let chunks = [];

  button.addEventListener("click", async () => {
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      status.textContent = "No microphone access — type your answer instead.";
      return;
    }
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    recorder.onstop = async () => {
      for (const track of stream.getTracks()) track.stop();
      button.dataset.state = "idle";
      button.textContent = "Record";
      status.textContent = "Transcribing…";
      const blob = new Blob(chunks, { type: "audio/webm" });
      const form = new FormData();
      form.append("audio", blob, "answer.webm");
      // Anchors bias recognition toward this question's labelled entities.
      form.append("year", String(state.year));
      form.append("question", String(current().question));
      try {
        const res = await fetch("/api/transcribe", { method: "POST", body: form });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        box.value = data.text;
        onTranscript(data.text);
        status.textContent = `Transcribed in ${data.seconds}s (${data.model}). Check it.`;
      } catch (err) {
        status.textContent = `Transcription failed: ${err.message}`;
      }
    };
    recorder.start();
    button.dataset.state = "recording";
    button.textContent = "Stop";
    status.textContent = "Recording… speak your full answer.";
  });
}

/* ----------------------------------------------------------------- splitter */

// A draggable divider between the paper and the answers. The right balance
// depends on the question — a dense diagram wants the paper wide, a four-part
// written answer wants the other side — so it is set per person, not by me, and
// remembered.
const SPLIT_MIN = 25;
const SPLIT_MAX = 70;
const SPLIT_DEFAULT = 45;
const SPLIT_KEY = "psle.splitPercent";

function applySplit(percent) {
  const clamped = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, percent));
  document.querySelector("main").style.setProperty("--paper-width", `${clamped}%`);
  els.splitter.setAttribute("aria-valuenow", String(Math.round(clamped)));
  try { localStorage.setItem(SPLIT_KEY, String(clamped)); } catch { /* private mode */ }
  return clamped;
}

function wireSplitter() {
  const splitter = els.splitter;
  if (!splitter) return;
  const main = document.querySelector("main");

  splitter.setAttribute("aria-valuemin", String(SPLIT_MIN));
  splitter.setAttribute("aria-valuemax", String(SPLIT_MAX));
  const saved = Number(localStorage.getItem(SPLIT_KEY));
  applySplit(Number.isFinite(saved) && saved ? saved : SPLIT_DEFAULT);

  const move = (event) => {
    const rect = main.getBoundingClientRect();
    applySplit(((event.clientX - rect.left) / rect.width) * 100);
  };
  const stop = () => {
    splitter.classList.remove("dragging");
    document.body.classList.remove("resizing");
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
  };

  splitter.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    splitter.classList.add("dragging");
    document.body.classList.add("resizing");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  });

  // Double-click restores the default rather than leaving someone stuck with a
  // pane they dragged to the edge.
  splitter.addEventListener("dblclick", () => applySplit(SPLIT_DEFAULT));

  splitter.addEventListener("keydown", (event) => {
    const step = event.key === "ArrowLeft" ? -2 : event.key === "ArrowRight" ? 2 : 0;
    if (!step) return;
    event.preventDefault();
    const current = parseFloat(
      getComputedStyle(main).getPropertyValue("--paper-width")) || SPLIT_DEFAULT;
    applySplit(current + step);
  });
}

/* -------------------------------------------------------------------- setup */

function selectQuestion(index) {
  state.index = Math.min(state.questions.length - 1, Math.max(0, index));
  els.question.value = String(state.index);
  els.prev.disabled = state.index === 0;
  els.next.disabled = state.index >= state.questions.length - 1;
  renderPages();
  renderQuestion();
}

async function loadPaper(year) {
  state.year = year;
  const data = await getJSON(`/api/papers/${year}/questions`);
  state.questions = data.questions;
  els.question.innerHTML = state.questions
    .map((q, i) => `<option value="${i}">Q${q.question} — ${q.total_marks} marks</option>`)
    .join("");
  selectQuestion(0);
}

async function init() {
  try {
    state.grading = (await getJSON("/api/grading")).available;
  } catch { state.grading = false; }
  let papers;
  try {
    papers = await getJSON("/api/papers");
  } catch (err) {
    els.parts.innerHTML = `<p class="empty">Could not reach the server: ${err.message}</p>`;
    return;
  }
  if (!papers.length) {
    els.parts.innerHTML = `<p class="empty">No papers indexed yet. Run the build scripts.</p>`;
    return;
  }
  els.year.innerHTML = papers
    .map((p) => `<option value="${p.year}">${p.year}</option>`).join("");
  els.year.addEventListener("change", () => loadPaper(Number(els.year.value)));
  els.question.addEventListener("change", () => selectQuestion(Number(els.question.value)));
  wireSplitter();
  els.prev.addEventListener("click", () => selectQuestion(state.index - 1));
  els.next.addEventListener("click", () => selectQuestion(state.index + 1));
  for (const button of document.querySelectorAll("[data-zoom]")) {
    button.addEventListener("click", () =>
      setZoom(state.zoom + (button.dataset.zoom === "in" ? 20 : -20)));
  }
  await loadPaper(papers[0].year);
}

init();
