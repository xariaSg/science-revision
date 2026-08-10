"use strict";

// A parent view, not a dashboard. Three questions it should answer at a glance:
// is she improving, what is she weakest at, and how much of the paper is left.
//
// Reported one subject at a time. Science and Chinese share the attempt log and
// the chart and almost nothing else -- a Science weakness is a syllabus topic and
// a broken reasoning chain, a Chinese one is a section of the paper -- so mixing
// them into a single view would average two unrelated things into a number that
// describes neither.

const els = {
  subject: document.getElementById("subject"),
  year: document.getElementById("year"),
  report: document.getElementById("report"),
};

// Filled by init() from /api/subjects, so the pickers offer only what is built.
let subjects = [];

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);
const esc = (s) => String(s).replace(/[&<>]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

const strength = (p) => (p < 50 ? "weak" : p < 80 ? "mid" : "strong");

// Weakest first — the list exists to be acted on, and a strength you already have
// is not the thing to practise next. Chinese sections are the exception and come
// pre-ordered by the server, in the order the paper prints them.
function barRows(items, limit = 8) {
  if (!items.length) return `<p class="empty">Nothing marked yet.</p>`;
  return items.slice(0, limit).map((row) => `
    <div class="prow">
      <div class="pname">${esc(row.name)}</div>
      <div class="pbar"><div class="pfill ${strength(row.percent)}"
        style="width:${row.percent}%"></div></div>
      <div class="ppct">${row.percent}%</div>
      <div class="pmeta">${row.earned}/${row.possible}</div>
    </div>`).join("");
}

// ---------------------------------------------------------------- the chart

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function shortDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y) return iso;
  const label = `${d} ${MONTHS[m - 1]}`;
  return y === new Date().getFullYear() ? label : `${label} ${String(y).slice(2)}`;
}

// Four gridlines at a round interval, the top one at or above the tallest bar —
// so the axis reads 0/10/20/30/40 rather than 0/9/18/27/37. The step has to be a
// whole number: on her first day there is one mark on the chart, and a step of
// 0.25 rounds to an axis labelled 1, 1, 1, 0, 0.
function axisSteps(peak) {
  const steps = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100];
  const step = steps.find((s) => s * 4 >= peak) || Math.ceil(peak / 4);
  return [4, 3, 2, 1, 0].map((i) => step * i);
}

// Marks per paper per day. Height is marks, which is what was asked for and is
// also the honest axis: a percentage would show a single lucky question as a
// full-height bar beside a whole paper. So the bar is as tall as the marks that
// were on offer, and the filled part is what she got — a short bar means a short
// sitting, not a bad one.
function chart(papers) {
  if (!papers.length) {
    return `<p class="empty">No marks logged yet. Answer a few questions and
            they will show up here.</p>`;
  }

  const ticks = axisSteps(Math.max(...papers.map((p) => p.possible)));
  const max = ticks[0];

  // One column per date, one bar per paper within it.
  const byDate = [];
  for (const p of papers) {
    const last = byDate[byDate.length - 1];
    if (last && last.date === p.date) last.bars.push(p);
    else byDate.push({ date: p.date, bars: [p] });
  }

  const groups = byDate.map(({ date, bars }) => `
    <div class="cgroup">
      <div class="cbars">
        ${bars.map((b) => `
          <div class="cbar" title="${esc(b.date)} · ${b.year} paper · ${b.earned} of
               ${b.possible} marks · ${b.attempts} question${b.attempts === 1 ? "" : "s"}">
            <div class="ctrack" style="height:${(b.possible / max) * 100}%">
              <div class="cfill ${strength(b.percent)}"
                   style="height:${pct(b.earned, b.possible)}%"></div>
              <span class="cval">${b.earned}</span>
            </div>
            <span class="cyear">${b.year}</span>
          </div>`).join("")}
      </div>
      <div class="cdate">${shortDate(date)}</div>
    </div>`).join("");

  return `
    <div class="chart">
      <div class="caxis">${ticks.map((t) => `<span>${t}</span>`).join("")}</div>
      <div class="cplot">
        <div class="cgrid">${ticks.map(() => `<i></i>`).join("")}</div>
        <div class="cgroups">${groups}</div>
      </div>
    </div>
    <p class="chint"><span class="key-fill"></span> marks earned ·
       <span class="key-track"></span> marks attempted · the label is the paper</p>`;
}

function trend(papers) {
  if (papers.length < 2) return "";
  const delta = papers[papers.length - 1].percent - papers[0].percent;
  if (delta === 0) return "";
  return `<p class="trend ${delta > 0 ? "up" : "down"}">
    ${delta > 0 ? "▲" : "▼"} ${Math.abs(delta)} percentage points
    since ${shortDate(papers[0].date)}</p>`;
}

