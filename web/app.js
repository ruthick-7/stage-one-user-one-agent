"use strict";

const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  users:
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  chart: '<path d="M3 3v18h18M8 16v-5M13 16V7M18 16v-8"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h6"/>',
  play: '<path d="m9 5 11 7-11 7z"/>',
  settings:
    '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  shield: '<path d="m12 3 8 4v6c0 5-8 9-8 9s-8-4-8-9V7zM8 12l3 3 5-6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  logout:
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 10-12h-7z"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
};
const icon = (name) =>
  `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${paths[name] || paths.file}</svg>`;
const e = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const n = (value) => Number(value || 0).toLocaleString();
const pct = (value) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "Unavailable";
const pp = (value) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(2)} pp` : "Unavailable";
const bounds = (values) =>
  Array.isArray(values)
    ? `${pp(values[0])} to ${pp(values[1])}`
    : "Unavailable";
const ms = (value) =>
  Number.isFinite(value)
    ? value < 1000
      ? `${value.toFixed(1)} ms`
      : `${(value / 1000).toFixed(2)} s`
    : "Unavailable";
const date = (value) =>
  value
    ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString(
        undefined,
        {
          timeZone: "Asia/Kolkata",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        },
      )
    : "—";
const initials = (name) =>
  String(name || "")
    .split(/\s+/)
    .slice(0, 2)
    .map((x) => x[0] || "")
    .join("")
    .toUpperCase();
const pill = (label, color = "", dot = false) =>
  `<span class="pill ${color}">${dot ? '<span class="dot"></span>' : ""}${e(label)}</span>`;
const actionPill = (action) =>
  action === "HOME_PAGE" ? pill("Home page", "purple") : pill("No action");
const statusPill = (status) =>
  pill(
    String(status).replaceAll("_", " "),
    {
      succeeded: "green",
      completed: "green",
      failed: "red",
      inconclusive: "amber",
      running: "purple",
      queued: "amber",
      cancelled: "",
    }[status] || "",
    ["running", "queued"].includes(status),
  );
const brand = () =>
  '<div class="brand"><span class="brand-mark">S</span><div><strong>STAGE</strong><small>AGENT WORKSPACE</small></div></div>';
const state = {
  user: null,
  runs: [],
  run: "sample",
  canRun: false,
  version: 0,
  jobs: [],
  route: "dashboard",
  page: 1,
  query: "",
  filter: "",
};
let searchTimer;

function toast(message, error = false) {
  const box = document.createElement("div");
  box.className = `toast ${error ? "error" : ""}`;
  box.textContent = message;
  document.querySelector("#toasts").append(box);
  setTimeout(() => box.remove(), 5000);
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(state.user ? { "X-CSRF-Token": state.user.csrf } : {}),
      ...options.headers,
    },
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && state.user) {
      state.user = null;
      renderAuth();
    }
    throw new Error(data.error || "The request could not be completed.");
  }
  return data;
}
const post = (url, body = {}) =>
  api(url, { method: "POST", body: JSON.stringify(body) });
const runUrl = (path, params = {}) =>
  `${path}?${new URLSearchParams({ run: state.run, ...params })}`;
const footer = () =>
  `<footer class="footer-note"><span>${icon("shield")} Synthetic assignment data · local workspace</span><span>Decide with evidence. Measure with care.</span></footer>`;
function notice(title, text, amber = false) {
  return `<div class="notice ${amber ? "amber" : ""}">${icon("info")}<div><h3>${e(title)}</h3><div class="small">${e(text)}</div></div></div>`;
}
function pageHeader(title, description, action = "", label = "") {
  return `<div class="page-header"><div><div class="page-title-row"><h1>${e(title)}</h1>${label ? pill(label, "purple") : ""}</div><p>${e(description)}</p></div>${action ? `<div class="page-actions">${action}</div>` : ""}</div>`;
}
function empty(title, text, button = "") {
  return `<div class="card empty-state"><span class="empty-icon">${icon("file")}</span><h2>${e(title)}</h2><p>${e(text)}</p>${button}</div>`;
}
function showError(id, message) {
  const node = document.getElementById(id);
  if (node) {
    node.innerHTML = `<div class="error-box" role="alert">${e(message)}</div>`;
  } else toast(message, true);
}

function renderAuth() {
  ++state.version;
  const signup = location.hash === "#/signup";
  document.title = `${signup ? "Create account" : "Sign in"} · STAGE`;
  document.getElementById("app").innerHTML =
    `<div class="auth-layout"><aside class="auth-story">${brand()}<div class="auth-headline"><div class="eyebrow">One user. One agent.</div><h1>Every viewer.<br>A thoughtful<br><span>next step.</span></h1><p>A workspace to understand your viewers, inspect agent decisions, and measure what actually changed.</p><div class="flow-card"><div class="flow-step"><span class="flow-number">01</span><div><strong>Understand the evidence</strong><small>Facts, freshness, and conflicts in one place.</small></div></div><div class="flow-step"><span class="flow-number">02</span><div><strong>Choose a safe next step</strong><small>One measurable goal. An independent check.</small></div></div><div class="flow-step"><span class="flow-number">03</span><div><strong>Measure the outcome</strong><small>Randomized arms. Honest uncertainty.</small></div></div></div></div><div class="auth-footer">${icon("lock")} Local accounts. No API key required.</div></aside><main class="auth-main" id="main-content"><div class="auth-form"><div class="auth-mobile-brand">${brand()}</div><div class="auth-tabs"><a href="#/signin" class="${!signup ? "active" : ""}">Sign in</a><a href="#/signup" class="${signup ? "active" : ""}">Create account</a></div><h2>${signup ? "Your workspace awaits." : "Welcome back."}</h2><p>${signup ? "Create a local account to explore the agent." : "Sign in to pick up where you left off."}</p><div id="auth-error"></div><form id="auth-form" data-mode="${signup ? "signup" : "signin"}">${signup ? '<div class="field"><label for="name">Full name</label><input id="name" name="name" autocomplete="name" placeholder="Your name" minlength="2" maxlength="60" required></div>' : ""}<div class="field"><label for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" maxlength="254" required></div><div class="field"><label for="password">Password</label><div class="input-wrap"><input id="password" name="password" type="password" autocomplete="${signup ? "new-password" : "current-password"}" placeholder="${signup ? "Create a strong password" : "Enter your password"}" ${signup ? 'minlength="10"' : ""} maxlength="128" required><button class="icon-btn" type="button" data-action="password" data-target="password" aria-label="Show password">${icon("eye")}</button></div>${signup ? '<div class="password-hint">At least 10 characters. Use a password unique to this app.</div>' : ""}</div><button class="btn full auth-submit" type="submit">${signup ? "Create account" : "Sign in"} ${icon("arrow")}</button></form><div class="auth-bottom">${signup ? 'Already have an account? <a href="#/signin">Sign in</a>' : 'New to the workspace? <a href="#/signup">Create an account</a>'}</div><p class="auth-note">This is a local development account, not a STAGE streaming login.<br>No verification email is sent. Account data stays on this computer.</p></div></main></div>`;
}

