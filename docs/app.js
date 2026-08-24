const PLATFORM_LABEL = { reddit: "Reddit", hn: "Hacker News", so: "Stack Exchange", devto: "DEV.to", medium: "Medium", lb: "Lobsters", bsky: "Bluesky", lm: "Lemmy", asr: "App Store", gpr: "Google Play", fb: "Facebook", gh: "GitHub" };

// Claude palette
const C = {
  ink: "#141413", body: "#3d3d3a", muted: "#6c6a64",
  hairline: "#e6dfd8", coral: "#cc785c", teal: "#5db8a6",
  amber: "#e8a55a", mutedSoft: "#8e8b82",
};

Chart.defaults.font.family = '"Inter", system-ui, -apple-system, sans-serif';
Chart.defaults.color = C.muted;

let charts = {};
let DATA = { posts: null, trending: null };
let RENDERED = {};

async function fetchPosts() {
  const platform = document.getElementById("f-platform").value;
  const days = parseInt(document.getElementById("f-days").value, 10);
  const since = days > 0 ? (Date.now() / 1000) - days * 86400 : null;

  // PostgREST gioi han ~1000 dong/lan -> tai phan trang cho du
  const PAGE = 1000;
  const MAX = 9000;
  let all = [];
  for (let offset = 0; offset < MAX; offset += PAGE) {
    let url = `${SUPABASE_URL}/rest/v1/posts?select=id,platform,subreddit,title,url,pain_score,num_comments,score,collected_at,created_utc,selftext,comments&order=collected_at.desc&limit=${PAGE}&offset=${offset}`;
    if (platform) url += `&platform=eq.${platform}`;
    if (since) url += `&collected_at=gte.${since}`;
    const resp = await fetch(url, { headers: { apikey: SUPABASE_ANON_KEY } });
    if (!resp.ok) throw new Error(`Supabase ${resp.status}`);
    const rows = await resp.json();
    all = all.concat(rows);
    if (rows.length < PAGE) break;
  }
  return all;
}

async function fetchTrending() {
  const since = (Date.now() / 1000) - 7 * 86400;
  const url = `${SUPABASE_URL}/rest/v1/repo_stars?select=full_name,stars,captured_at&captured_at=gte.${since}&order=captured_at.asc&limit=3000`;
  const resp = await fetch(url, { headers: { apikey: SUPABASE_ANON_KEY } });
  if (!resp.ok) return [];
  const rows = await resp.json();
  const byRepo = {};
  rows.forEach(r => (byRepo[r.full_name] = byRepo[r.full_name] || []).push(r));
  let meta = {};
  try {
    const mResp = await fetch(`${SUPABASE_URL}/rest/v1/repo_meta?select=*`, { headers: { apikey: SUPABASE_ANON_KEY } });
    if (mResp.ok) (await mResp.json()).forEach(m => meta[m.full_name] = m);
  } catch (_) {}
  return Object.entries(byRepo).map(([name, snaps]) => {
    const m = meta[name] || {};
    return {
      full_name: name,
      stars: m.stars || snaps[snaps.length - 1].stars,
      perDay: m.stars_per_day || 0,
      gain: snaps.length > 1 ? snaps[snaps.length - 1].stars - snaps[0].stars : 0,
      snapshots: snaps.length,
      description: m.description || "",
      language: m.language || "",
      url: m.url || `https://github.com/${name}`,
    };
  }).sort((a, b) => b.stars - a.stars).slice(0, 30);
}

