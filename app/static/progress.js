"use strict";

// A parent view, not a dashboard. Three questions it should answer at a glance:
// is she improving, what is she weakest at, and what has she not touched yet.

const els = {
  year: document.getElementById("year"),
  report: document.getElementById("report"),
};

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);
const partLabel = (p) =>
  !p ? "" : p.includes("(") ? `(${p.replace("(", ")(")}` : `(${p})`;

// Weakest first — the list exists to be acted on, and a strength you already have
// is not the thing to practise next.
function barRows(items, limit = 8) {
  if (!items.length) return `<p class="empty">Nothing marked yet.</p>`;
  return items.slice(0, limit).map((row) => `
    <div class="prow">
      <div class="pname">${row.name}</div>
      <div class="pbar"><div class="pfill ${row.percent < 50 ? "weak"
        : row.percent < 80 ? "mid" : "strong"}" style="width:${row.percent}%"></div></div>
      <div class="ppct">${row.percent}%</div>
      <div class="pmeta">${row.earned}/${row.possible}</div>
    </div>`).join("");
}

// Marks per day as a plain bar chart. A sparkline would look neater and say less;
// what matters is whether the percentage is climbing.
function overTime(days) {
  if (!days.length) return `<p class="empty">No attempts logged yet.</p>`;
  const rows = days.map((d) => {
    const p = pct(d.earned, d.possible);
    return `<div class="dayrow">
      <div class="dday">${d.date}</div>
      <div class="dbar"><div class="dfill" style="width:${p}%"></div></div>
      <div class="dpct">${p}%</div>
      <div class="dmeta">${d.earned}/${d.possible} · ${d.attempts} attempt${
        d.attempts === 1 ? "" : "s"}</div>
    </div>`;
  }).join("");
  const first = pct(days[0].earned, days[0].possible);
  const last = pct(days[days.length - 1].earned, days[days.length - 1].possible);
  const delta = last - first;
  const trend = days.length < 2 ? ""
    : `<p class="trend ${delta >= 0 ? "up" : "down"}">
         ${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta)} percentage points
         since ${days[0].date}</p>`;
  return trend + rows;
}

function render(data) {
  const totals = data.by_day.reduce(
    (acc, d) => ({ earned: acc.earned + d.earned, possible: acc.possible + d.possible }),
    { earned: 0, possible: 0 });

  const weakest = data.topics.filter((t) => t.percent < 80).slice(0, 3);

  els.report.innerHTML = `
    <div class="summary">
      <div class="stat"><span>${totals.earned}/${totals.possible}</span>marks earned</div>
      <div class="stat"><span>${pct(totals.earned, totals.possible)}%</span>overall</div>
      <div class="stat"><span>${data.total_attempts}</span>attempts</div>
      <div class="stat"><span>${data.never_attempted.length}</span>parts untouched</div>
    </div>

    ${weakest.length ? `<div class="focus">
      <strong>Worth practising next</strong>
      ${weakest.map((t) => `${t.name} (${t.percent}%)`).join(" · ")}
    </div>` : ""}

    ${data.gate_failures ? `<div class="focus warn">
      <strong>${data.gate_failures} answer${data.gate_failures === 1 ? "" : "s"}
      scored zero for not using the question's own details.</strong>
      That is the textbook-recital trap — the science was there but it did not
      answer the specific question.
    </div>` : ""}

    <h3>Marks over time</h3>
    ${overTime(data.by_day)}

    <h3>Weakest syllabus topics</h3>
    ${barRows(data.topics)}

    <h3>By theme</h3>
    ${barRows(data.themes)}

    <h3>Reasoning steps</h3>
    <p class="hint">Which part of a cause-and-effect chain is missed most:
    naming the variable, the action, or the resulting change.</p>
    ${data.facets.length
      ? data.facets.map((f) => `
        <div class="prow">
          <div class="pname">${f.name}</div>
          <div class="pbar"><div class="pfill ${f.percent < 50 ? "weak"
            : f.percent < 80 ? "mid" : "strong"}" style="width:${f.percent}%"></div></div>
          <div class="ppct">${f.percent}%</div>
          <div class="pmeta">${f.hit} hit · ${f.missed} missed</div>
        </div>`).join("")
      : `<p class="empty">Nothing graded yet — these come from the grader.</p>`}

    <h3>Not attempted yet <span class="count">${data.never_attempted.length}</span></h3>
    ${data.never_attempted.length
      ? `<div class="untouched">${data.never_attempted.map((n) =>
          `<span>Q${n.question}${partLabel(n.part)}</span>`).join("")}</div>`
      : `<p class="empty">Every sub-part has been attempted.</p>`}`;
}

async function load(year) {
  els.report.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    render(await getJSON(year === "all" ? "/api/progress"
                                        : `/api/papers/${year}/progress`));
  } catch (err) {
    els.report.innerHTML = `<p class="empty">Could not load progress: ${err.message}</p>`;
  }
}

async function init() {
  const papers = await getJSON("/api/papers");
  els.year.innerHTML = `<option value="all">All papers</option>` +
    papers.map((p) => `<option value="${p.year}">${p.year}</option>`).join("");
  els.year.addEventListener("change", () => load(els.year.value));
  await load("all");
}

init();