function renderShell() {
  const nav = [
    ["dashboard", "grid", "Overview"],
    ["viewers", "users", "Viewers"],
    ["decisions", "list", "Decisions"],
    ["experiments", "chart", "Experiments"],
    ["reports", "file", "Reports"],
    ["replays", "play", "Replay studio"],
  ];
  document.getElementById("app").innerHTML =
    `<aside class="sidebar" id="sidebar">${brand()}<div class="nav-label">WORKSPACE</div><nav aria-label="Main navigation">${nav.map(([id, ico, label]) => `<a class="nav-link" data-nav="${id}" href="#/${id}">${icon(ico)}${label}</a>`).join("")}</nav><div class="sidebar-bottom"><div class="local-card"><strong><span class="dot"></span> Local workspace</strong><small>Mock provider · real evidence.<br>Your data stays on this machine.</small></div><a class="nav-link" data-nav="account" href="#/account">${icon("settings")}Account settings</a><div class="side-account"><div class="avatar">${e(initials(state.user.name))}</div><div><div class="account-name">${e(state.user.name)}</div><div class="account-sub">Workspace member</div></div><button class="icon-btn" data-action="signout" title="Sign out" aria-label="Sign out">${icon("logout")}</button></div></div></aside><button class="scrim" data-action="menu" aria-label="Close navigation"></button><div class="workspace"><header class="topbar"><div class="breadcrumb"><button class="icon-btn mobile-toggle" data-action="menu" aria-label="Toggle navigation" aria-expanded="false">${icon("menu")}</button><span>Workspace</span><span>/</span><strong id="breadcrumb-title">Overview</strong></div><div class="top-actions">${pill("Local only", "green", true)}<span class="divider"></span><label class="sr-only" for="run-select">Selected result run</label><select class="run-select" id="run-select">${runOptions()}</select><a href="#/account" class="avatar" aria-label="Account settings">${e(initials(state.user.name))}</a></div></header><main class="content" id="main-content" tabindex="-1"></main></div>`;
}
function runOptions() {
  return state.runs.length
    ? state.runs
        .map(
          (run) =>
            `<option value="${e(run.id)}" ${run.id === state.run ? "selected" : ""}>${e(run.label)}</option>`,
        )
        .join("")
    : '<option value="sample">No completed runs</option>';
}
async function refreshRuns() {
  const data = await api("/api/runs");
  state.runs = data.runs;
  state.canRun = data.can_run;
  if (!state.runs.some((r) => r.id === state.run))
    state.run = state.runs[0]?.id || "sample";
  const select = document.getElementById("run-select");
  if (select) select.innerHTML = runOptions();
}
async function selectRun(id) {
  state.run = id;
  state.page = 1;
  state.query = "";
  state.filter = "";
  const select = document.getElementById("run-select");
  if (select) select.value = id;
  await route();
}