function kpi(label, value, cls) {
  return `<div class="kpi"><div class="v ${cls || ""}">${value}</div><div class="l">${label}</div></div>`;
}
function dayKey(ts) { return new Date(ts * 1000).toISOString().slice(0, 10); }
function runKey(ts) {
  const d = new Date(ts * 1000);
  return d.toISOString().slice(5, 16).replace("T", " ") + "h";
}
function esc(s) { return (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

/* ── Renderers theo tab ─────────────────── */
function renderOverview(posts) {
  const total = posts.length;
  const avgPain = total ? (posts.reduce((s, p) => s + p.pain_score, 0) / total).toFixed(2) : 0;
  const hot = posts.filter(p => p.pain_score >= 5).length;
  const today = dayKey(Date.now() / 1000);
  document.getElementById("kpis").innerHTML =
    kpi("Tổng posts", total.toLocaleString("vi-VN")) +
    kpi("Mới hôm nay", posts.filter(p => dayKey(p.collected_at) === today).length, "coral") +
    kpi("Pain score TB", avgPain) +
    kpi("Posts pain ≥ 5", hot);

  const byDay = {};
  posts.forEach(p => { byDay[dayKey(p.collected_at)] = (byDay[dayKey(p.collected_at)] || 0) + 1; });
  const days = Object.keys(byDay).sort().slice(-60);
  drawChart("chartDaily", "line", {
    labels: days,
    datasets: [{ label: "Posts/ngày", data: days.map(d => byDay[d]), borderColor: C.coral, backgroundColor: "rgba(204,120,92,0.12)", fill: true, tension: .3, pointRadius: 2 }]
  });

  const bySrc = {};
  posts.forEach(p => { bySrc[p.platform] = (bySrc[p.platform] || 0) + 1; });
  drawChart("chartSource", "doughnut", {
    labels: Object.keys(bySrc).map(k => PLATFORM_LABEL[k] || k),
    datasets: [{ data: Object.values(bySrc), backgroundColor: [C.coral, C.amber, C.teal, C.mutedSoft, C.ink, "#b8a06a", "#d98f6c", "#7fa8b8", "#9aa87c", "#c58fb0", "#88a2c2", "#5e5e5e"], borderColor: "#faf9f5", borderWidth: 2 }]
  });

  const painBySrc = {};
  posts.forEach(p => (painBySrc[p.platform] = painBySrc[p.platform] || []).push(p.pain_score));
  const srcKeys = Object.keys(painBySrc);
  drawChart("chartPain", "bar", {
    labels: srcKeys.map(k => PLATFORM_LABEL[k] || k),
    datasets: [{ label: "Pain TB", data: srcKeys.map(k => +(painBySrc[k].reduce((a, b) => a + b, 0) / painBySrc[k].length).toFixed(2)), backgroundColor: C.ink, borderRadius: 6 }]
  }, { y: { beginAtZero: true } });

  const byRun = runBuckets(posts);
  const runKeys = Object.keys(byRun).sort().slice(-24);
  drawChart("chartRunsMini", "bar", {
    labels: runKeys,
    datasets: [{ label: "Posts mỗi lần chạy", data: runKeys.map(k => byRun[k]), backgroundColor: C.teal, borderRadius: 6 }]
  }, { y: { beginAtZero: true }, x: { ticks: { maxRotation: 60 } } });
}

/* ── Phân trang chuyên nghiệp: 1 … 4 [5] 6 … 12 ── */
const PAGER_STATE = { pain: 1, trend: 1, runs: 1 };
const PAGE_SIZE = { pain: 25, trend: 15, runs: 10 };

function pagerRange(cur, pages) {
  const delta = 1;
  const range = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || (i >= cur - delta && i <= cur + delta)) {
      range.push(i);
    } else if (range[range.length - 1] !== "…") {
      range.push("…");
    }
  }
  return range;
}

function renderPager(elId, key, totalItems, onPage) {
  const el = document.getElementById(elId);
  const pages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE[key]));
  if (PAGER_STATE[key] > pages) PAGER_STATE[key] = pages;
  const cur = PAGER_STATE[key];
  if (pages <= 1) { el.innerHTML = ""; return; }

  let btns = "";
  btns += `<button class="pg nav" data-p="1" ${cur === 1 ? "disabled" : ""} title="Trang đầu">«</button>`;
  btns += `<button class="pg nav" data-p="${Math.max(1, cur - 1)}" ${cur === 1 ? "disabled" : ""} title="Trước">‹</button>`;
  for (const item of pagerRange(cur, pages)) {
    btns += item === "…"
      ? `<span class="pg dots">…</span>`
      : `<button class="pg ${item === cur ? "active" : ""}" data-p="${item}">${item}</button>`;
  }
  btns += `<button class="pg nav" data-p="${Math.min(pages, cur + 1)}" ${cur === pages ? "disabled" : ""} title="Sau">›</button>`;
  btns += `<button class="pg nav" data-p="${pages}" ${cur === pages ? "disabled" : ""} title="Trang cuối">»</button>`;

  el.innerHTML = btns + `<span class="pg-info">${totalItems.toLocaleString("vi-VN")} mục · ${cur}/${pages}</span>`;
  el.querySelectorAll("button.pg").forEach(b =>
    b.addEventListener("click", () => {
      PAGER_STATE[key] = parseInt(b.dataset.p, 10);
      onPage();
    }));
}

