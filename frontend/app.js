/* Long Video Session Planner, presentation tier.
   Talks to the FastAPI backend under /api/v1. The schedule is computed on the server;
   this file handles auth screens, the plan form (autosaved), rendering, and
   reading the video length from the YouTube player when no server API key is set. */
"use strict";

const $ = id => document.getElementById(id);
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];
const API = "/api/v1";

/* ---------- small helpers ---------- */
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])) }
function todayISO() { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10) }
function localDate(iso) { return new Date(iso + "T00:00:00") }
function fmt(sec) { sec = Math.round(sec); const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60; return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` }
function human(sec) { const m = Math.round(sec / 60); const h = Math.floor(m / 60); return h ? `${h}h ${m % 60}m` : `${m}m` }
function videoId(u) {
  if (!u) return "";
  const m = u.match(/(?:v=|youtu\.be\/|\/live\/|\/embed\/|\/shorts\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : (/^[A-Za-z0-9_-]{11}$/.test(u.trim()) ? u.trim() : "");
}
function link(id, t) { return id ? `https://www.youtube.com/watch?v=${id}&t=${Math.floor(t)}s` : "" }
function lsGet(k) { try { return localStorage.getItem(k) } catch (e) { return null } }
function lsSet(k, v) { try { localStorage.setItem(k, v) } catch (e) { } }
function toast(t) { const el = $("toast"); el.textContent = t; el.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => el.hidden = true, 1800) }

/* ---------- API client ---------- */
class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status } }

function errMsg(data, status) {
  const det = data && data.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det) && det.length) return det.map(x => String(x.msg || "").replace(/^Value error, /, "")).join(" ");
  return `Request failed (${status})`;
}

async function api(method, path, body) {
  // X-Requested-With is required by the server for state-changing calls (CSRF guard).
  const opts = { method, headers: { "X-Requested-With": "planner" }, credentials: "same-origin" };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body) }
  let r;
  try { r = await fetch(API + path, opts) } catch (e) { throw new ApiError(0, "Can't reach the server. Is it running?") }
  if (r.status === 204) return null;
  let data = null;
  try { data = await r.json() } catch (e) { }
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith("/auth/")) showAuth("Your session ended. Log in again.");
    throw new ApiError(r.status, errMsg(data, r.status));
  }
  return data;
}

/* ---------- app state ---------- */
let me = null;          // {id, email}
let cfg = { youtube_api: false };
let plans = [];         // PlanSummary[]
let current = null;     // PlanDetail {plan, schedule, done}

/* ---------- auth view ---------- */
let authMode = "login";
function setAuthMode(m) {
  authMode = m;
  $("tabLogin").setAttribute("aria-selected", m === "login");
  $("tabRegister").setAttribute("aria-selected", m === "register");
  $("authTitle").textContent = m === "login" ? "Sign in" : "Create your account";
  $("authSubmit").textContent = m === "login" ? "Log in" : "Create account";
  $("password").autocomplete = m === "login" ? "current-password" : "new-password";
  $("pwHint").hidden = m === "login";
  $("authErr").hidden = true;
}
function showAuth(msg) {
  me = null; current = null; plans = [];
  $("booting").hidden = true; $("appView").hidden = true; $("userBox").hidden = true; $("authView").hidden = false;
  if (msg) { $("authErr").textContent = msg; $("authErr").hidden = false }
  $("email").focus();
}
$("tabLogin").addEventListener("click", () => setAuthMode("login"));
$("tabRegister").addEventListener("click", () => setAuthMode("register"));
$("authForm").addEventListener("submit", async e => {
  e.preventDefault();
  const email = $("email").value.trim(), password = $("password").value, err = $("authErr");
  err.hidden = true;
  if (!email || !password) { err.textContent = "Enter your email and password."; err.hidden = false; return }
  if (authMode === "register" && password.length < 8) { err.textContent = "Use at least 8 characters for the password."; err.hidden = false; return }
  $("authSubmit").disabled = true;
  try {
    me = await api("POST", authMode === "login" ? "/auth/login" : "/auth/register", { email, password });
    $("password").value = "";
    await enterApp();
  } catch (ex) { err.textContent = ex.message; err.hidden = false }
  finally { $("authSubmit").disabled = false }
});
$("logout").addEventListener("click", async () => {
  await flushSave();
  try { await api("POST", "/auth/logout") } catch (e) { }
  showAuth();
  setAuthMode("login");
});

