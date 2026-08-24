const PLATFORM_LABEL = { reddit: "Reddit", hn: "Hacker News", so: "StackOverflow", gh: "GitHub" };

// Claude palette
const C = {
  ink: "#141413",
  body: "#3d3d3a",
  muted: "#6c6a64",
  mutedSoft: "#8e8b82",
  hairline: "#e6dfd8",
  coral: "#cc785c",
  coralDark: "#a9583e",
  teal: "#5db8a6",
  amber: "#e8a55a",
};

Chart.defaults.font.family = '"Inter", system-ui, -apple-system, sans-serif';
Chart.defaults.color = C.muted;

let charts = {};

async function fetchPosts() {
  const platform = document.getElementById("f-platform").value;
  const days = parseInt(document.getElementById("f-days").value, 10);
  let url = `${SUPABASE_URL}/rest/v1/posts?select=id,platform,subreddit,title,url,pain_score,num_comments,score,collected_at,selftext&order=collected_at.desc&limit=8000`;
  if (platform) url += `&platform=eq.${platform}`;
  if (days > 0) {
    const since = (Date.now() / 1000) - days * 86400;
    url += `&collected_at=gte.${since}`;
  }
  const resp = await fetch(url, { headers: { apikey: SUPABASE_ANON_KEY } });
  if (!resp.ok) throw new Error(`Supabase ${resp.status}`);
  return resp.json();
}