function slicePage(arr, key) {
  const start = (PAGER_STATE[key] - 1) * PAGE_SIZE[key];
  return arr.slice(start, start + PAGE_SIZE[key]);
}

function renderPain(posts) {
  const top = [...posts].sort((a, b) => b.pain_score - a.pain_score);
  window.__painRows = top;
  const rows = slicePage(top, "pain");
  document.querySelector("#topTable tbody").innerHTML = rows.map((p, i) => `
    <tr>
      <td class="pain">${p.pain_score}</td>
      <td><span class="tag ${p.platform}">${PLATFORM_LABEL[p.platform] || p.platform}</span></td>
      <td class="mut">${esc(p.subreddit.slice(0, 20))}</td>
      <td><a href="${p.url}" target="_blank" rel="noopener">${esc(p.title.slice(0, 90))}</a></td>
      <td class="mut">${esc(((p.selftext || "").replace(/\s+/g, " ").trim()).slice(0, 110))}${p.selftext && p.selftext.length > 110 ? "…" : ""}</td>
      <td>${p.score}</td>
      <td>${p.num_comments}</td>
      <td><button class="copy-btn" data-idx="${(PAGER_STATE.pain - 1) * PAGE_SIZE.pain + i}" title="Copy chi tiết pain point">Copy</button></td>
    </tr>`).join("") || '<tr><td colspan="8" class="mut">Chưa có dữ liệu</td></tr>';
  renderPager("pagerTop", "pain", top.length, () => renderPain(posts));
}

async function copyPain(idx, btn) {
  const p = (window.__painRows || [])[idx];
  if (!p) return;
  const content = ((p.selftext || "").replace(/\r/g, "")).trim() || "(bài không có nội dung)";
  const comments = ((p.comments || "").split("\n---\n").filter(Boolean).map(c => "- " + c.replace(/\s+/g, " ").trim())).join("\n");
  const text = [
    `Title: ${p.title}`,
    `URL: ${p.url}`,
    `Nguồn: ${PLATFORM_LABEL[p.platform] || p.platform} | Cộng đồng: ${p.subreddit}`,
    `Pain score: ${p.pain_score} | Upvote: ${p.score} | Comments: ${p.num_comments}`,
    `Ngày đăng: ${new Date((p.created_utc || 0) * 1000).toISOString().slice(0, 10)}`,
    ``,
    `Nội dung:`,
    content,
  ];
  if (comments) {
    text.push(``, `Comments nổi bật:`, comments);
  }
  try {
    await navigator.clipboard.writeText(text.join("\n"));
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text.join("\n");
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  btn.textContent = "✓ Đã copy";
  btn.classList.add("copied");
  setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1600);
}

function renderTrending(trending) {
  window.__trendRows = trending;
  const rows = slicePage(trending, "trend");
  document.querySelector("#trendTable tbody").innerHTML = rows.length ? rows.map((r, i) => `
    <tr>
      <td class="stars">⭐ ${r.stars}</td>
      <td>${r.perDay ? `<span class="perday">+${r.perDay}/ngày</span>` : '<span class="mut">—</span>'}</td>
      <td>${r.gain !== 0 ? `<span class="gain">+${r.gain}</span>` : `<span class="mut">${r.snapshots} lần đo</span>`}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">${esc(r.full_name)}</a></td>
      <td>${r.language ? `<span class="lang-chip">${esc(r.language)}</span>` : '<span class="mut">—</span>'}</td>
      <td class="mut">${esc((r.description || "").slice(0, 90))}</td>
      <td><button class="copy-btn" data-idx="${(PAGER_STATE.trend - 1) * PAGE_SIZE.trend + i}" title="Copy link repo">Link</button></td>
    </tr>`).join("") :
    '<tr><td colspan="7" class="mut">Chưa có dữ liệu trending — bot sẽ ghi sau mỗi lần chạy.</td></tr>';
  renderPager("pagerTrend", "trend", trending.length, () => renderTrending(trending));
}

