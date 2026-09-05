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
  paper: document.getElementById("paper"),
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

// One bar per paper per day, split into how the marks were answered for. Height is
// marks, which is what was asked for and is also the honest axis: a percentage
// would show a single lucky question as a full-height bar beside a whole paper. So
// the bar is as tall as the marks that were on offer, the filled part of each block
// is what she got — a short bar means a short sitting, not a bad one.
//
// The split is stacked rather than drawn as two bars side by side, so the bar still
// reads as one sitting and a click on it still means one paper on one day. Blocks
// stack in the order the paper is sat (the track is column-reverse), so Science's
// MCQ is the base and its written half sits on top.
function segment(part, paper) {
  return `
    <div class="cseg" title="${esc(part.name)} · ${part.earned} of ${part.possible}
         marks · ${part.attempts} answer${part.attempts === 1 ? "" : "s"}"
         style="height:${(part.possible / paper.possible) * 100}%">
      <div class="cfill ${strength(part.percent)}" style="height:${part.percent}%"></div>
      ${part.short ? `<span class="ckind" hidden>${esc(part.short)}</span>` : ""}
    </div>`;
}

// The letter is drawn hidden and then measured, rather than sized up in advance from
// the numbers: a block's height is a percentage of a percentage of a CSS variable,
// less whatever the row of year labels below the plot takes, and only the laid-out
// page knows what that comes to. Predicting it from a pixel constant copied out of
// the stylesheet was over by a tenth, which is the difference between a chip that
// fits and one crushed into a sliver.
function fitKindLabels(root) {
  for (const seg of root.querySelectorAll(".cseg")) {
    const label = seg.querySelector(".ckind");
    if (label) label.hidden = seg.getBoundingClientRect().height < 20;
  }
}

function bar(paper, max) {
  // A paper with no split — an older attempt, or a subject that does not declare
  // one — draws as a single block, which is what the chart did before the split.
  const parts = paper.parts && paper.parts.length ? paper.parts
    : [{ id: "all", name: `${paper.label} paper`, short: "", earned: paper.earned,
         possible: paper.possible, percent: paper.percent, attempts: paper.attempts }];
  return `
    <button type="button" class="cbar" data-date="${esc(paper.date)}"
            data-paper="${esc(paper.paper)}"
            aria-label="${esc(paper.date)}, ${esc(paper.label)} paper, ${paper.earned} of
                        ${paper.possible} marks. Show the answers.">
      <span class="ctrack" style="height:${(paper.possible / max) * 100}%">
        ${parts.map((part) => segment(part, paper)).join("")}
        <span class="cval">${paper.earned}</span>
      </span>
      <span class="cyear">${esc(paper.label)}</span>
    </button>`;
}

