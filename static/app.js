/* ── Topic palette ── */
const TOPIC_COLORS = {
  "Robot Navigation":      "#818cf8",
  "Autonomous Driving":    "#f59e0b",
  "Reinforcement Learning":"#10b981",
  "Video Generation":      "#ec4899",
  "3D Scene Modeling":     "#06b6d4",
  "Physics & Dynamics":    "#f97316",
  "Planning & Control":    "#84cc16",
  "Language & Vision":     "#a78bfa",
  "Situational Awareness": "#fb923c",
  "Game Playing":          "#4ade80",
  "Robotics & Manipulation":"#38bdf8",
  "Latent Space Models":   "#e879f9",
  "Other":                 "#64748b",
};

/* ── State ── */
let allPapers   = [];
let activeTopics = new Set();
let searchQuery  = "";

/* ── DOM refs ── */
const grid        = document.getElementById("papers-grid");
const loading     = document.getElementById("loading");
const empty       = document.getElementById("empty");
const searchEl    = document.getElementById("search");
const yearFrom    = document.getElementById("year-from");
const yearTo      = document.getElementById("year-to");
const sortSel     = document.getElementById("sort-select");
const codeOnly    = document.getElementById("code-only");
const topicFilters= document.getElementById("topic-filters");
const sidebarStats= document.getElementById("sidebar-stats");
const statTotal   = document.getElementById("stat-total");
const statShown   = document.getElementById("stat-shown");
const statCode    = document.getElementById("stat-code");
const statUpdated = document.getElementById("stat-updated");

/* ── Particle canvas ── */
(function initParticles() {
  const canvas = document.getElementById("particles");
  const ctx    = canvas.getContext("2d");
  let W, H, nodes;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    nodes = Array.from({ length: 80 }, () => ({
      x:  Math.random() * W,
      y:  Math.random() * H,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r:  Math.random() * 2 + 1,
    }));
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    // edges
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 140) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.strokeStyle = `rgba(91,33,182,${0.22 * (1 - d / 140)})`;
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }
    }
    // nodes
    nodes.forEach(n => {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(109,40,217,0.45)";
      ctx.fill();
      n.x += n.vx; n.y += n.vy;
      if (n.x < 0 || n.x > W) n.vx *= -1;
      if (n.y < 0 || n.y > H) n.vy *= -1;
    });
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  draw();
})();

/* ── Build topic sidebar ── */
function buildTopicFilters(papers) {
  const counts = {};
  papers.forEach(p => p.topics.forEach(t => { counts[t] = (counts[t] || 0) + 1; }));

  topicFilters.innerHTML = "";
  const sorted = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  sorted.forEach(topic => {
    const color = TOPIC_COLORS[topic] || "#94a3b8";
    const btn   = document.createElement("button");
    btn.className = "topic-btn";
    btn.dataset.topic = topic;
    btn.innerHTML = `<span class="topic-dot" style="background:${color}"></span>${topic} <span style="margin-left:auto;opacity:.5;font-size:10px">${counts[topic]}</span>`;
    btn.addEventListener("click", () => {
      if (activeTopics.has(topic)) activeTopics.delete(topic);
      else activeTopics.add(topic);
      btn.classList.toggle("active");
      render();
    });
    topicFilters.appendChild(btn);
  });
}