/* ---------- plans ---------- */
function defaultPlan(title) {
  return { title: title || "My first plan", video_url: "", duration: "10:00:00", chapters: "", minutes_per_day: 60, speed: 1, start_date: todayISO(), snap_to_chapters: true, weekdays: ALL_DAYS };
}

// One-time import of progress saved by the old single-file version (localStorage "lvsp").
async function importLegacy() {
  let s = null;
  try { if (!lsGet("lvsp_imported")) s = JSON.parse(lsGet("lvsp") || "null") } catch (e) { }
  if (!s || typeof s !== "object") return null;
  lsSet("lvsp_imported", "1");
  const body = {
    title: "Imported plan", video_url: s.url || "", duration: s.dur || "10:00:00", chapters: s.chap || "",
    minutes_per_day: Number(s.mins) || 60, speed: Number(s.speed) || 1, start_date: s.start || todayISO(),
    snap_to_chapters: s.snap !== "0", weekdays: Array.isArray(s.days) && s.days.length ? s.days.map(Number) : ALL_DAYS,
  };
  let d;
  try { d = await api("POST", "/plans", body) } catch (e) { return null }
  const ticks = (s.done || {})[videoId(s.url || "") || "sample"] || {};
  for (const [i, v] of Object.entries(ticks)) {
    if (v) { try { await api("PUT", `/plans/${d.plan.id}/progress/${Number(i)}`, { done: true }) } catch (e) { } }
  }
  toast("Imported your plan from this browser");
  return d;
}

async function enterApp() {
  $("booting").hidden = true; $("authView").hidden = true; $("appView").hidden = false; $("userBox").hidden = false;
  $("userEmail").textContent = me.email;
  plans = await api("GET", "/plans");
  if (!plans.length) {
    if (!(await importLegacy())) await api("POST", "/plans", defaultPlan());
    plans = await api("GET", "/plans");
  }
  const last = Number(lsGet("lvsp_last_plan"));
  await openPlan((plans.find(p => p.id === last) || plans[0]).id);
}

async function refreshPlanList() {
  plans = await api("GET", "/plans");
  renderPlanSelect();
}

function renderPlanSelect() {
  const sel = $("planSelect");
  sel.innerHTML = plans.map(p => `<option value="${p.id}">${esc(p.title)} · ${p.sessions_done}/${p.sessions_total} done</option>`).join("");
  if (current) sel.value = String(current.plan.id);
}

async function openPlan(id) {
  await flushSave();
  detectRun++; // cancel any length detection for the previous plan
  current = await api("GET", `/plans/${id}`);
  lsSet("lvsp_last_plan", String(id));
  lastDetected = current.plan.video_id;
  fillForm(current.plan);
  $("durStatus").hidden = true; $("err").hidden = true; $("saved").textContent = "";
  renderPlanSelect();
  render();
}

$("planSelect").addEventListener("change", e => openPlan(Number(e.target.value)).catch(err => toast(err.message)));
$("newPlan").addEventListener("click", async () => {
  try {
    await flushSave();
    const d = await api("POST", "/plans", defaultPlan("New plan"));
    await refreshPlanList();
    await openPlan(d.plan.id);
    $("url").focus();
  } catch (e) { toast(e.message) }
});
$("deletePlan").addEventListener("click", async () => {
  if (!current) return;
  if (!confirm(`Delete "${current.plan.title}" and its progress? This can't be undone.`)) return;
  try {
    clearTimeout(saveTimer); dirty = false;
    await api("DELETE", `/plans/${current.plan.id}`);
    current = null;
    plans = await api("GET", "/plans");
    if (!plans.length) { await api("POST", "/plans", defaultPlan()); plans = await api("GET", "/plans") }
    await openPlan(plans[0].id);
    toast("Plan deleted");
  } catch (e) { toast(e.message) }
});

/* ---------- form <-> plan ---------- */
function selectedDays() { return [...$("days").querySelectorAll('button[aria-pressed="true"]')].map(b => Number(b.dataset.d)) }

function fillForm(p) {
  $("title").value = p.title; $("url").value = p.video_url; $("dur").value = p.duration; $("chap").value = p.chapters;
  $("mins").value = p.minutes_per_day; $("speed").value = String(p.speed); $("start").value = p.start_date;
  $("snap").value = p.snap_to_chapters ? "1" : "0";
  $("days").innerHTML = [1, 2, 3, 4, 5, 6, 0].map(d => `<button type="button" data-d="${d}" aria-pressed="${p.weekdays.includes(d)}">${DOW[d]}</button>`).join("");
}