function chart(papers, kinds) {
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
      <div class="cbars">${bars.map((b) => bar(b, max)).join("")}</div>
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
       <span class="key-track"></span> marks attempted ·
       ${kinds.map((k) => `<span class="key-kind">${esc(k.short)}</span>
                           ${esc(k.name)}`).join(" · ")}</p>
    <p class="chint">Click a bar to see what she answered that day.</p>`;
}

function trend(papers) {
  if (papers.length < 2) return "";
  const delta = papers[papers.length - 1].percent - papers[0].percent;
  if (delta === 0) return "";
  return `<p class="trend ${delta > 0 ? "up" : "down"}">
    ${delta > 0 ? "▲" : "▼"} ${Math.abs(delta)} percentage points
    since ${shortDate(papers[0].date)}</p>`;
}

// ------------------------------------------------- what a bar is made of

// A bar says a morning on the 2021 paper earned 56 of 70. This says which
// questions those were and what she actually put down — the thing a parent asks
// next, and the thing that turns "82%" back into something to talk about.
//
// Grouped the way the bar is split, and in the same order, so the panel reads as
// the bar taken apart rather than as a second, differently-shaped report.

const time = (iso) => new Date(iso)
  .toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

// Chosen answers are dense — 28 of them in a Booklet A morning — so they pack into
// a grid of small cells rather than a list. Each one carries the question, the
// option she picked, and whether it was right; a wrong one also carries the option
// that was, which she was already shown when she answered it.
function choiceCells(rows) {
  return `<div class="dgrid">${rows.map((r) => {
    const state = r.correct === null ? "" : r.correct ? "ok" : "no";
    const answer = r.correct === false && r.correct_option
      ? `<span class="dans">ans ${r.correct_option}</span>` : "";
    return `
      <span class="dcell ${state}" title="${esc(r.label)} · chose option ${esc(r.chose)}${
        r.correct === false && r.correct_option
          ? `, the answer was ${r.correct_option}` : ""} · ${time(r.at)}">
        <span class="dq">${esc(r.label)}</span>
        <span class="dchose">${esc(r.chose ?? "—")}</span>
        <span class="dv">${r.correct === null ? "·" : r.correct ? "✓" : "✗"}</span>
        ${answer}
      </span>`;
  }).join("")}</div>`;
}

// Written answers are few and long, so they get the room to be read. The answer
// text is the point of the panel here: a mark on its own does not say what she
// wrote, and what she wrote is what a parent can actually help with.
function writtenList(rows) {
  return `<ul class="dlist">${rows.map((r) => `
    <li>
      <div class="dline">
        <span class="dq">${esc(r.label)}</span>
        <span class="dmark ${r.marks === null ? "" : strength(pct(r.marks, r.marks_total))}">
          ${r.marks === null ? "not marked yet" : `${r.marks}/${r.marks_total}`}</span>
        <span class="dtime">${time(r.at)}</span>
      </div>
      <p class="dtext">${esc(r.answer || "")}</p>
      ${r.correct === false && r.expected ? `<p class="dnote">The answer was
        <strong>${esc(r.expected)}</strong>.</p>` : ""}
      ${r.gate_passed === 0 ? `<p class="dnote">Zero for not using the question's
        own details — the textbook-recital trap.</p>` : ""}
    </li>`).join("")}</ul>`;
}

function dayPanel(data) {
  if (!data.groups.length) {
    return `<p class="empty">Nothing logged for that paper on that day.</p>`;
  }
  return `
    <div class="dhead">
      <strong>${shortDate(data.date)} · ${esc(data.label)} paper</strong>
      <span>${data.earned} of ${data.possible} marks</span>
      <button type="button" class="dclose">Close</button>
    </div>
    ${data.groups.map((g) => `
      <div class="dgroup">
        <h4>${esc(g.name)}
          <span>${g.earned}/${g.possible} · ${g.attempts}
                answer${g.attempts === 1 ? "" : "s"}</span></h4>
        ${g.kind === "choice" ? choiceCells(g.rows) : writtenList(g.rows)}
      </div>`).join("")}`;
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

// The two booklets, side by side. Marks are of what she has tried, like every other
// bar here; the coverage half of the row is of the whole paper, because "24 of 402"
// is the honest answer to how much is left and a percentage of it would not be.
function bookletRows(booklets) {
  return booklets.map((b) => `
    <div class="prow wide">
      <div class="pname">${esc(b.name)}</div>
      <div class="pbar">${b.possible ? `<div class="pfill ${strength(b.percent)}"
        style="width:${b.percent}%"></div>` : ""}</div>
      <div class="ppct">${b.possible ? `${b.percent}%` : "—"}</div>
      <div class="pmeta">${b.possible ? `${b.earned}/${b.possible} marks · ` : ""}${
        b.slots - b.untouched} of ${b.slots} tried</div>
    </div>`).join("");
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

    <h3>MCQ and written</h3>
    <p class="hint">Booklet A is marked against the answer key and is right or
    wrong; Booklet B is marked link by link and is usually partly right. They are
    two different skills sharing one paper. Marks are her best attempt at each
    question, so these read higher than the chart above, which counts every try.</p>
    ${bookletRows(data.booklets || [])}

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

function englishBody(data) {
  const weakest = data.sections.filter((s) => s.percent < 80)
    .sort((a, b) => a.percent - b.percent).slice(0, 2);
  return `
    ${weakest.length ? `<div class="focus">
      <strong>Worth practising next</strong>
      ${weakest.map((s) => `${esc(s.name)} (${s.percent}%)`).join(" · ")}
    </div>` : ""}

    ${data.unmarked ? `<div class="focus warn">
      <strong>${data.unmarked} answer${data.unmarked === 1 ? "" : "s"}
      ${data.unmarked === 1 ? "is" : "are"} still waiting to be marked.</strong>
      A transformed sentence has no rubric to mark it against, so it is marked
      against the model answer by hand.
    </div>` : ""}

    <h3>By section</h3>
    <p class="hint">In the order the paper prints them. Booklet A's names are the
    school's own; Booklet B prints none, so the section is named by how it is
    answered.</p>
    ${barRows(data.sections)}

    <h3>By booklet</h3>
    <p class="hint">Choosing an option and writing an answer are close to two
    different skills, and the two booklets are sat separately.</p>
    ${barRows(data.booklets)}`;
}

const SUBJECT_BODY = { chinese: chineseBody, english: englishBody };

function render(data) {
  const totals = data.papers.reduce(
    (acc, p) => ({ earned: acc.earned + p.earned, possible: acc.possible + p.possible }),
    { earned: 0, possible: 0 });

  els.report.innerHTML = `
    <h3>Marks by paper</h3>
    ${trend(data.papers)}
    ${chart(data.papers, data.kinds || [])}
    <div id="day" class="day" hidden></div>
    ${SUBJECT_BODY[data.subject] ? SUBJECT_BODY[data.subject](data)
                                : scienceBody(data)}`;
  fitKindLabels(els.report);
}

// ---------------------------------------------------------------- wiring

// One report per subject, never a shared one taking ?subject= (CLAUDE.md 8): the
// three share only the attempt log and the chart, and a union schema would have
// two thirds of its fields null on every request.
const API_BASE = { chinese: "/api/chinese", english: "/api/english" };
const base = (subject) => API_BASE[subject] || "/api";

function endpoint(subject, paper) {
  return paper === "all" ? `${base(subject)}/progress`
                         : `${base(subject)}/papers/${paper}/progress`;
}

function dayEndpoint(subject, paper, date) {
  return `${base(subject)}/papers/${paper}/attempts/${date}`;
}

// Which bar is open. Cleared whenever the report reloads, because the panel sits
// inside the report and a subject or year change replaces the chart under it.
let openBar = null;

function closeDay() {
  openBar = null;
  document.querySelectorAll(".cbar.on").forEach((b) => b.classList.remove("on"));
  const box = document.getElementById("day");
  if (box) { box.hidden = true; box.innerHTML = ""; }
}

async function openDay(barEl) {
  const { date, paper } = barEl.dataset;
  if (openBar && openBar.date === date && openBar.paper === paper) return closeDay();

  closeDay();
  openBar = { date, paper };
  barEl.classList.add("on");
  const box = document.getElementById("day");
  box.hidden = false;
  box.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    box.innerHTML = dayPanel(
      await getJSON(dayEndpoint(els.subject.value, paper, date)));
  } catch (err) {
    box.innerHTML = `<p class="empty">Could not load that day: ${esc(err.message)}</p>`;
  }
}

// Delegated, because the chart is rebuilt from scratch on every load.
els.report.addEventListener("click", (event) => {
  if (event.target.closest(".dclose")) return closeDay();
  const bar = event.target.closest(".cbar");
  if (bar) openDay(bar);
});

async function load() {
  closeDay();
  els.report.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    render(await getJSON(endpoint(els.subject.value, els.paper.value)));
  } catch (err) {
    els.report.innerHTML = `<p class="empty">Could not load progress: ${esc(err.message)}</p>`;
  }
}

function fillPapers() {
  const entry = subjects.find((s) => s.id === els.subject.value);
  // Grouped with <optgroup>, because Science now offers twenty-eight papers and
  // fourteen of them are the same year as each other. The value is the paper id;
  // what is shown is the paper's name.
  const groups = (entry ? entry.groups : []).map((g) => `
    <optgroup label="${esc(g.group)}">
      ${g.papers.map((p) => `<option value="${esc(p.paper)}">${esc(p.label)}</option>`).join("")}
    </optgroup>`).join("");
  els.paper.innerHTML = `<option value="all">All papers</option>` + groups;
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

  els.subject.addEventListener("change", () => { fillPapers(); load(); });
  els.paper.addEventListener("change", load);

  fillPapers();
  await load();
}

init();