// ---------------------------------------------------------------- the report

function summary(data, totals) {
  return `
    <div class="summary">
      <div class="stat"><span>${totals.earned}/${totals.possible}</span>marks earned</div>
      <div class="stat"><span>${pct(totals.earned, totals.possible)}%</span>overall</div>
      <div class="stat"><span>${data.total_attempts}</span>attempts</div>
      <div class="stat"><span>${data.untouched}</span>of ${data.slots} not tried yet</div>
    </div>`;
}

function scienceBody(data) {
  const weakest = data.topics.filter((t) => t.percent < 80).slice(0, 3);
  return `
    ${weakest.length ? `<div class="focus">
      <strong>Worth practising next</strong>
      ${weakest.map((t) => `${esc(t.name)} (${t.percent}%)`).join(" · ")}
    </div>` : ""}

    ${data.gate_failures ? `<div class="focus warn">
      <strong>${data.gate_failures} answer${data.gate_failures === 1 ? "" : "s"}
      scored zero for not using the question's own details.</strong>
      That is the textbook-recital trap — the science was there but it did not
      answer the specific question.
    </div>` : ""}

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
          <div class="pname">${esc(f.name)}</div>
          <div class="pbar"><div class="pfill ${strength(f.percent)}"
            style="width:${f.percent}%"></div></div>
          <div class="ppct">${f.percent}%</div>
          <div class="pmeta">${f.hit} hit · ${f.missed} missed</div>
        </div>`).join("")
      : `<p class="empty">Nothing graded yet — these come from the grader.</p>`}`;
}

function chineseBody(data) {
  const weakest = data.sections.filter((s) => s.percent < 80)
    .sort((a, b) => a.percent - b.percent).slice(0, 2);
  return `
    ${weakest.length ? `<div class="focus">
      <strong>Worth practising next</strong>
      ${weakest.map((s) => `${esc(s.name)} (${s.percent}%)`).join(" · ")}
    </div>` : ""}

    ${data.unmarked ? `<div class="focus warn">
      <strong>${data.unmarked} written answer${data.unmarked === 1 ? "" : "s"}
      ${data.unmarked === 1 ? "is" : "are"} still waiting to be marked.</strong>
      The 2021 and 2022 papers print no mark points, so those answers are marked
      against the model answer by hand.
    </div>` : ""}

    <h3>By section</h3>
    <p class="hint">In the order the paper prints them.</p>
    ${barRows(data.sections)}

    <h3>By how it is answered</h3>
    <p class="hint">Choosing an option and writing an answer are close to two
    different skills sharing one paper.</p>
    ${barRows(data.modes)}`;
}

function render(data) {
  const totals = data.papers.reduce(
    (acc, p) => ({ earned: acc.earned + p.earned, possible: acc.possible + p.possible }),
    { earned: 0, possible: 0 });

  els.report.innerHTML = `
    ${summary(data, totals)}
    <h3>Marks by paper</h3>
    ${trend(data.papers)}
    ${chart(data.papers)}
    ${data.subject === "chinese" ? chineseBody(data) : scienceBody(data)}`;
}

// ---------------------------------------------------------------- wiring

function endpoint(subject, year) {
  const base = subject === "chinese" ? "/api/chinese" : "/api";
  return year === "all" ? `${base}/progress`
                        : `${base}/papers/${year}/progress`;
}

async function load() {
  els.report.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    render(await getJSON(endpoint(els.subject.value, els.year.value)));
  } catch (err) {
    els.report.innerHTML = `<p class="empty">Could not load progress: ${esc(err.message)}</p>`;
  }
}

function fillYears() {
  const entry = subjects.find((s) => s.id === els.subject.value);
  els.year.innerHTML = `<option value="all">All papers</option>` +
    (entry ? entry.years : []).map((y) => `<option value="${y}">${y}</option>`).join("");
}

async function init() {
  subjects = await getJSON("/api/subjects");
  if (!subjects.length) {
    els.report.innerHTML = `<p class="empty">No papers are indexed yet.</p>`;
    return;
  }
  els.subject.innerHTML = subjects
    .map((s) => `<option value="${s.id}">${esc(s.label)}</option>`).join("");
  // A single subject makes the picker a control with one choice; keep it visible
  // for consistency but do not pretend it is a decision.
  els.subject.disabled = subjects.length === 1;

  els.subject.addEventListener("change", () => { fillYears(); load(); });
  els.year.addEventListener("change", load);

  fillYears();
  await load();
}

init();
