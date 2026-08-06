"use strict";

const els = {
  year: document.getElementById("year"),
  queue: document.getElementById("queue"),
  progress: document.getElementById("progress"),
};

const state = { year: null };

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
  el.className = "rubric" + (rubric.reviewed ? " approved" : "");

  const marks = rubric.marks === null ? "marks unknown"
    : `${rubric.marks} mark${rubric.marks === 1 ? "" : "s"}`;
  const gate = rubric.context_gate === "general"
    ? `<span class="tag">no scenario gate</span>` : "";
  const model = rubric.mark_model === "per_chain"
    ? `<span class="tag">${rubric.chains_required} routes, 1 mark each</span>`
    : `<span class="tag">1 mark per keypoint</span>`;

  el.innerHTML = `
    <div class="rubric-head">
      <h3>Q${rubric.question}${partLabel(rubric.part)}</h3>
      <span class="marks">${marks}</span>
      ${model}${gate}
      <span class="spacer"></span>
      <span class="state">${rubric.reviewed ? "approved" : "not reviewed"}</span>
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
        ${rubric.chains.map((c) => chainHTML(c, rubric.mark_model)).join("")}
        ${rubric.scenario_anchors.length
          ? `<div class="anchors">anchors: ${rubric.scenario_anchors
              .map((a) => `<code>${a}</code>`).join(" ")}</div>` : ""}
        ${rubric.traps && rubric.traps.length
          ? `<div class="traps"><strong>Traps</strong><ul>${rubric.traps
              .map((t) => `<li>${t}</li>`).join("")}</ul></div>` : ""}
      </div>
    </div>

    <div class="actions">
      <button class="approve" type="button">Approve</button>
      <button class="reject" type="button">Needs work</button>
      <input class="note" type="text" placeholder="Note (optional — required if it needs work)">
      <span class="saved status"></span>
    </div>`;

  const note = el.querySelector(".note");
  const saved = el.querySelector(".saved");
  if (rubric.review_note) note.value = rubric.review_note;

  async function send(approved) {
    if (!approved && !note.value.trim()) {
      saved.textContent = "Say what is wrong with it.";
      note.focus();
      return;
    }
    saved.textContent = "Saving…";
    try {
      const res = await fetch(`/api/review/${state.year}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: rubric.question, part: rubric.part,
          approved, note: note.value,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      rubric.reviewed = approved;
      el.classList.toggle("approved", approved);
      el.classList.toggle("rejected", !approved);
      el.querySelector(".state").textContent = approved ? "approved" : "needs work";
      saved.textContent = "Saved.";
      refreshProgress();
    } catch (err) {
      saved.textContent = `Could not save: ${err.message}`;
    }
  }

  el.querySelector(".approve").addEventListener("click", () => send(true));
  el.querySelector(".reject").addEventListener("click", () => send(false));
  return el;
}

let queue = { total: 0, authored: 0, rubrics: [] };

function refreshProgress() {
  const approved = queue.rubrics.filter((r) => r.reviewed).length;
  els.progress.textContent =
    `${approved} of ${queue.authored} authored approved · ` +
    `${queue.total - queue.authored} still unauthored`;
}

async function loadYear(year) {
  state.year = year;
  els.queue.innerHTML = `<p class="empty">Loading…</p>`;
  queue = await getJSON(`/api/review/${year}`);
  els.queue.innerHTML = "";
  if (!queue.rubrics.length) {
    els.queue.innerHTML =
      `<p class="empty">No rubrics have chains yet for ${year}. ` +
      `Author them in build/authored/${year}.py first.</p>`;
  }
  for (const rubric of queue.rubrics) els.queue.append(card(rubric));
  refreshProgress();
}

async function init() {
  const papers = await getJSON("/api/papers");
  els.year.innerHTML = papers
    .map((p) => `<option value="${p.year}">${p.year}</option>`).join("");
  els.year.addEventListener("change", () => loadYear(Number(els.year.value)));
  await loadYear(papers[0].year);
}

init();
