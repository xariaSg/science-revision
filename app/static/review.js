"use strict";

const els = {
  year: document.getElementById("year"),
  filter: document.getElementById("filter"),
  reload: document.getElementById("reload"),
  queue: document.getElementById("queue"),
  progress: document.getElementById("progress"),
};

// Default to the work queue. Landing on rubrics already signed off buries the
// ones still needing a decision, which is the whole reason to open this page.
// Rubrics are approved by default, so the interesting list is what has been
// flagged — not a backlog of things awaiting a decision nobody has reason to make.
const state = { year: null, filter: "flagged" };

const FILTERS = {
  flagged: { label: "Flagged", match: (r) => r.flagged },
  all: { label: "All", match: () => true },
};

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const partLabel = (part) =>
  !part ? "" : part.includes("(") ? `(${part.replace("(", ")(")}` : `(${part})`;

function facetTag(facet) {
  return `<span class="facet facet-${facet}">${facet}</span>`;
}

function chainHTML(chain, markModel) {
  const links = chain.keypoints.map((kp) => `
    <li>
      ${facetTag(kp.facet)}
      <span class="kp">${kp.statement}</span>
      ${kp.accepts && kp.accepts.length
        ? `<div class="accepts">also accepts: ${kp.accepts
            .map((a) => `<em>${a}</em>`).join(" · ")}</div>`
        : ""}
    </li>`).join("");
  const worth = markModel === "per_chain" ? "1 mark for this route" : "";
  return `<div class="chain">
      <div class="chain-head">${chain.chain_id}${worth ? ` — ${worth}` : ""}</div>
      <ol class="links">${links}</ol>
    </div>`;
}