async function route() {
  if (!state.user) return renderAuth();
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  let target = parts[0] || "dashboard";
  if (["signin", "signup"].includes(target)) {
    location.hash = "#/dashboard";
    return;
  }
  if (
    ![
      "dashboard",
      "viewers",
      "decisions",
      "experiments",
      "reports",
      "replays",
      "account",
    ].includes(target)
  )
    target = "dashboard";
  if (state.route !== target) {
    state.page = 1;
    state.query = "";
    state.filter = "";
  }
  state.route = target;
  const version = ++state.version;
  const labels = {
    dashboard: "Overview",
    viewers: "Viewers",
    decisions: "Decisions",
    experiments: "Experiments",
    reports: "Reports",
    replays: "Replay studio",
    account: "Account settings",
  };
  document.title = `${labels[target]} · STAGE`;
  document.getElementById("sidebar")?.classList.remove("open");
  document
    .querySelector(".mobile-toggle")
    ?.setAttribute("aria-expanded", "false");
  document.querySelectorAll("[data-nav]").forEach((node) => {
    node.classList.toggle("active", node.dataset.nav === target);
    node.setAttribute(
      "aria-current",
      node.dataset.nav === target ? "page" : "false",
    );
  });
  document.getElementById("breadcrumb-title").textContent = labels[target];
  const main = document.getElementById("main-content");
  main.innerHTML =
    '<div class="loading-panel" role="status"><span class="spinner"></span>Loading your workspace…</div>';
  try {
    let html;
    if (!state.runs.length && !["replays", "account"].includes(target))
      html = empty(
        "No completed runs yet",
        "Start a replay in the replay studio. Its completed results will appear here.",
        '<a class="btn" href="#/replays">Open replay studio</a>',
      );
    else if (target === "dashboard") html = await dashboard();
    else if (target === "viewers")
      html = parts[1] ? await viewerDetail(parts[1]) : await viewers();
    else if (target === "decisions") html = await decisions();
    else if (target === "experiments") html = await experiments();
    else if (target === "reports") html = await reports();
    else if (target === "replays") html = await replays();
    else html = account();
    if (version === state.version && state.user) {
      main.innerHTML = html + footer();
    }
  } catch (error) {
    if (version === state.version && state.user)
      main.innerHTML = empty(
        "We couldn’t load this page",
        error.message,
        '<button class="btn secondary" data-action="retry">Try again</button>',
      );
  }
}

