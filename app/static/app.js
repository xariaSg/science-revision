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
};

const state = { year: null, questions: [], index: 0, zoom: 100 };

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
      <button class="reveal" type="button">Reveal model answer</button>
      <button class="save" type="button">Save attempt</button>
      <span class="saved status"></span>
    </div>
    <div class="model" hidden></div>`;

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
      const crop = match.crops && match.crops[0]
        ? `<img src="${match.crops[0]}" alt="Answer for part ${match.part || ""}">` : "";
      model.innerHTML = `<h4>Suggested answer</h4>
        ${crop}
        <div class="caveat">This is a publisher's suggested answer, not the official
        SEAB marking scheme. If your wording differs but your science is right,
        you may still have the mark.</div>`;
      model.append(selfMarkRow(part, (value) => { selfMark = value; }));
      card.classList.add("done");
    } catch (err) {
      model.innerHTML = `<h4>Suggested answer</h4><p>Could not load it: ${err.message}</p>`;
    }
  });

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

function selfMarkRow(part, onPick) {
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
  els.prev.addEventListener("click", () => selectQuestion(state.index - 1));
  els.next.addEventListener("click", () => selectQuestion(state.index + 1));
  for (const button of document.querySelectorAll("[data-zoom]")) {
    button.addEventListener("click", () =>
      setZoom(state.zoom + (button.dataset.zoom === "in" ? 20 : -20)));
  }
  await loadPaper(papers[0].year);
}

init();