async function copyText(text, btn, okLabel = "✓ Đã copy") {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  const old = btn.textContent;
  btn.textContent = okLabel;
  btn.classList.add("copied");
  setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1600);
}

function renderRuns(posts) {
  const byRun = runBuckets(posts);
  const runKeys = Object.keys(byRun).sort().slice(-48);
  drawChart("chartRunsFull", "bar", {
    labels: runKeys,
    datasets: [{ label: "Posts mỗi lần chạy", data: runKeys.map(k => byRun[k]), backgroundColor: C.teal, borderRadius: 6 }]
  }, { y: { beginAtZero: true }, x: { ticks: { maxRotation: 60 } } });

  const list = runKeys.reverse().map(k => {
    const items = posts.filter(p => runKey(Math.floor(p.collected_at / 3600) * 3600) === k);
    const platforms = [...new Set(items.map(p => p.platform))].map(x => PLATFORM_LABEL[x] || x).join(", ");
    const avg = items.length ? (items.reduce((s, p) => s + p.pain_score, 0) / items.length).toFixed(2) : 0;
    return `<tr><td>${k}</td><td>${platforms}</td><td>${items.length}</td><td class="pain">${avg}</td></tr>`;
  });
  document.querySelector("#runsTable tbody").innerHTML =
    slicePage(list, "runs").join("") || '<tr><td colspan="4" class="mut">Chưa có dữ liệu</td></tr>';
  renderPager("pagerRuns", "runs", list.length, () => renderRuns(posts));
}

function runBuckets(posts) {
  const byRun = {};
  posts.forEach(p => {
    const k = runKey(Math.floor(p.collected_at / 3600) * 3600);
    byRun[k] = (byRun[k] || 0) + 1;
  });
  return byRun;
}

/* ── Tab logic ──────────────────────────── */
const RENDERERS = {
  overview: () => renderOverview(DATA.posts),
  pain: () => renderPain(DATA.posts),
  trending: () => renderTrending(DATA.trending),
  runs: () => renderRuns(DATA.posts),
};

function activateTab(name) {
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-pane").forEach(p =>
    p.classList.toggle("active", p.dataset.pane === name));
  if (DATA.posts && !RENDERED[name]) {
    RENDERERS[name]();
    RENDERED[name] = true;
  }
}

document.getElementById("tabs").addEventListener("click", e => {
  const btn = e.target.closest(".tab");
  if (btn) activateTab(btn.dataset.tab);
});

document.querySelector("#topTable").addEventListener("click", e => {
  const btn = e.target.closest(".copy-btn");
  if (btn) copyPain(parseInt(btn.dataset.idx, 10), btn);
});

document.querySelector("#trendTable").addEventListener("click", e => {
  const btn = e.target.closest(".copy-btn");
  if (!btn) return;
  const r = (window.__trendRows || [])[parseInt(btn.dataset.idx, 10)];
  if (r) copyText(r.url, btn, "✓ Đã copy link");
});

/* ── Charts ─────────────────────────────── */
function drawChart(id, type, data, options = {}) {
  if (charts[id]) charts[id].destroy();
  const grid = { color: C.hairline };
  const baseScales = {
    x: Object.assign({ grid: Object.assign({}, grid) }, options.x || {}),
    y: Object.assign({ beginAtZero: true, grid: Object.assign({}, grid) }, options.y || {}),
  };
  charts[id] = new Chart(document.getElementById(id), {
    type,
    data,
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: type === "doughnut", position: "right" } },
      scales: type === "doughnut" ? {} : baseScales,
    },
  });
}

/* ── Load ───────────────────────────────── */
async function load() {
  document.getElementById("kpis").innerHTML = '<div id="status">Đang tải dữ liệu…</div>';
  try {
    [DATA.posts, DATA.trending] = await Promise.all([fetchPosts(), fetchTrending()]);
    RENDERED = {};
    const active = document.querySelector(".tab.active").dataset.tab;
    RENDERERS[active]();
    RENDERED[active] = true;
  } catch (e) {
    document.getElementById("kpis").innerHTML =
      `<div id="status">⚠️ Không tải được dữ liệu: ${e.message}<br>Kiểm tra config.js (SUPABASE_URL / ANON_KEY)</div>`;
  }
}

document.getElementById("f-platform").addEventListener("change", load);
document.getElementById("f-days").addEventListener("change", load);
load();