async function dashboard() {
  const [s, recent] = await Promise.all([
    api(runUrl("/api/summary")),
    api(runUrl("/api/decisions")),
  ]);
  const ratio = s.decisions ? s.actions / s.decisions : 0;
  const max = Math.max(1, ...s.timeline.map((p) => p.count));
  const totalGoals = Object.values(s.outcomes).reduce((a, b) => a + b, 0);
  const policy = s.simulator.policy_problem_count;
  return (
    pageHeader(
      "Overview",
      "A clear view of every decision, action, and outcome.",
      '<a class="btn" href="#/replays">' + icon("play") + " New replay</a>",
      state.run === "sample" ? "Sample replay" : "Your replay",
    ) +
    `<div class="stats">${stat("Decisions", n(s.decisions), "Unique triggers, after deduplication", "grid")}${stat("Published pages", n(s.actions), "Passed the independent verifier", "bolt")}${stat("Abstentions", n(s.abstentions), "A recorded reason for doing nothing", "shield")}${stat("Maximum latency", ms(s.latency.max_ms), "Entry to durable decision release", "clock")}</div>
  <div class="grid two"><section class="card"><div class="card-head"><div><h2>Decision activity</h2><p>Replay day · IST (UTC +05:30)</p></div><div class="chart-legend"><span class="legend-item"><span class="legend-box"></span>Unique decisions</span></div></div><div class="card-body"><div class="bar-chart" role="group" aria-label="Decisions by IST hour">${s.timeline.map((p) => `<button class="bar" style="height:${Math.max(1, (p.count / max) * 100)}%" title="${e(p.hour)} IST · ${n(p.count)} decisions" aria-label="${e(p.hour)} IST: ${n(p.count)} decisions"></button>`).join("")}</div><div class="chart-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span></div><p class="chart-footnote">Historical replay activity, not live production traffic.</p></div></section><section class="card"><div class="card-head"><div><h2>Action mix</h2><p>Safe action and deliberate abstention</p></div></div><div class="card-body"><div class="donut-layout"><div class="donut" style="--portion:${ratio * 100}%" role="img" aria-label="${pct(ratio)} of decisions published a page"><div class="donut-center">${pct(ratio)}<small>published a page</small></div></div><div class="legend-stack"><div><span class="legend-item"><span class="legend-box"></span>Home page</span><strong class="legend-value">${n(s.actions)}</strong></div><div><span class="legend-item"><span class="legend-box" style="background:#ded6f2"></span>No action</span><strong class="legend-value">${n(s.abstentions)}</strong></div></div></div></div></section></div>
  <div class="grid equal section-gap"><section class="card"><div class="card-head"><div><h2>Safety & reliability</h2><p>Checks reported by this replay</p></div>${policy === 0 ? pill("Checks clear", "green", true) : pill("Review needed", "amber")}</div><div class="card-body"><div class="mini-status"><span>Simulator policy violations</span><strong>${policy === undefined ? "Unavailable" : n(policy)}</strong></div><div class="mini-status"><span>Decisions over 60 seconds</span><strong>${s.latency.over_60s === undefined ? "Unavailable" : n(s.latency.over_60s)}</strong></div><div class="mini-status"><span>Fallback decisions</span><strong>${n(s.fallbacks)}</strong></div><div class="mini-status"><span>Independent artifact audit</span>${s.audit.passed === true ? pill("Passed", "green") : pill("Not available", "amber")}</div></div></section><section class="card"><div class="card-head"><div><h2>Goal attempts</h2><p>Adaptive goal judgments · ${n(totalGoals)} attempts</p></div><a href="#/experiments" class="text-link">See experiment ${icon("arrow")}</a></div><div class="card-body"><div class="mini-status"><span>Observed success</span><strong>${n(s.outcomes.succeeded)}</strong></div><div class="mini-status"><span>No success in window</span><strong>${n(s.outcomes.failed)}</strong></div><div class="mini-status"><span>Inconclusive</span><strong>${n(s.outcomes.inconclusive)}</strong></div><p class="chart-footnote">An observed success does not prove the intervention caused it. Use randomized comparisons to assess impact.</p></div></section></div>
  <section class="card table-card section-gap"><div class="card-head"><div><h2>Recent decisions</h2><p>Inspect what the agent knew and chose</p></div><a class="text-link" href="#/decisions">View all ${icon("arrow")}</a></div>${decisionTable(recent.decisions.slice(0, 5))}</section>`
  );
}
function stat(label, value, caption, ico) {
  return `<div class="card stat-card"><div class="stat-top">${e(label)}<span class="stat-icon">${icon(ico)}</span></div><div class="stat-value">${e(value)}</div><div class="stat-caption">${e(caption)}</div></div>`;
}
function decisionTable(rows) {
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Viewer</th><th>Goal</th><th>Action</th><th>Dialect</th><th>Decision time</th><th>Published (IST)</th></tr></thead><tbody>${rows.length ? rows.map((d) => `<tr><td><a class="viewer-link mono" href="#/viewers/${encodeURIComponent(d.viewer_id)}">${e(d.viewer_id)}</a></td><td>${d.goal ? pill(d.goal.id, "purple") : "—"}</td><td>${actionPill(d.action)}</td><td>${e(d.dialect.used || "Unknown")}</td><td class="mono">${ms(d.decided_in_ms)}</td><td>${e(date(d.published_at))}</td></tr>`).join("") : '<tr><td colspan="6">No matching decisions.</td></tr>'}</tbody></table></div>`;
}
function pager(data) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  return `<div class="table-foot"><span>${n(data.total)} results · Page ${data.page} of ${pages}</span><div class="pagination"><button class="btn secondary small" data-action="page" data-page="${data.page - 1}" ${data.page <= 1 ? "disabled" : ""}>Previous</button><button class="btn secondary small" data-action="page" data-page="${data.page + 1}" ${data.page >= pages ? "disabled" : ""}>Next</button></div></div>`;
}
function searchBox(placeholder) {
  return `<div class="search-field">${icon("search")}<label class="sr-only" for="search">${e(placeholder)}</label><input type="search" id="search" placeholder="${e(placeholder)}" value="${e(state.query)}" maxlength="100"></div>`;
}
async function viewers() {
  const data = await api(
    runUrl("/api/viewers", {
      q: state.query,
      arm: state.filter,
      page: state.page,
    }),
  );
  return (
    pageHeader(
      "Viewers",
      "Follow a viewer from evidence to decision to outcome.",
    ) +
    `<div class="filters">${searchBox("Search by viewer ID…")}<label class="sr-only" for="list-filter">Randomized arm</label><select class="filter-select" id="list-filter"><option value="">All arms</option><option value="agent" ${state.filter === "agent" ? "selected" : ""}>Agent arm</option><option value="holdout" ${state.filter === "holdout" ? "selected" : ""}>Holdout arm</option></select><span class="filter-note">Synthetic viewer identities</span></div><div class="card"><div class="table-wrap"><table class="data-table"><thead><tr><th>Viewer ID</th><th>Arm</th><th>Dialect</th><th>Decisions</th><th>Pages</th><th>Latest goal</th><th>Last decision</th></tr></thead><tbody>${data.viewers.length ? data.viewers.map((v) => `<tr><td><a class="viewer-link mono" href="#/viewers/${encodeURIComponent(v.id)}">${e(v.id)}</a></td><td>${pill(v.arm, v.arm === "agent" ? "purple" : "")}</td><td>${e(v.dialect || "Unknown")}</td><td>${n(v.decisions)}</td><td>${n(v.actions)}</td><td>${e(v.goal || "—")}</td><td>${actionPill(v.last_action)}</td></tr>`).join("") : '<tr><td colspan="7">No matching viewers. Try a different ID or arm.</td></tr>'}</tbody></table></div>${pager(data)}</div>`
  );
}
async function decisions() {
  const data = await api(
    runUrl("/api/decisions", {
      q: state.query,
      action: state.filter,
      page: state.page,
    }),
  );
  return (
    pageHeader(
      "Decisions",
      "Every action and abstention has a reason you can inspect.",
    ) +
    `<div class="filters">${searchBox("Search viewer or decision ID…")}<label class="sr-only" for="list-filter">Decision action</label><select class="filter-select" id="list-filter"><option value="">All decisions</option><option value="HOME_PAGE" ${state.filter === "HOME_PAGE" ? "selected" : ""}>Home page</option><option value="NO_ACTION" ${state.filter === "NO_ACTION" ? "selected" : ""}>No action</option></select><span class="filter-note">Open a viewer to inspect the full trace</span></div><div class="card">${decisionTable(data.decisions)}${pager(data)}</div>`
  );
}
async function viewerDetail(id) {
  const d = await api(runUrl("/api/viewers/" + encodeURIComponent(id)));
  const last = d.decisions.at(-1),
    facts = last.facts || {};
  return `<a class="back-link" href="#/viewers">${icon("arrow")}Back to viewers</a><div class="page-header"><div class="detail-header"><div class="avatar">${icon("users")}</div><div><h1>${e(d.viewer.id)}</h1><p class="muted">${e(d.viewer.arm)} arm · ${n(d.decisions.length)} decisions · ${n(d.actions.length)} home pages</p></div></div>${pill("Synthetic viewer", "purple")}</div><div class="detail-grid"><section class="card"><div class="card-head"><div><h2>Decision timeline</h2><p>Facts and checks captured at each decision</p></div></div><div class="card-body"><div class="timeline">${d.decisions.map((item) => `<article class="event-item"><h3>${actionPill(item.action)}${item.goal ? pill(item.goal.id, "purple") : ""}${item.fallback_used ? pill("Fallback", "amber") : ""}</h3><time>${e(date(item.trigger.deliver_at))} · ${ms(item.decided_in_ms)}</time><p>${e(item.no_action_reason || (item.goal?.name || "").replaceAll("_", " "))}</p>${item.goal ? `<p>Deadline: ${e(date(item.goal.deadline))} · Signal: <span class="mono">${e(item.goal.success_signal.event)}</span></p>` : ""}<div class="checks">${(item.checks.passed || []).map((c) => pill(c.replaceAll("_", " "), "green")).join("")}${(item.checks.failed || []).map((c) => pill(c.replaceAll("_", " "), "red")).join("")}</div><details><summary>Inspect decision evidence</summary><pre class="raw-json">${e(JSON.stringify(item, null, 2))}</pre></details></article>`).join("")}</div></div></section><div class="grid"><section class="card"><div class="card-head"><div><h2>Resolved facts</h2><p>As of the latest decision, not today</p></div></div><div class="card-body"><div class="fact-list">${
    Object.entries(facts)
      .map(
        ([key, fact]) =>
          `<div class="fact"><div class="fact-label">${e(key.replaceAll("_", " "))}</div><div class="fact-value">${e(fact.value)}</div><div class="fact-source">Source: ${e(fact.source)}<br>Evidence age at decision: ${n(Math.round(fact.age_s || 0))} seconds</div></div>`,
      )
      .join("") || '<p class="muted small">No trusted facts were available.</p>'
  }</div></div></section><section class="card"><div class="card-head"><h2>Goal outcomes</h2></div><div class="card-body">${d.outcomes.length ? d.outcomes.map((j) => `<div class="fact"><div class="inline-meta"><strong>${e(j.goal_id)}</strong>${statusPill(j.status)}</div><p class="fact-source">${e(j.learning)}</p><p class="fact-source">${n(j.evidence.length)} matching signals · deadline ${e(date(j.deadline))}</p></div>`).join("") : '<p class="small muted">No measurable goal was committed.</p>'}</div></section><section class="card"><div class="card-head"><h2>Source conflicts</h2></div><div class="card-body">${last.conflicts?.length ? `<pre class="raw-json">${e(JSON.stringify(last.conflicts, null, 2))}</pre>` : '<p class="small muted">No conflicting resolved facts at the latest decision.</p>'}</div></section></div></div>`;
}

async function experiments() {
  const d = await api(runUrl("/api/experiments"));
  const primary = d.metrics.baseline_goal_itt;
  const counts = primary?.counts || {};
  return (
    pageHeader(
      "Experiments",
      "Compare randomized arms without hiding missing outcomes.",
      pill("Baseline-goal analysis", "purple"),
    ) +
    notice(
      "No identified population uplift",
      "Missing follow-up prevents a single full-population goal-success estimate. The bounds below show what remains possible; they are not a rollout recommendation.",
    ) +
    `<div class="grid equal section-gap">${["agent", "holdout"]
      .map((arm) => {
        const c = counts[arm] || {
          n: 0,
          succeeded: 0,
          failed: 0,
          inconclusive: 0,
        };
        return `<section class="card arm-card"><div class="arm-heading"><h2>${arm === "agent" ? "Agent arm" : "Holdout arm"}</h2>${pill(arm === "agent" ? "Eligible for intervention" : "No interventions", arm === "agent" ? "purple" : "")}</div><div class="arm-total">${n(c.n)}<small>randomized viewers</small></div><div class="stack-bar" role="img" aria-label="${c.succeeded} successes, ${c.failed} failures, ${c.inconclusive} inconclusive">${[
          ["succeeded", "#8c75d9"],
          ["failed", "#d7d0e9"],
          ["inconclusive", "#f0e7ce"],
        ]
          .map(
            ([key, color]) =>
              `<span class="stack-segment" style="width:${c.n ? (c[key] / c.n) * 100 : 0}%;background:${color}"></span>`,
          )
          .join(
            "",
          )}</div><div class="outcome-key"><div>Observed success<strong>${n(c.succeeded)}</strong></div><div>Failed<strong>${n(c.failed)}</strong></div><div>Inconclusive<strong>${n(c.inconclusive)}</strong></div></div><div class="metric-callout"><span>Possible success rate</span><strong>${c.success_rate_bounds ? `${pct(c.success_rate_bounds[0])} – ${pct(c.success_rate_bounds[1])}` : "Unavailable"}</strong></div></section>`;
      })
      .join(
        "",
      )}</div><section class="card section-gap"><div class="card-head"><div><h2>Full-arm uncertainty</h2><p>All assigned viewers remain in their randomized arm</p></div></div><div class="card-body"><div class="mini-status"><span>Goal-success difference bounds</span><strong>${bounds(primary?.difference_bounds)}</strong></div><div class="mini-status"><span>95% sampling envelope</span><strong>${bounds(primary?.ci95_envelope)}</strong></div><p class="chart-footnote">Baseline goals are frozen before the first intervention. Missing follow-up and unavailable goals are inconclusive, not failed. Comparing served viewers with everyone else would introduce selection bias.</p></div></section><section class="card table-card section-gap"><div class="card-head"><div><h2>Baseline goal breakdown</h2><p>Missing-outcome bounds, including abstentions</p></div><a href="#/reports" class="text-link">Read full report ${icon("arrow")}</a></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Goal</th><th>Agent viewers</th><th>Holdout viewers</th><th>Difference bounds</th><th>95% envelope</th></tr></thead><tbody>${Object.entries(
      d.goals,
    )
      .map(
        ([gid, g]) =>
          `<tr><td>${pill(gid, "purple")}</td><td>${n(g.counts.agent.n)}</td><td>${n(g.counts.holdout.n)}</td><td class="mono">${bounds(g.difference_bounds)}</td><td class="mono">${bounds(g.ci95_envelope)}</td></tr>`,
      )
      .join("")}</tbody></table></div></section>`
  );
}
async function reports() {
  const d = await api(runUrl("/api/reports"));
  return (
    pageHeader(
      "Reports",
      "The evidence behind the dashboard, ready to inspect or download.",
    ) +
    `<div class="report-grid">${d.reports.map((r) => `<article class="card report-card"><div class="report-icon">${icon(r.file.endsWith(".md") ? "file" : "chart")}</div><h3>${e(r.title)}</h3><p>${e(r.description)}</p><div class="report-actions"><button class="btn secondary small" data-action="report" data-file="${e(r.file)}" data-title="${e(r.title)}">Read report ${icon("arrow")}</button><a class="icon-btn" href="${e(runUrl("/api/report", { file: r.file, download: "1" }))}" aria-label="Download ${e(r.title)}" title="Download">${icon("download")}</a></div></article>`).join("")}</div><section class="card report-preview" id="report-preview" hidden><div class="card-head"><h2 id="report-title"></h2><button class="icon-btn" data-action="close-report" aria-label="Close report">×</button></div><pre id="report-content"></pre></section>`
  );
}
async function replays() {
  const d = await api("/api/jobs");
  state.jobs = d.jobs;
  return (
    pageHeader(
      "Replay studio",
      "Run the full decide → act → measure loop on your local data.",
    ) +
    `<div class="replay-grid"><section class="card replay-intro"><div class="report-icon">${icon("play")}</div><h2>Start a new replay</h2><p>Replay the supplied events, run the outcome simulator, and audit the exported decisions. Results are saved to your account.</p>${!state.canRun ? notice("Assignment pack required", "The included sample works now. To start a new run, extract the supplied ZIP into data_pack/ and keep its data/, config/, replay/, and simulator/ folders inside.") : ""}<div class="replay-steps"><div class="replay-step"><span class="step-num">1</span>Resolve evidence and make verified decisions</div><div class="replay-step"><span class="step-num">2</span>Simulate behavior and judge goal windows</div><div class="replay-step"><span class="step-num">3</span>Measure impact and independently audit actions</div></div><div id="job-error"></div><form id="replay-form"><div class="field"><label for="seed">Simulator seed</label><input id="seed" name="seed" value="oua-practice" pattern="[A-Za-z0-9_.-]{1,64}" maxlength="64" required ${!state.canRun ? "disabled" : ""}><small>The same seed makes simulator randomness reproducible.</small></div><button class="btn full" type="submit" ${!state.canRun ? "disabled" : ""}>${icon("play")}Start replay</button></form><p class="auth-note">Runs locally without a model API key. Processing time depends on your computer. One replay runs at a time.</p></section><section class="card"><div class="card-head"><div><h2>Your replay history</h2><p>Completed runs can be opened across the workspace</p></div><button class="icon-btn" data-action="refresh-jobs" aria-label="Refresh replay history">${icon("clock")}</button></div><div id="job-list" class="section-gap">${jobsHtml(d.jobs)}</div></section></div>`
  );
}
function jobsHtml(jobs) {
  return jobs.length
    ? jobs
        .map(
          (j) =>
            `<div class="job-row"><div class="report-icon" style="width:34px;height:34px;margin:0">${icon("play")}</div><div class="job-info"><strong>${e(j.seed)}</strong><p>${e(date(j.created_at))}${j.finished_at ? ` · finished ${e(date(j.finished_at))}` : ""}</p>${j.error ? `<p style="color:var(--red)">${e(j.error)}</p>` : ""}</div><div class="job-actions">${statusPill(j.status)}${j.status === "completed" ? `<button class="btn secondary small" data-action="open-run" data-id="${e(j.id)}">Open ${icon("arrow")}</button>` : ["running", "queued"].includes(j.status) ? `<button class="btn ghost small" data-action="cancel-job" data-id="${e(j.id)}">Cancel</button>` : ""}</div></div>`,
        )
        .join("")
    : '<div class="empty-state"><span class="empty-icon">' +
        icon("clock") +
        "</span><h2>No replays yet</h2><p>Start your first replay, or explore the included sample using the run selector above.</p></div>";
}
async function refreshJobs() {
  if (!state.user || state.route !== "replays") return;
  const d = await api("/api/jobs");
  const before = new Map(state.jobs.map((j) => [j.id, j.status]));
  state.jobs = d.jobs;
  const list = document.getElementById("job-list");
  if (list) list.innerHTML = jobsHtml(d.jobs);
  if (
    d.jobs.some(
      (j) =>
        j.status === "completed" &&
        before.has(j.id) &&
        before.get(j.id) !== "completed",
    )
  ) {
    await refreshRuns();
    toast("Replay complete. Open its results from the history.");
  }
}
function account() {
  return (
    pageHeader(
      "Account settings",
      "Manage your local profile and sign-in security.",
    ) +
    `<div class="account-grid"><section class="card"><div class="card-head"><div><h2>Profile & password</h2><p>Changes apply to this local website</p></div></div><div class="card-body"><div id="account-error"></div><form id="account-form"><div class="field"><label for="account-name">Full name</label><input id="account-name" name="name" value="${e(state.user.name)}" minlength="2" maxlength="60" autocomplete="name" required></div><div class="field"><label for="account-email">Email address</label><input id="account-email" value="${e(state.user.email)}" readonly><small>Email changes are not supported in this local version.</small></div><hr class="form-divider"><h3>Change password</h3><p class="form-help">Leave these fields blank to keep your current password.</p><div class="field"><label for="current-password">Current password</label><input id="current-password" name="current_password" type="password" autocomplete="current-password" maxlength="128"></div><div class="form-grid"><div class="field"><label for="new-password">New password</label><input id="new-password" name="new_password" type="password" autocomplete="new-password" minlength="10" maxlength="128"></div><div class="field"><label for="confirm-password">Confirm new password</label><input id="confirm-password" name="confirm_password" type="password" autocomplete="new-password" maxlength="128"></div></div><button class="btn" type="submit">Save changes ${icon("check")}</button></form></div></section><section class="card account-intro"><div class="avatar">${e(initials(state.user.name))}</div><h3>${e(state.user.name)}</h3><p>${e(state.user.email)}</p><div class="account-list">Joined ${e(date(state.user.created_at))}<br>Local password account<br>No email verification or recovery service</div><hr class="form-divider"><h3>Other sessions</h3><p class="form-help">Sign out other browsers signed in to this account. This browser stays signed in.</p><button class="btn secondary small" data-action="revoke-sessions">${icon("lock")}Sign out other sessions</button><hr class="form-divider"><button class="btn danger small" data-action="signout">${icon("logout")}Sign out of this browser</button></section></div>`
  );
}

async function signedIn(user) {
  state.user = user;
  state.run = "sample";
  await refreshRuns();
  renderShell();
  location.hash = "#/dashboard";
  await route();
}
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!["auth-form", "replay-form", "account-form"].includes(form.id)) return;
  event.preventDefault();
  const button = form.querySelector("[type=submit]");
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "Please wait…";
  const body = Object.fromEntries(new FormData(form));
  try {
    if (form.id === "auth-form") {
      const result = await post("/api/auth/" + form.dataset.mode, body);
      await signedIn(result.user);
    } else if (form.id === "replay-form") {
      await post("/api/jobs", body);
      await refreshJobs();
      toast("Replay started. You can keep exploring while it runs.");
    } else {
      if (body.new_password !== body.confirm_password)
        throw new Error("The new passwords do not match.");
      const result = await post("/api/account", body);
      state.user = result.user;
      renderShell();
      await route();
      toast("Your account has been updated.");
    }
  } catch (error) {
    showError(
      form.id === "auth-form"
        ? "auth-error"
        : form.id === "replay-form"
          ? "job-error"
          : "account-error",
      error.message,
    );
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
});
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  try {
    if (action === "password") {
      const input = document.getElementById(button.dataset.target);
      input.type = input.type === "password" ? "text" : "password";
      button.setAttribute(
        "aria-label",
        input.type === "password" ? "Show password" : "Hide password",
      );
      button.setAttribute("aria-pressed", input.type === "text");
    } else if (action === "menu") {
      const sidebar = document.getElementById("sidebar");
      sidebar.classList.toggle("open");
      document
        .querySelector(".mobile-toggle")
        ?.setAttribute("aria-expanded", sidebar.classList.contains("open"));
    } else if (action === "signout") {
      await post("/api/auth/signout");
      state.user = null;
      state.jobs = [];
      location.hash = "#/signin";
      renderAuth();
    } else if (action === "retry") await route();
    else if (action === "page") {
      state.page = Number(button.dataset.page);
      await route();
    } else if (action === "refresh-jobs") await refreshJobs();
    else if (action === "cancel-job") {
      await post("/api/jobs/" + button.dataset.id + "/cancel");
      await refreshJobs();
      toast("Replay cancelled. Partial results will not be shown.");
    } else if (action === "open-run") {
      state.run = button.dataset.id;
      await refreshRuns();
      document.getElementById("run-select").value = state.run;
      location.hash = "#/dashboard";
    } else if (action === "revoke-sessions") {
      await post("/api/auth/revoke-others");
      toast("Other sessions have been signed out.");
    } else if (action === "close-report")
      document.getElementById("report-preview").hidden = true;
    else if (action === "report") {
      const version = state.version;
      const response = await fetch(
        runUrl("/api/report", { file: button.dataset.file }),
      );
      if (!response.ok)
        throw new Error("This report is unavailable. Refresh and try again.");
      const text = await response.text();
      if (version !== state.version) return;
      document.getElementById("report-title").textContent =
        button.dataset.title;
      document.getElementById("report-content").textContent = text;
      const panel = document.getElementById("report-preview");
      panel.hidden = false;
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    toast(error.message, true);
  }
});
document.addEventListener("change", async (event) => {
  if (event.target.id === "run-select") await selectRun(event.target.value);
  if (event.target.id === "list-filter") {
    state.filter = event.target.value;
    state.page = 1;
    await route();
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "search") {
    clearTimeout(searchTimer);
    state.query = event.target.value;
    state.page = 1;
    searchTimer = setTimeout(async () => {
      const pos = state.query.length;
      await route();
      const input = document.getElementById("search");
      if (input) {
        input.focus();
        if (input.type !== "search") input.setSelectionRange(pos, pos);
      }
    }, 350);
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.getElementById("sidebar")?.classList.remove("open");
    document
      .querySelector(".mobile-toggle")
      ?.setAttribute("aria-expanded", "false");
  }
});
window.addEventListener("hashchange", () => route());
setInterval(() => refreshJobs().catch(() => {}), 3000);
(async () => {
  try {
    const data = await api("/api/auth/me");
    state.user = data.user;
    await refreshRuns();
    renderShell();
    await route();
  } catch {
    state.user = null;
    renderAuth();
  }
})();