/* ── Filtering + sorting ── */
function filterAndSort() {
  const q   = searchQuery.toLowerCase();
  const yfr = parseInt(yearFrom.value) || 0;
  const yto = parseInt(yearTo.value)   || 9999;
  const co  = codeOnly.checked;

  let out = allPapers.filter(p => {
    if (p.year < yfr || p.year > yto) return false;
    if (co && !p.code_url)            return false;
    if (activeTopics.size && !p.topics.some(t => activeTopics.has(t))) return false;
    if (q) {
      const hay = (p.title + " " + p.abstract + " " + p.authors + " " + p.venue).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const s = sortSel.value;
  if (s === "citations")  out.sort((a, b) => (b.citations || 0) - (a.citations || 0));
  else if (s === "year-asc") out.sort((a, b) => a.year - b.year);
  else                    out.sort((a, b) => b.year - a.year);

  return out;
}

/* ── Render one card ── */
function renderCard(p, idx) {
  const card = document.createElement("div");
  card.className = "card";
  card.style.animationDelay = `${Math.min(idx * 20, 400)}ms`;

  const badges = p.topics.map(t => {
    const c = TOPIC_COLORS[t] || "#94a3b8";
    return `<span class="badge" style="color:${c};border-color:${c}">${t}</span>`;
  }).join("");

  const GH_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0"><path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2 0-.4-.5-1.6.2-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17 5.1 18 5.4 18 5.4c.6 1.6.2 2.8.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.5.4.9 1.2.9 2.3v3.3c0 .3.1.7.8.6A12 12 0 0 0 12 .3"/></svg>`;

  const actions = [
    p.paper_url ? `<a href="${p.paper_url}" target="_blank" rel="noopener" class="btn btn-paper">&#128196; Paper</a>` : "",
    p.code_url  ? `<a href="${p.code_url}"  target="_blank" rel="noopener" class="btn btn-code">${GH_ICON} Code</a>` : "",
  ].join("");

  const authors = (p.authors || "").length > 80 ? p.authors.slice(0, 80) + "…" : p.authors;
  const cites   = p.citations ? `&#9733; ${p.citations.toLocaleString()}` : "";
  const venueBadge = p.venue
    ? `<span class="venue-badge">&#127891; ${esc(p.venue)}</span>`
    : "";
  const metaParts = [
    `<span>&#128197; ${p.year}</span>`,
    cites  ? `<span>${cites} citations</span>` : "",
    authors? `<span>&#128100; ${authors}</span>` : "",
  ].filter(Boolean).join("");

  const absId = `abs-${idx}`;
  card.innerHTML = `
    <div class="card-title">${esc(p.title)}</div>
    <div class="card-topics">${badges}${venueBadge}</div>
    <div class="card-meta">${metaParts}</div>
    ${actions ? `<div class="card-actions">${actions}</div>` : ""}
    ${p.abstract ? `
      <div class="abstract-text" id="${absId}">${esc(p.abstract)}</div>
      <span class="abstract-toggle" onclick="toggleAbs('${absId}',this)" style="margin-top:6px">&#9654; Show more</span>
    ` : ""}
  `;
  return card;
}

function esc(s) {
  return String(s)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;");
}

window.toggleAbs = function(id, el) {
  const box = document.getElementById(id);
  box.classList.toggle("open");
  el.textContent = box.classList.contains("open") ? "▾ Show less" : "▶ Show more";
};

/* ── Main render ── */
function render() {
  const filtered = filterAndSort();

  grid.innerHTML = "";
  empty.classList.add("hidden");

  if (filtered.length === 0) {
    empty.classList.remove("hidden");
    return;
  }

  const frag = document.createDocumentFragment();
  filtered.slice(0, 200).forEach((p, i) => frag.appendChild(renderCard(p, i)));
  grid.appendChild(frag);

  const withCode = allPapers.filter(p => p.code_url).length;
  statShown.textContent   = `${filtered.length} shown`;
  sidebarStats.innerHTML  = `${allPapers.length} total · ${filtered.length} shown<br>${withCode} with code`;
}

/* ── Update global stats chips ── */
function updateStats(lastUpdated, visits) {
  const withCode = allPapers.filter(p => p.code_url).length;
  statTotal.textContent   = `${allPapers.length} papers`;
  statCode.textContent    = `${withCode} with code`;
  statUpdated.textContent = lastUpdated ? `Updated ${lastUpdated.slice(0,10)}` : "";
  if (visits) {
    const chip = document.getElementById("stat-visits");
    if (chip) chip.textContent = `${visits.toLocaleString()} visits`;
  }
}

/* ── Event listeners ── */
searchEl.addEventListener("input", e => { searchQuery = e.target.value; render(); });
yearFrom.addEventListener("change", render);
yearTo.addEventListener("change", render);
sortSel.addEventListener("change", render);
codeOnly.addEventListener("change", render);

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault(); searchEl.focus();
  }
});

/* ── Fetch & boot ── */
async function boot() {
  try {
    // Record visit and fetch papers in parallel
    const [papersRes, visitRes] = await Promise.all([
      fetch("/api/papers"),
      fetch("/api/visit"),
    ]);
    const data  = await papersRes.json();
    const visits = (await visitRes.json()).visits;

    allPapers = data.papers || [];

    loading.classList.add("hidden");
    buildTopicFilters(allPapers);
    updateStats(data.last_updated, visits);
    statTotal.textContent = `${allPapers.length} papers`;
    render();
  } catch (err) {
    loading.innerHTML = `<p style="color:var(--accent)">Failed to load papers: ${err.message}</p>`;
  }
}

boot();