function readForm() {
  return {
    title: $("title").value, video_url: $("url").value, duration: $("dur").value, chapters: $("chap").value,
    minutes_per_day: Number($("mins").value), speed: Number($("speed").value), start_date: $("start").value || todayISO(),
    snap_to_chapters: $("snap").value === "1", weekdays: selectedDays(),
  };
}

/* ---------- autosave (debounced, serialized so saves can't land out of order) ---------- */
let saveTimer = null, dirty = false, saveChain = Promise.resolve();

function scheduleSave(delay = 400) {
  if (!current) return;
  dirty = true;
  $("saved").textContent = "Unsaved changes";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSave, delay);
}

function flushSave() {
  clearTimeout(saveTimer);
  if (!dirty || !current) return saveChain;
  dirty = false;
  const id = current.plan.id, body = readForm();
  saveChain = saveChain.then(() => doSave(id, body));
  return saveChain;
}

async function doSave(id, body) {
  $("saved").textContent = "Saving...";
  try {
    const d = await api("PUT", `/plans/${id}`, body);
    if (!current || current.plan.id !== id || dirty) return; // a newer edit is pending
    current = d;
    $("err").hidden = true; $("saved").textContent = "Saved";
    const s = plans.find(p => p.id === id);
    if (s) { s.title = d.plan.title; s.sessions_total = d.schedule.sessions.length; s.sessions_done = doneCount(); renderPlanSelect() }
    render();
  } catch (e) {
    if (dirty || e.status === 401) return;
    $("err").textContent = e.message; $("err").hidden = false; $("saved").textContent = "Not saved";
  }
}

// Last-chance save if the tab closes during the debounce window.
addEventListener("pagehide", () => {
  if (!dirty || !current) return;
  dirty = false;
  try {
    fetch(`${API}/plans/${current.plan.id}`, { method: "PUT", keepalive: true, credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Requested-With": "planner" }, body: JSON.stringify(readForm()) });
  } catch (e) { }
});

["title", "url", "dur", "chap", "mins", "start"].forEach(k => $(k).addEventListener("input", () => {
  scheduleSave();
  if (k === "url") { clearTimeout(detectTimer); detectTimer = setTimeout(detect, 500) }
  if (k === "dur") $("durStatus").hidden = true;
}));
["speed", "snap"].forEach(k => $(k).addEventListener("change", () => scheduleSave(0)));
$("cfg").addEventListener("submit", e => e.preventDefault());
$("days").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  const on = b.getAttribute("aria-pressed") === "true";
  if (on && selectedDays().length === 1) return; // keep at least one day
  b.setAttribute("aria-pressed", String(!on));
  scheduleSave(0);
});

/* ---------- rendering ---------- */
function doneCount() {
  if (!current) return 0;
  const n = current.schedule.sessions.length;
  return current.done.filter(i => i < n).length;
}