function card(rubric) {
  const el = document.createElement("article");
  el.className = "rubric" + (rubric.flagged ? " rejected" : " approved");

  const marks = rubric.marks === null ? "marks unknown"
    : `${rubric.marks} mark${rubric.marks === 1 ? "" : "s"}`;
  const gate = rubric.context_gate === "general"
    ? `<span class="tag">no scenario gate</span>` : "";
  const drawn = rubric.response_mode === "drawn";
  const model = drawn ? `<span class="tag">answered by drawing</span>`
    : rubric.mark_model === "per_chain"
    ? `<span class="tag">${rubric.chains_required} routes, 1 mark each</span>`
    : `<span class="tag">1 mark per keypoint</span>`;

  el.innerHTML = `
    <div class="rubric-head">
      <h3>Q${rubric.question}${partLabel(rubric.part)}</h3>
      <span class="marks">${marks}</span>
      ${model}${gate}
      <span class="spacer"></span>
      <span class="state">${rubric.flagged ? "flagged" : "in use"}</span>
    </div>

    <div class="pair">
      <div>
        <h4>Suggested answer</h4>
        <p class="answer">${rubric.model_answer || "<em>none extracted</em>"}</p>
        ${rubric.explanation
          ? `<h4>Explanation</h4><p class="answer">${rubric.explanation}</p>` : ""}
      </div>
      <div>
        <h4>Rubric</h4>
        ${drawn
          ? `<p class="answer">This sub-part is answered by drawing on the paper, so
             there is nothing to grade from speech. Confirm that is right — approving
             marks it done rather than missing.</p>`
          : rubric.chains.map((c) => chainHTML(c, rubric.mark_model)).join("")}
        ${rubric.scenario_anchors.length
          ? `<div class="anchors">anchors: ${rubric.scenario_anchors
              .map((a) => `<code>${a}</code>`).join(" ")}</div>` : ""}
        ${rubric.traps && rubric.traps.length
          ? `<div class="traps"><strong>Traps</strong><ul>${rubric.traps
              .map((t) => `<li>${t}</li>`).join("")}</ul></div>` : ""}
      </div>
    </div>

    ${rubric.flagged && rubric.flag_reason
      ? `<div class="traps"><strong>Flagged</strong> — ${rubric.flag_reason}
         ${rubric.flag_source ? `<em>(from ${rubric.flag_source})</em>` : ""}</div>`
      : ""}

    <div class="actions">
      <button class="reject" type="button">${rubric.flagged ? "Re-flag" : "Flag"}</button>
      <button class="approve" type="button" ${rubric.flagged ? "" : "disabled"}>Clear flag</button>
      <input class="note" type="text" placeholder="What is wrong with it?">
      <span class="saved status"></span>
    </div>`;

  const note = el.querySelector(".note");
  const saved = el.querySelector(".saved");
  if (rubric.flag_reason) note.value = rubric.flag_reason;

  async function send(clearing) {
    if (!clearing && !note.value.trim()) {
      saved.textContent = "Say what is wrong with it.";
      note.focus();
      return;
    }
    saved.textContent = "Saving…";
    try {
      const res = await fetch(`/api/flags/${state.year}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: rubric.question, part: rubric.part,
          flagged: !clearing, reason: note.value, source: "review",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      rubric.flagged = !clearing;
      rubric.reviewed = clearing;
      el.classList.toggle("approved", clearing);
      el.classList.toggle("rejected", !clearing);
      el.querySelector(".state").textContent = clearing ? "in use" : "flagged";
      el.querySelector(".approve").disabled = clearing;
      saved.textContent = "Saved.";
      refreshProgress();
      // Fade the card out of the flagged list rather than yanking it away
      // mid-scroll, which loses the reader's place.
      if (state.filter === "flagged" && clearing) {
        el.classList.add("settled");
        setTimeout(() => { if (state.filter === "flagged") el.remove(); }, 900);
      }
    } catch (err) {
      saved.textContent = `Could not save: ${err.message}`;
    }
  }

  el.querySelector(".approve").addEventListener("click", () => send(true));
  el.querySelector(".reject").addEventListener("click", () => send(false));
  return el;
}

let queue = { total: 0, authored: 0, rubrics: [] };

function counts() {
  const out = {};
  for (const [key, spec] of Object.entries(FILTERS)) {
    out[key] = queue.rubrics.filter(spec.match).length;
  }
  return out;
}

function refreshProgress() {
  const n = counts();
  els.progress.textContent =
    `${n.all - n.flagged} in use · ${n.flagged} flagged` +
    (queue.total - queue.authored
      ? ` · ${queue.total - queue.authored} unauthored` : "");
  const selected = els.filter.value || state.filter;
  els.filter.innerHTML = Object.entries(FILTERS)
    .map(([key, spec]) => `<option value="${key}">${spec.label} (${n[key]})</option>`)
    .join("");
  els.filter.value = selected;
}

function renderQueue() {
  const match = FILTERS[state.filter].match;
  const visible = queue.rubrics.filter(match);
  els.queue.innerHTML = "";
  if (!visible.length) {
    els.queue.innerHTML = state.filter === "flagged"
      ? `<p class="empty">Nothing flagged for ${state.year} — every rubric is in ` +
        `use. Flag one here, or from the practice app when an answer looks wrong.</p>`
      : `<p class="empty">Nothing here.</p>`;
    return;
  }
  for (const rubric of visible) els.queue.append(card(rubric));
}

async function loadYear(year) {
  state.year = year;
  els.queue.innerHTML = `<p class="empty">Loading…</p>`;
  queue = await getJSON(`/api/review/${year}`);
  if (!queue.rubrics.length) {
    els.queue.innerHTML =
      `<p class="empty">No rubrics have chains yet for ${year}. ` +
      `Author them in build/authored/${year}.py first.</p>`;
    els.progress.textContent = "";
    return;
  }
  refreshProgress();
  renderQueue();
}

async function init() {
  const papers = await getJSON("/api/papers");
  els.year.innerHTML = papers
    .map((p) => `<option value="${p.year}">${p.year}</option>`).join("");
  els.year.addEventListener("change", () => loadYear(Number(els.year.value)));
  els.filter.addEventListener("change", () => {
    state.filter = els.filter.value;
    renderQueue();
  });
  els.reload.addEventListener("click", () => loadYear(state.year));
  await loadYear(papers[0].year);
}

init();