async function fetchTrending() {
  // Lấy toàn bộ snapshot, gộp lấy mới nhất + tăng trưởng 7 ngày theo repo
  const since = (Date.now() / 1000) - 7 * 86400;
  const url = `${SUPABASE_URL}/rest/v1/repo_stars?select=full_name,stars,captured_at&captured_at=gte.${since}&order=captured_at.asc&limit=3000`;
  const resp = await fetch(url, { headers: { apikey: SUPABASE_ANON_KEY } });
  if (!resp.ok) return [];
  const rows = await resp.json();
  const byRepo = {};
  rows.forEach(r => {
    (byRepo[r.full_name] = byRepo[r.full_name] || []).push(r);
  });
  const meta = {};
  try {
    const mResp = await fetch(`${SUPABASE_URL}/rest/v1/repo_meta?select=*`, { headers: { apikey: SUPABASE_ANON_KEY } });
    if (mResp.ok) (await mResp.json()).forEach(m => meta[m.full_name] = m);
  } catch (_) {}
  return Object.entries(byRepo).map(([name, snaps]) => ({
    full_name: name,
    stars: snaps[snaps.length - 1].stars,
    gain: snaps.length > 1 ? snaps[snaps.length - 1].stars - snaps[0].stars : 0,
    snapshots: snaps.length,
    description: (meta[name] || {}).description || "",
    language: (meta[name] || {}).language || "",
    url: `https://github.com/${name}`,
  })).sort((a, b) => b.stars - a.stars).slice(0, 20);
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

function render(posts, trending) {
  const total = posts.length;
  const avgPain = total ? (posts.reduce((s, p) => s + p.pain_score, 0) / total).toFixed(2) : 0;
  const hot = posts.filter(p => p.pain_score >= 5).length;
  const today = dayKey(Date.now() / 1000);
  const todayCount = posts.filter(p => dayKey(p.collected_at) === today).length;

  document.getElementById("kpis").innerHTML =
    kpi("Tổng posts", total.toLocaleString("vi-VN")) +
    kpi("Mới hôm nay", todayCount, "coral") +
    kpi("Pain score TB", avgPain) +
    kpi("Posts pain ≥ 5", hot);

  // theo ngày
  const byDay = {};
  posts.forEach(p => { byDay[dayKey(p.collected_at)] = (byDay[dayKey(p.collected_at)] || 0) + 1; });
  const days = Object.keys(byDay).sort().slice(-60);
  drawChart("chartDaily", "line", {
    labels: days,
    datasets: [{ label: "Posts/ngày", data: days.map(d => byDay[d]), borderColor: C.coral, backgroundColor: "rgba(204,120,92,0.12)", fill: true, tension: .3, pointRadius: 2 }]
  });

  // theo nguồn
  const bySrc = {};
  posts.forEach(p => { bySrc[p.platform] = (bySrc[p.platform] || 0) + 1; });
  drawChart("chartSource", "doughnut", {
    labels: Object.keys(bySrc).map(k => PLATFORM_LABEL[k] || k),
    datasets: [{ data: Object.values(bySrc), backgroundColor: [C.coral, C.amber, C.teal, C.mutedSoft], borderColor: "#faf9f5", borderWidth: 2 }]
  });

  // pain TB theo nguồn
  const painBySrc = {};
  posts.forEach(p => {
    (painBySrc[p.platform] = painBySrc[p.platform] || []).push(p.pain_score);
  });
  const srcKeys = Object.keys(painBySrc);
  drawChart("chartPain", "bar", {
    labels: srcKeys.map(k => PLATFORM_LABEL[k] || k),
    datasets: [{ label: "Pain TB", data: srcKeys.map(k => +(painBySrc[k].reduce((a, b) => a + b, 0) / painBySrc[k].length).toFixed(2)), backgroundColor: C.ink, borderRadius: 6 }]
  }, { y: { beginAtZero: true } });

  // các lần crawl
  const byRun = {};
  posts.forEach(p => {
    const k = runKey(Math.floor(p.collected_at / 3600) * 3600);
    byRun[k] = (byRun[k] || 0) + 1;
  });
  const runKeys = Object.keys(byRun).sort().slice(-24);
  drawChart("chartRuns", "bar", {
    labels: runKeys,
    datasets: [{ label: "Posts mỗi lần chạy", data: runKeys.map(k => byRun[k]), backgroundColor: C.teal, borderRadius: 6 }]
  }, { y: { beginAtZero: true }, x: { ticks: { maxRotation: 60 } } });

  // top pain
  const top = [...posts].sort((a, b) => b.pain_score - a.pain_score).slice(0, 25);
  document.querySelector("#topTable tbody").innerHTML = top.map(p => `
    <tr>
      <td class="pain">${p.pain_score}</td>
      <td><span class="tag ${p.platform}">${PLATFORM_LABEL[p.platform] || p.platform}</span></td>
      <td class="mut">${esc(p.subreddit.slice(0, 22))}</td>
      <td><a href="${p.url}" target="_blank" rel="noopener">${esc(p.title.slice(0, 95))}</a></td>
      <td>${p.score}</td>
      <td>${p.num_comments}</td>
    </tr>`).join("");

  // trending
  document.querySelector("#trendTable tbody").innerHTML = trending.length ? trending.map(r => `
    <tr>
      <td class="stars">⭐ ${r.stars}</td>
      <td>${r.gain > 0 ? `<span class="gain">+${r.gain}</span>` : `<span class="mut">${r.snapshots} lần đo</span>`}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">${esc(r.full_name)}</a></td>
      <td>${r.language ? `<span class="lang-chip">${esc(r.language)}</span>` : '<span class="mut">—</span>'}</td>
      <td class="mut">${esc((r.description || "").slice(0, 90))}</td>
    </tr>`).join("") :
    '<tr><td colspan="5" class="mut">Chưa có dữ liệu trending — bot sẽ ghi sau mỗi lần chạy.</td></tr>';

  // lần crawl gần nhất
  const runRows = runKeys.reverse().map(k => {
    const items = posts.filter(p => runKey(Math.floor(p.collected_at / 3600) * 3600) === k);
    const platforms = [...new Set(items.map(p => p.platform))].map(x => PLATFORM_LABEL[x] || x).join(", ");
    const avg = items.length ? (items.reduce((s, p) => s + p.pain_score, 0) / items.length).toFixed(2) : 0;
    return `<tr><td>${k}</td><td>${platforms}</td><td>${items.length}</td><td class="pain">${avg}</td></tr>`;
  }).join("");
  document.querySelector("#runsTable tbody").innerHTML = runRows || '<tr><td colspan="4" class="mut">Chưa có dữ liệu</td></tr>';
}

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

async function load() {
  document.getElementById("kpis").innerHTML = '<div id="status">Đang tải dữ liệu…</div>';
  try {
    const [posts, trending] = await Promise.all([fetchPosts(), fetchTrending()]);
    render(posts, trending);
  } catch (e) {
    document.getElementById("kpis").innerHTML =
      `<div id="status">⚠️ Không tải được dữ liệu: ${e.message}<br>Kiểm tra config.js (SUPABASE_URL / ANON_KEY)</div>`;
  }
}

document.getElementById("f-platform").addEventListener("change", load);
document.getElementById("f-days").addEventListener("change", load);
load();