function render() {
  if (!current) return;
  const p = current.plan, s = current.schedule, list = $("list");
  const done = new Set(current.done), id = p.video_id, sp = p.speed, today = todayISO();
  const n = s.sessions.length, nd = doneCount(), last = s.sessions[n - 1];

  $("warn").innerHTML = s.warnings.map(esc).join("<br>");
  $("warn").hidden = !s.warnings.length;

  if (!n) { $("summary").innerHTML = ""; $("strip").innerHTML = ""; $("scale").innerHTML = ""; list.innerHTML = ""; return }

  $("summary").innerHTML = `
    <div class="stat"><div class="v">${n}</div><div class="k">sessions</div></div>
    <div class="stat"><div class="v">${esc(s.total_watch)}</div><div class="k">total watch time at ${sp}×</div></div>
    <div class="stat"><div class="v">${localDate(last.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div><div class="k">finish date</div></div>
    <div class="stat"><div class="v">${Math.round(nd / n * 100)}%</div><div class="k">${nd} of ${n} done</div></div>`;
  $("strip").innerHTML = s.sessions.map(x => `<span style="flex:${x.end_sec - x.start_sec}" class="${done.has(x.index) ? "done" : x.date === today ? "today" : ""}" title="Day ${x.index + 1}: ${x.start}–${x.end}" data-i="${x.index}"></span>`).join("");
  $("scale").innerHTML = `<span>0:00:00</span><span>${fmt(s.duration_sec / 2)}</span><span>${esc(s.duration)}</span>`;

  const next = s.sessions.find(x => !done.has(x.index));
  $("progressNote").textContent = !next ? "All sessions complete." : `Next up: Day ${next.index + 1}, starting at ${next.start}` + (id ? "" : ". Add the video link to enable the Open buttons.");

  list.innerHTML = s.sessions.map(x => {
    const i = x.index, isToday = x.date === today, isDone = done.has(i);
    const ch = [];
    if (x.continues) ch.push(`<li><span class="t">cont.</span>${esc(x.continues)}</li>`);
    x.chapters.forEach(c => ch.push(`<li><span class="t">${c.time}</span>${esc(c.title)}</li>`));
    return `<article class="day${isToday ? " is-today" : ""}${isDone ? " is-done" : ""}" id="day-${i}">
      <input type="checkbox" data-i="${i}" ${isDone ? "checked" : ""} aria-label="Mark day ${i + 1} done">
      <div style="min-width:0">
        <h3>Day ${i + 1} <span class="date">${localDate(x.date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</span>${isToday ? '<span class="pill">Today</span>' : ""}</h3>
        <div class="ts">${x.start} → ${x.end} · ${esc(x.watch)} at ${sp}×</div>
        ${ch.length ? `<ul class="chap">${ch.join("")}</ul>` : ""}
      </div>
      <div class="act">
        <a class="btn primary" href="${link(id, x.start_sec) || "#"}" target="_blank" rel="noopener" ${id ? "" : 'aria-disabled="true"'}>Open at ${x.start}</a>
      </div>
    </article>`;
  }).join("");
}

$("list").addEventListener("change", async e => {
  if (e.target.type !== "checkbox" || !current) return;
  const i = Number(e.target.dataset.i), on = e.target.checked;
  try {
    await flushSave(); // day numbers depend on the saved settings
    const id = current.plan.id;
    const done = await api("PUT", `/plans/${id}/progress/${i}`, { done: on });
    if (!current || current.plan.id !== id) return;
    current.done = done;
    const s = plans.find(p => p.id === id); if (s) { s.sessions_done = doneCount(); renderPlanSelect() }
    render();
  } catch (ex) { e.target.checked = !on; toast(ex.message) }
});
$("strip").addEventListener("click", e => { const i = e.target.dataset.i; if (i != null) $("day-" + i)?.scrollIntoView({ behavior: "smooth", block: "center" }) });
$("reset").addEventListener("click", async () => {
  if (!current) return;
  try {
    await api("DELETE", `/plans/${current.plan.id}/progress`);
    current.done = [];
    const s = plans.find(p => p.id === current.plan.id); if (s) { s.sessions_done = 0; renderPlanSelect() }
    render(); toast("Ticks cleared");
  } catch (e) { toast(e.message) }
});
$("copy").addEventListener("click", () => {
  if (!current) return;
  const p = current.plan, id = p.video_id;
  const txt = current.schedule.sessions.map(x => {
    const t = [x.continues, ...x.chapters.map(c => c.title)].filter(Boolean).join("; ");
    return `Day ${x.index + 1} (${localDate(x.date).toDateString()}): ${x.start} – ${x.end} [${x.watch}]${t ? " | " + t : ""}${id ? "\n  " + link(id, x.start_sec) : ""}`;
  }).join("\n");
  const fallback = () => { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); toast("Plan copied") } catch (e) { toast("Select and copy manually") } ta.remove() };
  if (navigator.clipboard) navigator.clipboard.writeText(txt).then(() => toast("Plan copied")).catch(fallback); else fallback();
});

/* ---------- length detection ----------
   1. Server-side YouTube Data API (exact length + chapters) when the server has a key.
   2. Otherwise a hidden YouTube player reads the length (whole seconds, may be 1 s high). */
let ytReady = null, player = null, lastDetected = "", detectTimer = null, detectRun = 0;

function loadYT() {
  if (ytReady) return ytReady;
  ytReady = new Promise((res, rej) => {
    if (window.YT && window.YT.Player) return res();
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev && prev(); res() };
    const sc = document.createElement("script"); sc.src = "https://www.youtube.com/iframe_api"; sc.onerror = () => rej(new Error("blocked"));
    document.head.appendChild(sc); setTimeout(() => rej(new Error("timeout")), 10000);
  });
  ytReady.catch(() => { ytReady = null });
  return ytReady;
}

function setDetected(durSec, chapters) {
  $("dur").value = fmt(durSec);
  if (chapters) $("chap").value = chapters;
  scheduleSave(0);
}

async function detect() {
  const id = videoId($("url").value), st = $("durStatus");
  if (!id) { detectRun++; st.textContent = "Paste a YouTube link first."; st.hidden = false; lastDetected = ""; return }
  if (id === lastDetected) return;
  lastDetected = id;
  st.hidden = false;
  const run = ++detectRun, live = () => run === detectRun; // ignore results for an older URL or plan
  st.textContent = "Reading the length from YouTube...";

  if (cfg.youtube_api) {
    try {
      const m = await api("GET", `/youtube/videos/${id}`);
      if (!live()) return;
      setDetected(m.duration_sec, m.chapters);
      st.textContent = `Read from YouTube: length ${m.duration}` + (m.chapter_count ? `, ${m.chapter_count} chapters` : ", no chapters in description");
      return;
    } catch (e) {
      if (!live()) return;
      console.log("[Planner] API error", e.message);
      if (e.status === 404 && e.message !== "not_configured") { st.textContent = `YouTube says: ${e.message} Enter the length manually.`; return }
      st.textContent = "API lookup failed. Trying the player instead...";
    }
  }

  try {
    await loadYT();
    if (!live()) return;
    if (player) { try { player.destroy() } catch (e) { } player = null }
    $("probeWrap").innerHTML = '<div id="ytprobe"></div>';
    let finished = false, p = null, iv = null;
    const stop = () => { finished = true; clearInterval(iv); clearTimeout(failTimer); try { p.stopVideo() } catch (e) { } };
    const finish = d => {
      if (finished) return; stop(); if (!live()) return;
      setDetected(d, null);
      st.textContent = `Length read from YouTube: ${fmt(d)}`; console.log("[Planner] duration", d);
    };
    const tryRead = () => { if (finished) return true; const d = p && p.getDuration && p.getDuration(); if (d > 0) { finish(d); return true } return false };
    const failTimer = setTimeout(() => {
      if (finished) return; stop(); if (!live()) return; console.log("[Planner] timed out");
      st.textContent = "YouTube didn't return a length in time. Check the browser console for [Planner] messages, or enter it manually.";
    }, 15000);
    p = player = new YT.Player("ytprobe", {
      videoId: id, width: 200, height: 200,
      playerVars: { autoplay: 0, controls: 0, mute: 1, playsinline: 1, origin: location.origin },
      events: {
        onReady: e => {
          console.log("[Planner] player ready");
          if (tryRead()) return;
          try { e.target.mute(); e.target.playVideo() } catch (err) { } // length can be 0 until playback starts
          let n = 0; iv = setInterval(() => { if (tryRead() || ++n > 40) clearInterval(iv) }, 300);
        },
        onStateChange: () => { tryRead() },
        onError: e => {
          if (finished) return; stop(); console.log("[Planner] player error", e.data); if (!live()) return;
          const msg = { 2: "invalid video ID", 5: "HTML5 player error", 100: "video not found or private", 101: "the video is private, removed, or can't be embedded", 150: "the video is private, removed, or can't be embedded", 153: "missing referrer" }[e.data] || ("error code " + e.data);
          st.textContent = `YouTube refused: ${msg}. Enter the length manually.`;
        },
      },
    });
  } catch (err) {
    if (!live()) return;
    console.log("[Planner] iframe_api failed:", err.message);
    st.textContent = err.message === "blocked"
      ? "Couldn't load the YouTube player script. An ad blocker or privacy extension may be blocking youtube.com. Enter the length manually."
      : "Automatic length detection isn't available right now. Enter the length shown on YouTube.";
  }
}
$("detectBtn").addEventListener("click", () => { lastDetected = ""; detect() });

/* ---------- boot ---------- */
(async function boot() {
  setAuthMode("login");
  try { cfg = await api("GET", "/config") } catch (e) { }
  try { me = await api("GET", "/auth/me") } catch (e) { me = null }
  if (!me) { showAuth(); $("authErr").hidden = true; return }
  try { await enterApp() } catch (e) { showAuth(e.message) }
})();
