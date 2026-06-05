
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */
window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER = true;
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */


const state = {
  mapPayload: null,
  variable: "overall",
  showInjectors: false,
  showInactive: false,
};

function cls(score, klass) {
  if (score === null || score === undefined || score === "" || !Number.isFinite(Number(score))) return "score-na";
  const v = Number(score);
  if (v >= 80) return "score-good";
  if (v >= 60) return "score-fair";
  return "score-poor";
}

function fmt(v, digits = 1) {
  if (v === null || v === undefined || v === "" || !Number.isFinite(Number(v))) return "N/A";
  return Number(v).toFixed(digits);
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

async function postJson(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

async function loadKpis() {
  const data = await getJson("/api/dashboard/kpi-summary?t=" + Date.now());
  const row = document.getElementById("kpiRow");

  row.innerHTML = (data.cards || []).map(card => `
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(card.label)}</div>
      <div class="kpi-value ${cls(card.score, card.class)}">${fmt(card.score)}</div>
      <div class="kpi-class">${escapeHtml(card.class || "Not Evaluated")}</div>
      <div class="kpi-sub">${escapeHtml(card.subtext || "")}</div>
    </div>
  `).join("");
}

function mapClassColor(c) {
  c = String(c || "").toLowerCase();
  if (c === "good") return "#39ff6b";
  if (c === "fair") return "#ffd84d";
  if (c === "poor") return "#ff5757";
  return "#9fb2d0";
}

function selectedScore(w) {
  const v = state.variable;
  return {
    score: w[`${v}_score`],
    class: w[`${v}_class`] || "Not Evaluated",
  };
}

function buildMapItems() {
  const wells = (state.mapPayload && state.mapPayload.wells) || [];
  const items = [];

  for (const w of wells) {
    if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

    if (w.producer_candidate && w.active_producer) {
      items.push({...w, display_role: "producer", display_active: true});
    }

    if (state.showInactive && w.producer_candidate && !w.active_producer) {
      items.push({...w, display_role: "inactive_producer", display_active: false});
    }

    if (state.showInjectors && w.injector_candidate) {
      items.push({...w, display_role: "injector", display_active: !!w.active_injector});
    }
  }

  const seen = new Set();
  return items.filter(w => {
    const key = `${w.well}_${w.display_role}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderMap() {
  const mount = document.getElementById("mapCanvas");
  const items = buildMapItems();

  if (!items.length) {
    mount.innerHTML = `<div class="empty-state">No wells available for current filters.</div>`;
    return;
  }

  const W = 1200;
  const H = 680;
  const pad = 70;

  const iVals = items.map(w => Number(w.i)).filter(Number.isFinite);
  const jVals = items.map(w => Number(w.j)).filter(Number.isFinite);

  const minI = Math.min(...iVals);
  const maxI = Math.max(...iVals);
  const minJ = Math.min(...jVals);
  const maxJ = Math.max(...jVals);

  const sx = i => maxI === minI ? W / 2 : pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  const sy = j => maxJ === minJ ? H / 2 : pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);

  let grid = "";
  for (let k = 0; k <= 8; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    grid += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(160,190,255,.12)" />`;
    grid += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(160,190,255,.12)" />`;
  }

  const points = items.map(w => {
    const x = sx(w.i);
    const y = sy(w.j);
    let s = selectedScore(w);
    let kls = s.class;

    if (w.display_role === "inactive_producer") kls = "Inactive";
    if (w.display_role === "injector") kls = w.injection_class || "Not Evaluated";

    const color = mapClassColor(kls);
    const label = escapeHtml(w.well);

    if (w.display_role === "injector") {
      return `
        <g onclick="selectWell('${label}')" style="cursor:pointer">
          <polygon points="${x},${y-13} ${x+13},${y} ${x},${y+13} ${x-13},${y}"
            fill="${color}" stroke="#fff" stroke-width="1.5" opacity="${w.display_active ? 1 : .55}" />
          <text x="${x+16}" y="${y-10}" fill="#f8fafc" font-size="13" font-weight="800">${label}</text>
          <title>${label} | Injector | ${kls}</title>
        </g>`;
    }

    return `
      <g onclick="selectWell('${label}')" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="22" fill="${color}" opacity=".16" />
        <circle cx="${x}" cy="${y}" r="10" fill="${color}" stroke="#fff" stroke-width="1.7" opacity="${w.display_active ? 1 : .55}" />
        <text x="${x+16}" y="${y-10}" fill="#f8fafc" font-size="13" font-weight="800">${label}</text>
        <title>${label} | ${kls} | ${state.variable.toUpperCase()} ${fmt(s.score)}</title>
      </g>`;
  }).join("");

  mount.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}">
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <rect x="0" y="0" width="${W}" height="${H}" fill="rgba(3,10,24,.15)" />
      <text x="36" y="40" fill="#f8fafc" font-size="22" font-weight="900">History Match Map</text>
      <text x="36" y="64" fill="#9fb2d0" font-size="13">Color by ${state.variable.toUpperCase()} score. Active producers shown by default.</text>
      <text x="${W-36}" y="40" text-anchor="end" fill="#35d7ff" font-size="13" font-weight="800">404 Reservoir Not Found</text>
      ${grid}
      <g filter="url(#glow)">${points}</g>
    </svg>
    <div class="legend">
      <span><span class="dot" style="background:#39ff6b"></span>Good</span>
      <span><span class="dot" style="background:#ffd84d"></span>Fair</span>
      <span><span class="dot" style="background:#ff5757"></span>Poor</span>
      <span><span class="dot" style="background:#9fb2d0"></span>Inactive / Not evaluated</span>
      <span>● Producer</span>
      <span>◆ Injector</span>
    </div>
  `;
}

async function loadMap() {
  state.mapPayload = await getJson("/api/dashboard/hm-map?t=" + Date.now());
  renderMap();
}

function renderWellInsight(data) {
  const mount = document.getElementById("wellInsight");

  if (!data || !data.found) {
    mount.innerHTML = `<div class="empty-state">${escapeHtml(data?.message || "Well not found.")}</div>`;
    return;
  }

  const cards = data.cards || [];
  const activity = data.activity || {};
  const crit = data.criticalities || [];

  mount.innerHTML = `
    <div class="well-title">${escapeHtml(data.well)}</div>
    <div class="well-sub">
      Active producer: ${activity.active_producer === true ? "Yes" : activity.active_producer === false ? "No" : "N/A"}
      ${activity.exclude_from_hm ? " | Excluded from HM" : ""}
    </div>

    <div class="well-kpi-grid">
      ${cards.map(card => `
        <div class="well-kpi">
          <div class="well-kpi-label">${escapeHtml(card.label)}</div>
          <div class="well-kpi-value ${cls(card.score, card.class)}">${fmt(card.score)}</div>
          <div class="well-kpi-class">${escapeHtml(card.class || "Not Evaluated")}</div>
        </div>
      `).join("")}
    </div>

    <div class="section-title">Criticalities</div>
    <ul class="insight-list">
      ${crit.length ? crit.map(x => `<li>${escapeHtml(x)}</li>`).join("") : "<li>No major criticality detected.</li>"}
    </ul>

    <div class="section-title">Recommended Action</div>
    <p class="insight-text">${escapeHtml(data.recommended_action || "Review profiles, local properties and connectivity before applying model edits.")}</p>

    ${data.interpretation ? `
      <div class="section-title">Interpretation</div>
      <p class="insight-text">${escapeHtml(data.interpretation)}</p>
    ` : ""}
  `;
}

async function selectWell(well) {
  const data = await getJson("/api/dashboard/well-insight?well=" + encodeURIComponent(well) + "&t=" + Date.now());
  renderWellInsight(data);
}

window.selectWell = selectWell;


function heatColorForProperty(v, minV, maxV) {
  v = Number(v);
  if (!Number.isFinite(v)) return "rgba(0,0,0,0)";
  let t = maxV === minV ? 0.5 : Math.max(0, Math.min(1, (v - minV) / (maxV - minV)));

  if (t < 0.33) {
    const u = t / 0.33;
    return `rgb(${30 + Math.round(60*u)},${100 + Math.round(110*u)},255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${90 + Math.round(165*u)},${210 + Math.round(25*u)},${255 - Math.round(210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255,${235 - Math.round(145*u)},${45 - Math.round(20*u)})`;
}

function renderProfilePlot(block) {
  const panel = document.getElementById("visualPanel");
  const data = block.data || {};
  const series = data.series || data.data || data;

  let dates = series.dates || series.date || series.time || series.x || [];
  let sim = series.simulated || series.sim || series.sim_values || series.y_sim || [];
  let obs = series.observed || series.obs || series.hist || series.observed_values || series.y_obs || [];

  // Some backend payloads may wrap variable data one level deeper.
  if ((!dates.length || !sim.length) && data.profile) {
    dates = data.profile.dates || data.profile.time || data.profile.x || [];
    sim = data.profile.simulated || data.profile.sim || data.profile.y_sim || [];
    obs = data.profile.observed || data.profile.obs || data.profile.y_obs || [];
  }

  const title = block.title || `${data.well || ""} profile`;

  if (!dates.length || (!sim.length && !obs.length)) {
    panel.innerHTML = `
      <div class="empty-state">
        Profile data was returned, but I could not detect date/simulated/observed arrays.
        <pre>${escapeHtml(JSON.stringify(data, null, 2).slice(0, 4000))}</pre>
      </div>
    `;
    return;
  }

  const W = 900;
  const H = 420;
  const padL = 58;
  const padR = 22;
  const padT = 42;
  const padB = 54;

  const n = Math.max(dates.length, sim.length, obs.length);
  const xs = Array.from({length: n}, (_, i) => i);

  const vals = []
    .concat((sim || []).map(Number).filter(Number.isFinite))
    .concat((obs || []).map(Number).filter(Number.isFinite));

  const ymin = 0;
  const ymax = Math.max(1, ...vals) * 1.08;

  function sx(i) {
    if (n <= 1) return padL;
    return padL + i * (W - padL - padR) / (n - 1);
  }

  function sy(v) {
    v = Number(v);
    if (!Number.isFinite(v)) v = 0;
    return H - padB - (v - ymin) * (H - padT - padB) / (ymax - ymin);
  }

  function pathFrom(arr) {
    let d = "";
    for (let i = 0; i < n; i++) {
      const v = Number(arr[i]);
      if (!Number.isFinite(v)) continue;
      d += `${d ? "L" : "M"} ${sx(i)} ${sy(v)} `;
    }
    return d;
  }

  const grid = Array.from({length: 5}, (_, k) => {
    const y = padT + k * (H - padT - padB) / 4;
    const val = ymax - k * ymax / 4;
    return `
      <line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(160,190,255,.13)" />
      <text x="${padL-10}" y="${y+4}" fill="#9fb2d0" font-size="11" text-anchor="end">${fmt(val, 0)}</text>
    `;
  }).join("");

  const obsPath = pathFrom(obs || []);
  const simPath = pathFrom(sim || []);

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:420px;border-radius:16px;background:#061022;border:1px solid rgba(160,190,255,.14)">
      <text x="${padL}" y="25" fill="#f8fafc" font-size="16" font-weight="900">${escapeHtml(title)}</text>
      ${grid}
      <line x1="${padL}" y1="${H-padB}" x2="${W-padR}" y2="${H-padB}" stroke="rgba(160,190,255,.35)" />
      <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H-padB}" stroke="rgba(160,190,255,.35)" />

      ${obsPath ? `<path d="${obsPath}" fill="none" stroke="#39ff6b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />` : ""}
      ${simPath ? `<path d="${simPath}" fill="none" stroke="#35d7ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="8 5" />` : ""}

      <text x="${padL}" y="${H-18}" fill="#9fb2d0" font-size="12">Time index</text>
      <text x="16" y="${padT}" fill="#9fb2d0" font-size="12" transform="rotate(-90 16 ${padT})">Rate / value</text>

      <circle cx="${W-190}" cy="24" r="5" fill="#39ff6b" />
      <text x="${W-178}" y="28" fill="#d8e5ff" font-size="12">Observed</text>
      <line x1="${W-105}" y1="24" x2="${W-78}" y2="24" stroke="#35d7ff" stroke-width="3" stroke-dasharray="8 5" />
      <text x="${W-70}" y="28" fill="#d8e5ff" font-size="12">Simulated</text>
    </svg>
  `;
}


function findFirstArrayByKeys(obj, keys) {
  if (!obj || typeof obj !== "object") return null;

  for (const key of Object.keys(obj)) {
    const lk = key.toLowerCase();

    if (keys.some(k => lk.includes(k)) && Array.isArray(obj[key]) && obj[key].length > 0) {
      return obj[key];
    }
  }

  for (const key of Object.keys(obj)) {
    const value = obj[key];

    if (value && typeof value === "object") {
      const found = findFirstArrayByKeys(value, keys);
      if (found) return found;
    }
  }

  return null;
}

function findFirstStringByKeys(obj, keys) {
  if (!obj || typeof obj !== "object") return null;

  for (const key of Object.keys(obj)) {
    const lk = key.toLowerCase();

    if (keys.some(k => lk.includes(k)) && typeof obj[key] === "string" && obj[key].length > 0) {
      return obj[key];
    }
  }

  for (const key of Object.keys(obj)) {
    const value = obj[key];

    if (value && typeof value === "object") {
      const found = findFirstStringByKeys(value, keys);
      if (found) return found;
    }
  }

  return null;
}

function normalizeProfilePayload(block) {
  const root = block.data || block.payload || block || {};

  // 1. If backend already generated a PNG/image path, use it.
  const imageUrl =
    findFirstStringByKeys(root, ["png", "image_url", "plot_url", "fallback_plot", "map_url"]) ||
    null;

  // 2. Try common direct formats.
  let dates =
    root.dates || root.date || root.time || root.times || root.x ||
    root.profile?.dates || root.profile?.date || root.profile?.time || root.profile?.x ||
    root.series?.dates || root.series?.date || root.series?.time || root.series?.x ||
    null;

  let simulated =
    root.simulated || root.sim || root.sim_values || root.y_sim || root.simulation ||
    root.profile?.simulated || root.profile?.sim || root.profile?.y_sim ||
    root.series?.simulated || root.series?.sim || root.series?.y_sim ||
    null;

  let observed =
    root.observed || root.obs || root.hist || root.historical || root.observed_values || root.y_obs ||
    root.profile?.observed || root.profile?.obs || root.profile?.hist || root.profile?.y_obs ||
    root.series?.observed || root.series?.obs || root.series?.hist || root.series?.y_obs ||
    null;

  // 3. Recursive fallback.
  if (!dates) {
    dates = findFirstArrayByKeys(root, ["date", "time", "month", "year", "x"]);
  }

  if (!simulated) {
    simulated = findFirstArrayByKeys(root, ["simulated", "simulation", "sim_", "sim"]);
  }

  if (!observed) {
    observed = findFirstArrayByKeys(root, ["observed", "historical", "history", "hist", "obs"]);
  }

  // 4. If payload is table-like rows, extract columns.
  const rows =
    Array.isArray(root.rows) ? root.rows :
    Array.isArray(root.data) ? root.data :
    Array.isArray(root.series) ? root.series :
    null;

  if ((!dates || !simulated || !observed) && rows && rows.length && typeof rows[0] === "object") {
    const cols = Object.keys(rows[0]);
    const lower = Object.fromEntries(cols.map(c => [c.toLowerCase(), c]));

    const dateCol = cols.find(c => /date|time|month|year/i.test(c));
    const simCol = cols.find(c => /sim|simulation|simulated/i.test(c));
    const obsCol = cols.find(c => /obs|observed|hist|historical/i.test(c));

    if (dateCol && !dates) dates = rows.map(r => r[dateCol]);
    if (simCol && !simulated) simulated = rows.map(r => r[simCol]);
    if (obsCol && !observed) observed = rows.map(r => r[obsCol]);
  }

  return {
    root,
    imageUrl,
    dates: Array.isArray(dates) ? dates : [],
    simulated: Array.isArray(simulated) ? simulated : [],
    observed: Array.isArray(observed) ? observed : [],
    title: block.title || root.title || root.well || "Simulated vs Observed Profile",
  };
}

function renderProfilePlot(block) {
  const panel = document.getElementById("visualPanel");
  if (!ensurePlotlyAvailableV11()) return;
  const parsed = normalizeProfilePayload(block);

  // If backend gave us a PNG/image, show it.
  if (parsed.imageUrl) {
    let url = parsed.imageUrl;

    if (!url.startsWith("/") && !url.startsWith("http")) {
      url = "/" + url.replaceAll("\\\\", "/");
    }

    panel.innerHTML = `
      <div class="section-title">${escapeHtml(parsed.title)}</div>
      <img src="${escapeHtml(url)}" style="width:100%;max-height:520px;object-fit:contain;border-radius:16px;border:1px solid rgba(160,190,255,.14);background:#061022" />
    `;
    return;
  }

  const dates = parsed.dates;
  const sim = parsed.simulated.map(Number);
  const obs = parsed.observed.map(Number);

  const n = Math.max(dates.length, sim.length, obs.length);

  if (n < 2 || (!sim.some(Number.isFinite) && !obs.some(Number.isFinite))) {
    panel.innerHTML = `
      <div class="section-title">Profile plot not available</div>
      <div class="empty-state">
        I received profile data, but could not detect valid date, simulated and observed arrays.
        <br/><br/>
        <b>Detected:</b><br/>
        dates: ${dates.length}<br/>
        simulated: ${sim.length}<br/>
        observed: ${obs.length}
      </div>
      <pre>${escapeHtml(JSON.stringify(parsed.root, null, 2).slice(0, 5000))}</pre>
    `;
    return;
  }

  const W = 920;
  const H = 440;
  const padL = 62;
  const padR = 24;
  const padT = 48;
  const padB = 58;

  const vals = sim.concat(obs).filter(Number.isFinite);
  const ymin = 0;
  const ymax = Math.max(1, ...vals) * 1.08;

  function sx(i) {
    if (n <= 1) return padL;
    return padL + i * (W - padL - padR) / (n - 1);
  }

  function sy(v) {
    v = Number(v);
    if (!Number.isFinite(v)) return null;
    return H - padB - (v - ymin) * (H - padT - padB) / (ymax - ymin);
  }

  function makePath(arr) {
    let d = "";

    for (let i = 0; i < n; i++) {
      const y = sy(arr[i]);
      if (y === null) continue;

      d += `${d ? "L" : "M"} ${sx(i)} ${y} `;
    }

    return d;
  }

  function makePoints(arr, color) {
    const step = Math.max(1, Math.ceil(n / 90));
    let out = "";

    for (let i = 0; i < n; i += step) {
      const y = sy(arr[i]);
      if (y === null) continue;

      out += `<circle cx="${sx(i)}" cy="${y}" r="2.5" fill="${color}" opacity=".85">
        <title>${escapeHtml(String(dates[i] ?? i))}: ${fmt(arr[i], 2)}</title>
      </circle>`;
    }

    return out;
  }

  const simPath = makePath(sim);
  const obsPath = makePath(obs);

  const grid = Array.from({length: 5}, (_, k) => {
    const y = padT + k * (H - padT - padB) / 4;
    const val = ymax - k * ymax / 4;

    return `
      <line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="rgba(160,190,255,.13)" />
      <text x="${padL-10}" y="${y+4}" fill="#9fb2d0" font-size="11" text-anchor="end">${fmt(val, 0)}</text>
    `;
  }).join("");

  const xLabels = [0, Math.floor(n/2), n-1]
    .filter((v, idx, arr) => arr.indexOf(v) === idx)
    .map(i => `
      <text x="${sx(i)}" y="${H-26}" fill="#9fb2d0" font-size="11" text-anchor="middle">
        ${escapeHtml(String(dates[i] ?? i)).slice(0, 10)}
      </text>
    `).join("");

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(parsed.title)}</div>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:440px;border-radius:16px;background:#061022;border:1px solid rgba(160,190,255,.14)">
      <text x="${padL}" y="28" fill="#f8fafc" font-size="17" font-weight="900">${escapeHtml(parsed.title)}</text>

      ${grid}

      <line x1="${padL}" y1="${H-padB}" x2="${W-padR}" y2="${H-padB}" stroke="rgba(160,190,255,.35)" />
      <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H-padB}" stroke="rgba(160,190,255,.35)" />

      ${obsPath ? `<path d="${obsPath}" fill="none" stroke="#39ff6b" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />` : ""}
      ${simPath ? `<path d="${simPath}" fill="none" stroke="#35d7ff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="9 6" />` : ""}

      ${makePoints(obs, "#39ff6b")}
      ${makePoints(sim, "#35d7ff")}

      ${xLabels}

      <text x="${padL}" y="${H-8}" fill="#9fb2d0" font-size="12">Time</text>
      <text x="18" y="${padT}" fill="#9fb2d0" font-size="12" transform="rotate(-90 18 ${padT})">Value</text>

      <circle cx="${W-225}" cy="27" r="5" fill="#39ff6b" />
      <text x="${W-212}" y="31" fill="#d8e5ff" font-size="12">Observed</text>

      <line x1="${W-125}" y1="27" x2="${W-94}" y2="27" stroke="#35d7ff" stroke-width="3.5" stroke-dasharray="9 6" />
      <text x="${W-84}" y="31" fill="#d8e5ff" font-size="12">Simulated</text>
    </svg>
  `;
}



function getStreamlineTimeLabelV15(block) {
  const t =
    block.streamline_time ||
    block.streamline_payload?.requested_streamline_time ||
    block.payload?.streamline_time ||
    "auto";

  const labels = {
    initial: "Initial History",
    final: "End of History",
    compare: "Initial vs End of History",
    auto: "Default Snapshot",
  };

  return labels[t] || t;
}

function getMapPropertyLabelV14(block) {
  const payload = block.payload || block.data || {};
  return (
    block.title ||
    payload.label ||
    payload.property_label ||
    payload.requested_property ||
    payload.property ||
    "Property Map"
  );
}

function renderCellPropertyMap(block) {
  debugStreamlinePayloadV17(block);
  const p = block.payload;
  const panel = document.getElementById("visualPanel");

  if (!p || !p.ok) {
    panel.innerHTML = `<div class="empty-state">${escapeHtml(p?.message || "Map not available.")}</div>`;
    return;
  }

  const streamlinePayload = block.streamline_payload || null;
  const corridorPayload = block.corridor_payload || null;
  const uid = "cellmap_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(block.title || p.label || p.property)}</div>
    <div style="color:#9fb2d0;font-size:12px;margin-bottom:8px">
      ${escapeHtml(p.message || "")}<br/>
      Grid: ${p.nx} × ${p.ny} × ${p.nz} | Cells: ${p.cell_count}
      ${streamlinePayload ? ` | Streamlines/links: ${(streamlinePayload.lines || []).length}` : ""}
    </div>

    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
      <button id="${uid}_reset" style="border:none;border-radius:999px;padding:8px 11px;background:rgba(53,215,255,.12);color:#c9f6ff;font-weight:800;cursor:pointer">
        Reset zoom
      </button>
      <span style="color:#9fb2d0;font-size:12px">Wheel = zoom | drag = pan | hover = cell value | click well = insight</span>
    </div>

    <div id="${uid}_shell" style="position:relative;width:100%;height:500px;border-radius:16px;overflow:hidden;background:#061022;border:1px solid rgba(160,190,255,.14);cursor:grab">
      <canvas id="${uid}_canvas" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
      <div id="${uid}_overlay" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto"></div>
      <div id="${uid}_tooltip" style="position:fixed;display:none;z-index:9999;pointer-events:none;background:rgba(2,6,23,.96);border:1px solid rgba(160,190,255,.25);border-radius:10px;padding:8px 10px;color:#f8fafc;font-size:12px"></div>
    </div>

    <div style="margin-top:10px;padding:10px 12px;border:1px solid rgba(160,190,255,.14);border-radius:14px;background:rgba(255,255,255,.025)">
      <div style="font-size:12px;color:#d8e5ff;font-weight:900;margin-bottom:7px">${escapeHtml(p.label || p.property)} ${p.unit ? "(" + escapeHtml(p.unit) + ")" : ""}</div>
      <div style="height:13px;border-radius:999px;background:linear-gradient(90deg,rgb(30,100,255),rgb(70,200,255),rgb(255,235,45),rgb(255,90,35));border:1px solid rgba(255,255,255,.2)"></div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;color:#9fb2d0;font-size:12px">
        <span>${fmt(p.p2 ?? p.min,3)}</span>
        <span>low → high</span>
        <span>${fmt(p.p98 ?? p.max,3)}</span>
      </div>
    </div>
  `;

  requestAnimationFrame(() => {
    const shell = document.getElementById(`${uid}_shell`);
    const canvas = document.getElementById(`${uid}_canvas`);
    const overlay = document.getElementById(`${uid}_overlay`);
    const tooltip = document.getElementById(`${uid}_tooltip`);
    const reset = document.getElementById(`${uid}_reset`);

    const rect = shell.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;
    const pad = 28;

    const nx = Number(p.nx);
    const ny = Number(p.ny);
    const minV = p.p2 ?? p.min;
    const maxV = p.p98 ?? p.max;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);

    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const stateMap = { scale: 1, tx: 0, ty: 0, dragging: false, lx: 0, ly: 0 };
    const plotW = W - 2 * pad;
    const plotH = H - 2 * pad;

    const valueMap = new Map();
    for (const c of p.cells || []) {
      valueMap.set(`${Number(c.i)}_${Number(c.j)}`, Number(c.value));
    }

    function bx(i) { return pad + (Number(i)-1) * plotW / nx; }
    function by(j) { return pad + (Number(j)-1) * plotH / ny; }
    function sx(x) { return stateMap.tx + stateMap.scale * x; }
    function sy(y) { return stateMap.ty + stateMap.scale * y; }
    function invx(x) { return (x - stateMap.tx) / stateMap.scale; }
    function invy(y) { return (y - stateMap.ty) / stateMap.scale; }

    function drawCanvas() {
      ctx.setTransform(dpr,0,0,dpr,0,0);
      ctx.clearRect(0,0,W,H);
      ctx.fillStyle = "#061022";
      ctx.fillRect(0,0,W,H);

      ctx.save();
      ctx.translate(stateMap.tx, stateMap.ty);
      ctx.scale(stateMap.scale, stateMap.scale);

      ctx.strokeStyle = "rgba(160,190,255,.10)";
      ctx.lineWidth = 1 / stateMap.scale;

      for (let k=0; k<=8; k++) {
        const x = pad + k * plotW / 8;
        const y = pad + k * plotH / 8;
        ctx.beginPath(); ctx.moveTo(x,pad); ctx.lineTo(x,H-pad); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(W-pad,y); ctx.stroke();
      }

      const cw = Math.max(1, plotW / nx);
      const ch = Math.max(1, plotH / ny);

      for (const c of p.cells || []) {
        const i = Number(c.i);
        const j = Number(c.j);
        const v = Number(c.value);
        if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;

        ctx.fillStyle = heatColorForProperty(v, minV, maxV);
        ctx.globalAlpha = .9;
        ctx.fillRect(bx(i), by(j), Math.ceil(cw) + .4, Math.ceil(ch) + .4);
      }

      ctx.globalAlpha = 1;

      if (corridorPayload && corridorPayload.cells && corridorPayload.cells.length) {
        const cells = corridorPayload.cells;
        const step = Math.max(1, Math.ceil(cells.length / 6500));
        ctx.fillStyle = "rgba(255,220,80,.90)";
        for (let idx=0; idx<cells.length; idx+=step) {
          const c = cells[idx];
          ctx.fillRect(bx(c.i), by(c.j), Math.max(3/stateMap.scale, cw*1.5), Math.max(3/stateMap.scale, ch*1.5));
        }
      }

      ctx.restore();
    }

    function drawOverlay() {
      const wells = p.wells || [];
      const lines = streamlinePayload && streamlinePayload.lines ? streamlinePayload.lines : [];

      let svg = `
        <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
          <defs>
            <filter id="wellGlow">
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <marker id="arrowCyan" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L7,3 z" fill="#67e8f9" opacity=".85" />
            </marker>
          </defs>
      `;

      const maxLines = 450;
      const lineStep = Math.max(1, Math.ceil(lines.length / maxLines));

      for (let idx=0; idx<lines.length; idx+=lineStep) {
        const line = lines[idx];
        const pts = line.points || [];
        if (pts.length < 2) continue;

        const d = pts.map((pt, k) => {
          const x = sx(bx(pt.i));
          const y = sy(by(pt.j));
          return `${k === 0 ? "M" : "L"} ${x} ${y}`;
        }).join(" ");

        svg += `
          <path d="${d}" fill="none" stroke="#67e8f9" stroke-width="2.2" opacity=".55"
                stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrowCyan)">
            <title>Streamline / connectivity</title>
          </path>
        `;
      }

      for (const w of wells) {
        if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

        const x = sx(bx(w.i));
        const y = sy(by(w.j));

        if (x < -80 || y < -80 || x > W+80 || y > H+80) continue;

        const producer = !!w.producer_candidate;
        const injector = !!w.injector_candidate && !producer;
        const inactive = producer && w.active_producer === false;

        const scoreObj = selectedScore(w);
        let klass = inactive ? "Inactive" : (scoreObj.class || w.overall_class || "Not Evaluated");
        if (injector) klass = w.injection_class || "Not Evaluated";

        const color = mapClassColor(klass);
        const label = escapeHtml(w.well);

        if (injector) {
          svg += `
            <g onclick="selectWell('${label}')" style="cursor:pointer">
              <polygon points="${x},${y-12} ${x+12},${y} ${x},${y+12} ${x-12},${y}" fill="${color}" stroke="#fff" stroke-width="1.5" filter="url(#wellGlow)" />
              <text x="${x+15}" y="${y-9}" fill="#f8fafc" font-size="12" font-weight="800">${label}</text>
              <title>${label} | Injector | ${klass}</title>
            </g>`;
        } else {
          svg += `
            <g onclick="selectWell('${label}')" style="cursor:pointer">
              <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity=".16" />
              <circle cx="${x}" cy="${y}" r="8.5" fill="${color}" stroke="#fff" stroke-width="1.5" opacity="${inactive ? .55 : 1}" filter="url(#wellGlow)" />
              <text x="${x+14}" y="${y-9}" fill="#f8fafc" font-size="12" font-weight="800">${label}</text>
              <title>${label} | ${klass}</title>
            </g>`;
        }
      }

      svg += `</svg>`;
      overlay.innerHTML = svg;
    }

    function redraw() {
      drawCanvas();
      drawOverlay();
    }

    redraw();

    reset.addEventListener("click", () => {
      stateMap.scale = 1;
      stateMap.tx = 0;
      stateMap.ty = 0;
      redraw();
    });

    shell.addEventListener("wheel", ev => {
      ev.preventDefault();
      const r = shell.getBoundingClientRect();
      const mx = ev.clientX - r.left;
      const my = ev.clientY - r.top;
      const old = stateMap.scale;
      const factor = ev.deltaY < 0 ? 1.18 : 1/1.18;
      const next = Math.max(.55, Math.min(10, old * factor));
      stateMap.tx = mx - (next / old) * (mx - stateMap.tx);
      stateMap.ty = my - (next / old) * (my - stateMap.ty);
      stateMap.scale = next;
      redraw();
    }, {passive:false});

    shell.addEventListener("mousedown", ev => {
      stateMap.dragging = true;
      stateMap.lx = ev.clientX;
      stateMap.ly = ev.clientY;
      shell.style.cursor = "grabbing";
    });

    window.addEventListener("mousemove", ev => {
      if (!stateMap.dragging) return;
      stateMap.tx += ev.clientX - stateMap.lx;
      stateMap.ty += ev.clientY - stateMap.ly;
      stateMap.lx = ev.clientX;
      stateMap.ly = ev.clientY;
      redraw();
    });

    window.addEventListener("mouseup", () => {
      stateMap.dragging = false;
      shell.style.cursor = "grab";
    });

    shell.addEventListener("mousemove", ev => {
      const r = shell.getBoundingClientRect();
      const x = ev.clientX - r.left;
      const y = ev.clientY - r.top;
      const baseX = invx(x);
      const baseY = invy(y);
      const i = Math.floor((baseX - pad) / plotW * nx) + 1;
      const j = Math.floor((baseY - pad) / plotH * ny) + 1;

      if (i < 1 || j < 1 || i > nx || j > ny) {
        tooltip.style.display = "none";
        return;
      }

      const val = valueMap.get(`${i}_${j}`);
      tooltip.style.display = "block";
      tooltip.style.left = `${ev.clientX + 14}px`;
      tooltip.style.top = `${ev.clientY + 14}px`;
      tooltip.innerHTML = `
        <b>${escapeHtml(p.label || p.property)}</b><br/>
        I=${i}, J=${j}<br/>
        Value: ${fmt(val,3)} ${escapeHtml(p.unit || "")}
      `;
    });

    shell.addEventListener("mouseleave", () => tooltip.style.display = "none");
  });
}


function renderInteractiveHmMap(block) {
  const panel = document.getElementById("visualPanel");
  const payload = block.payload || block.data || {};
  const wells = payload.wells || [];
  const variable = payload.variable || state.variable || "overall";

  
  // HM_MAP_EMPTY_FILTER_FALLBACK_V392
  // If the default active-producer filter removes every well, keep the dashboard useful:
  // show all wells with valid I/J coordinates instead of an empty map.
  if ((!wells || !wells.length) && hmMapPayload && Array.isArray(hmMapPayload.wells)) {
    const fallbackWells = hmMapPayload.wells.filter(w =>
      Number.isFinite(Number(w.i)) && Number.isFinite(Number(w.j))
    );

    if (fallbackWells.length) {
      wells = fallbackWells;
    }
  }

if (!wells.length) {
    panel.innerHTML = `<div class="empty-state">No wells available in this map payload.</div>`;
    return;
  }

  const activeWells = wells.filter(w =>
    w.i !== null &&
    w.i !== undefined &&
    w.j !== null &&
    w.j !== undefined &&
    (
      (w.producer_candidate && w.active_producer) ||
      (state.showInjectors && w.injector_candidate) ||
      (state.showInactive && w.producer_candidate && !w.active_producer)
    )
  );

  const items = activeWells.length ? activeWells : wells.filter(w =>
    w.i !== null && w.i !== undefined && w.j !== null && w.j !== undefined
  );

  if (!items.length) {
    panel.innerHTML = `<div class="empty-state">No spatial wells available for this map.</div>`;
    return;
  }

  const W = 900;
  const H = 520;
  const pad = 55;

  const iVals = items.map(w => Number(w.i)).filter(Number.isFinite);
  const jVals = items.map(w => Number(w.j)).filter(Number.isFinite);

  const minI = Math.min(...iVals);
  const maxI = Math.max(...iVals);
  const minJ = Math.min(...jVals);
  const maxJ = Math.max(...jVals);

  const sx = i => maxI === minI ? W / 2 : pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  const sy = j => maxJ === minJ ? H / 2 : pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);

  function classColor(kls) {
    const c = String(kls || "").toLowerCase();
    if (c === "good") return "#39ff6b";
    if (c === "fair") return "#ffd84d";
    if (c === "poor") return "#ff5757";
    return "#9fb2d0";
  }

  let grid = "";
  for (let k = 0; k <= 8; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    grid += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(160,190,255,.12)" />`;
    grid += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(160,190,255,.12)" />`;
  }

  const points = items.map(w => {
    const x = sx(w.i);
    const y = sy(w.j);

    const score = w[`${variable}_score`] ?? w.overall_score;
    let kls = w[`${variable}_class`] || w.overall_class || "Not Evaluated";

    const isInjector = w.injector_candidate && !w.producer_candidate;
    const isInactive = w.producer_candidate && !w.active_producer;

    if (isInactive) kls = "Inactive";

    const color = classColor(kls);
    const label = escapeHtml(w.well);

    if (isInjector) {
      return `
        <g onclick="selectWell('${label}')" style="cursor:pointer">
          <polygon points="${x},${y-12} ${x+12},${y} ${x},${y+12} ${x-12},${y}"
            fill="${color}" stroke="#fff" stroke-width="1.5" />
          <text x="${x+15}" y="${y-9}" fill="#f8fafc" font-size="12" font-weight="800">${label}</text>
          <title>${label} | Injector | ${kls}</title>
        </g>`;
    }

    return `
      <g onclick="selectWell('${label}')" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity=".16" />
        <circle cx="${x}" cy="${y}" r="8.5" fill="${color}" stroke="#fff" stroke-width="1.5" opacity="${isInactive ? .55 : 1}" />
        <text x="${x+14}" y="${y-9}" fill="#f8fafc" font-size="12" font-weight="800">${label}</text>
        <title>${label} | ${kls} | ${variable.toUpperCase()} ${fmt(score,1)}</title>
      </g>`;
  }).join("");

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(block.title || payload.title || "History Match Map")}</div>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:500px;border-radius:16px;background:#061022;border:1px solid rgba(160,190,255,.14)">
      <text x="34" y="34" fill="#f8fafc" font-size="18" font-weight="900">${escapeHtml(payload.title || block.title || "History Match Map")}</text>
      <text x="34" y="56" fill="#9fb2d0" font-size="12">Color by ${variable.toUpperCase()} score. Click a well to inspect detail.</text>
      ${grid}
      ${points}
    </svg>

    <div class="legend">
      <span><span class="dot" style="background:#39ff6b"></span>Good</span>
      <span><span class="dot" style="background:#ffd84d"></span>Fair</span>
      <span><span class="dot" style="background:#ff5757"></span>Poor</span>
      <span><span class="dot" style="background:#9fb2d0"></span>Inactive / Not evaluated</span>
      <span>● Producer</span>
      <span>◆ Injector</span>
    </div>
  `;
}


function renderCompactTable(block) {
  const rows = block.rows || [];
  const columns = block.columns || (rows.length ? Object.keys(rows[0]) : []);
  if (!rows.length) return "";

  return `
    <div class="section-title">${escapeHtml(block.title || "Table")}</div>
    <div style="overflow:auto;border:1px solid rgba(160,190,255,.14);border-radius:14px">
      <table style="width:100%;border-collapse:collapse;font-size:12px;color:#d8e5ff">
        <thead>
          <tr>
            ${columns.map(c => `<th style="text-align:left;padding:8px;border-bottom:1px solid rgba(160,190,255,.14);color:#9fb2d0">${escapeHtml(c)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              ${columns.map(c => `<td style="padding:8px;border-bottom:1px solid rgba(160,190,255,.08)">${escapeHtml(r[c] ?? "")}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderCompactNotes(block) {
  const items = block.items || [];
  if (!items.length) return "";
  return `
    <div class="section-title">${escapeHtml(block.title || "Evidence")}</div>
    <ul class="insight-list">
      ${items.map(x => `<li>${escapeHtml(x)}</li>`).join("")}
    </ul>
  `;
}

function renderSuggestions(block) {
  const items = block.items || [];
  if (!items.length) return "";
  return `
    <div class="section-title">${escapeHtml(block.title || "Suggested follow-up")}</div>
    <div class="quick-actions">
      ${items.map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${escapeHtml(x)}</button>`).join("")}
    </div>
  `;
}

function renderVisualResponse(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  answer.innerHTML = `<p>${escapeHtml(data.answer || "")}</p>`;

  const blocks = data.ui_blocks || [];
  let visualHtml = "";

  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      renderCellPropertyMapV20(block);
      return;
    }

    if (block.type === "tran_corridor_map") {
      renderTRANCorridorMapV47(block);
      return;
    }

    if (block.type === "plotly_chart" && typeof renderPlotlyChartBlockV505A === "function") { renderPlotlyChartBlockV505A(block); return true; }

  if (block.type === "generic_property_map") {
      renderGenericPropertyMapV49(block);
      return;
    }

    if (block.type === "profile_ensemble") {
      renderProfileEnsembleV49(block);
      return;
    }

    if (block.type === "cluster_map") {
      renderSimilarityClusterMapV32(block);
      return;
    }

    if (block.type === "interactive_map") {
      renderInteractiveHmMap(block);
      return;
    }

    if (block.type === "profile_series") {
      renderProfilePlotV11(block);
      return;
    }

    if (block.type === "correlation_scatter") {
      renderCorrelationScatterV11(block);
      return;
    }

    if (block.type === "cluster_map") {
      renderSimilarityClusterMapV32(block);
      return;
    }

    if (renderVisualBlockForcedV50(block)) {
      return;
    }

    if (block.type === "compact_table") {
      visualHtml += renderCompactTable(block);
    }

    else if (block.type === "compact_notes") {
      visualHtml += renderCompactNotes(block);
    }

    else if (block.type === "suggestions") {
      visualHtml += renderSuggestions(block);
    }
  }

  if (visualHtml) {
    visual.innerHTML = visualHtml;
    return;
  }

  if (data.intent === "hm_map" || data.intent === "ranking" || data.intent === "area_summary") {
    renderInteractiveHmMap({
      title: data.data?.title || "History Match Map",
      payload: data.data
    });
    return;
  }

  visual.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.data || {}, null, 2).slice(0, 5000))}</pre>`;
}

async function askChat(prompt) {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  const msg = prompt || input.value.trim();
  if (!msg) return;

  input.value = msg;
  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<div class="empty-state">Preparing visual evidence...</div>`;

  try {
    const data = await postJson("/api/agent-chat-v501", {message: msg});
    if (data.type === "visual_response") renderVisualResponse(data);
    else {
      answer.innerHTML = `<p>${escapeHtml(data.answer || "No answer.")}</p>`;
      visual.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.data || {}, null, 2).slice(0, 5000))}</pre>`;
    }
  } catch (e) {
    answer.innerHTML = `<p style="color:#ff5757">Chat request failed: ${escapeHtml(e.message)}</p>`;
    visual.innerHTML = `<div class="empty-state">No visual output generated.</div>`;
  }
}

window.askQuick = askChat;

async function runDiagnostics() {
  try {
    await postJson("/run", {});
    await refreshAll();
  } catch (e) {
    alert("Run failed: " + e.message);
  }
}

async function refreshAll() {
  await Promise.all([loadKpis(), loadMap()]);
}

function bindEvents() {
  document.getElementById("hmVariable").addEventListener("change", e => {
    state.variable = e.target.value;
    renderMap();
  });

  document.getElementById("showInjectors").addEventListener("change", e => {
    state.showInjectors = e.target.checked;
    renderMap();
  });

  document.getElementById("showInactive").addEventListener("change", e => {
    state.showInactive = e.target.checked;
    renderMap();
  });

  document.getElementById("askBtn").addEventListener("click", () => askChat());
  document.getElementById("chatInput").addEventListener("keydown", e => {
    if (e.key === "Enter") askChat();
  });

  document.querySelectorAll(".quick-actions button").forEach(btn => {
    btn.addEventListener("click", () => askChat(btn.dataset.prompt));
  });

  document.getElementById("refreshBtn").addEventListener("click", refreshAll);
  document.getElementById("runBtn").addEventListener("click", runDiagnostics);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await refreshAll();
});



// ==========================================================
// CHAT UX FIX V9
// - Suggestions trigger a real new request immediately
// - Ask button always uses current input
// - Visual panel is cleared on every request
// - Late responses are ignored
// ==========================================================

let chatRequestSeqV9 = 0;

function attrEscape(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderSuggestionsV9(block) {
  const items = block.items || [];
  if (!items.length) return "";

  return `
    <div class="section-title">${escapeHtml(block.title || "Suggested follow-up")}</div>
    <div class="quick-actions">
      ${items.map(x => `
        <button type="button" data-prompt="${attrEscape(x)}">
          ${escapeHtml(x)}
        </button>
      `).join("")}
    </div>
  `;
}

function renderCompactNotesV9(block) {
  const items = block.items || [];
  if (!items.length) return "";

  return `
    <div class="section-title">${escapeHtml(block.title || "Evidence")}</div>
    <ul class="insight-list">
      ${items.map(x => `<li>${escapeHtml(x)}</li>`).join("")}
    </ul>
  `;
}

function renderCompactTableV9(block) {
  const rows = block.rows || [];
  const columns = block.columns || (rows.length ? Object.keys(rows[0]) : []);

  if (!rows.length) return "";

  return `
    <div class="section-title">${escapeHtml(block.title || "Table")}</div>
    <div style="overflow:auto;border:1px solid rgba(160,190,255,.14);border-radius:14px;margin-bottom:12px">
      <table style="width:100%;border-collapse:collapse;font-size:12px;color:#d8e5ff">
        <thead>
          <tr>
            ${columns.map(c => `<th style="text-align:left;padding:8px;border-bottom:1px solid rgba(160,190,255,.14);color:#9fb2d0">${escapeHtml(c)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              ${columns.map(c => `<td style="padding:8px;border-bottom:1px solid rgba(160,190,255,.08)">${escapeHtml(r[c] ?? "")}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderVisualResponseV9(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  answer.innerHTML = `<p>${escapeHtml(data.answer || "")}</p>`;

  const blocks = data.ui_blocks || [];
  let visualHtml = "";

  // Prefer real visual blocks first.
  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      renderCellPropertyMapV20(block);
      return;
    }

    if (block.type === "tran_corridor_map") {
      renderTRANCorridorMapV47(block);
      return;
    }

    if (block.type === "plotly_chart" && typeof renderPlotlyChartBlockV505A === "function") { renderPlotlyChartBlockV505A(block); return true; }

  if (block.type === "generic_property_map") {
      renderGenericPropertyMapV49(block);
      return;
    }

    if (block.type === "profile_ensemble") {
      renderProfileEnsembleV49(block);
      return;
    }

    if (block.type === "cluster_map") {
      renderSimilarityClusterMapV32(block);
      return;
    }

    if (block.type === "interactive_map") {
      renderInteractiveHmMap(block);
      return;
    }

    if (block.type === "profile_series") {
      renderProfilePlotV11(block);
      return;
    }

    if (block.type === "correlation_scatter") {
      renderCorrelationScatterV11(block);
      return;
    }

    if (block.type === "cluster_map") {
      renderSimilarityClusterMapV32(block);
      return;
    }
  }

  // Otherwise render supporting evidence.
  for (const block of blocks) {
    if (renderVisualBlockForcedV50(block)) {
      return;
    }

    if (block.type === "compact_table") {
      visualHtml += renderCompactTableV9(block);
    } else if (block.type === "compact_notes") {
      visualHtml += renderCompactNotesV9(block);
    } else if (block.type === "suggestions") {
      visualHtml += renderSuggestionsV9(block);
    }
  }

  if (visualHtml) {
    visual.innerHTML = visualHtml;
    return;
  }

  if (data.intent === "hm_map" || data.intent === "ranking" || data.intent === "area_summary") {
    renderInteractiveHmMap({
      title: data.data?.title || "History Match Map",
      payload: data.data
    });
    return;
  }

  visual.innerHTML = `<div class="empty-state">No visual evidence was returned for this question.</div>`;
}

async function askChatV9(prompt = null) {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  const msg = String(prompt || input.value || "").trim();
  if (!msg) return;

  input.value = msg;

  const requestId = ++chatRequestSeqV9;

  answer.innerHTML = `<p>Investigating: <b>${escapeHtml(msg)}</b>...</p>`;
  visual.innerHTML = `<div class="empty-state">Preparing new visual evidence...</div>`;

  try {
    const data = await postJson("/api/agent-chat-v501?t=" + Date.now(), {message: msg});

    // V52: force visual block rendering immediately after chat response.
    try {
      console.log("[V52] Chat response received", {
        intent: data && data.intent,
        blocks: data && data.ui_blocks ? data.ui_blocks.map(b => b.type) : []
      });

      setTimeout(() => {
        try {
          if (typeof tryRenderFirstSupportedVisualBlockV51 === "function") {
            const ok = forceRenderChatVisualsV52(data);
            console.log("[V52] Forced visual render result:", ok);
          } else {
            console.warn("[V52] tryRenderFirstSupportedVisualBlockV51 is not available");
          }
        } catch (e) {
          console.error("[V52] Forced visual render failed", e);
        }
      }, 120);

      setTimeout(() => {
        try {
          if (typeof tryRenderFirstSupportedVisualBlockV51 === "function") {
            forceRenderChatVisualsV52(data);
          }
        } catch (e) {}
      }, 700);

    } catch (e) {
      console.error("[V52] Chat visual auto-render hook failed", e);
    }

    // Ignore stale responses if the user clicked another suggestion quickly.
    if (requestId !== chatRequestSeqV9) return;

    if (data.type === "visual_response") {
      renderVisualResponseV9(data);
    } else {
      answer.innerHTML = `<p>${escapeHtml(data.answer || "No answer.")}</p>`;
      visual.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.data || {}, null, 2).slice(0, 5000))}</pre>`;
    }

  } catch (e) {
    if (requestId !== chatRequestSeqV9) return;

    answer.innerHTML = `<p style="color:#ff5757">Chat request failed: ${escapeHtml(e.message)}</p>`;
    visual.innerHTML = `<div class="empty-state">No visual output generated.</div>`;
  }
}

// Override global quick action behavior.
window.askQuick = function(prompt) {
  return askChatV9(prompt);
};

// Override main ask behavior.
window.askChat = askChatV9;

// Event delegation for any future suggestion button.
document.addEventListener("click", function(ev) {
  const btn = ev.target.closest("button[data-prompt]");
  if (!btn) return;

  ev.preventDefault();
  ev.stopPropagation();

  const prompt = btn.getAttribute("data-prompt");
  if (prompt) askChatV9(prompt);
});

// Re-bind Ask button safely after page load.
setTimeout(() => {
  const askBtn = document.getElementById("askBtn");
  const input = document.getElementById("chatInput");

  if (askBtn) {
    askBtn.onclick = function(ev) {
      ev.preventDefault();
      askChatV9();
    };
  }

  if (input) {
    input.onkeydown = function(ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        askChatV9();
      }
    };
  }
}, 500);



// ==========================================================
// DYNAMIC PLOTLY VISUALS V11
// Interactive profiles and dynamic correlation crossplots.
// ==========================================================

function renderCorrelationScatterV11(block) {
  const panel = document.getElementById("visualPanel");
  if (!ensurePlotlyAvailableV11()) return;
  const uid = "corr_" + Date.now();

  const points = block.points || [];
  if (!points.length) {
    panel.innerHTML = `<div class="empty-state">No points available for this crossplot.</div>`;
    return;
  }

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(block.title || "Dynamic correlation plot")}</div>
    <div id="${uid}" style="width:100%;height:520px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  const x = points.map(p => p.x);
  const y = points.map(p => p.y);
  const labels = points.map(p => p.well || "");
  const colors = points.map(p => Number.isFinite(Number(p.water)) ? Number(p.water) : null);

  const trace = {
    type: "scatter",
    mode: "markers+text",
    x,
    y,
    text: labels,
    textposition: "top center",
    marker: {
      size: 13,
      color: colors,
      colorscale: "RdYlGn",
      reversescale: false,
      showscale: true,
      colorbar: {title: "Water HM"},
      line: {width: 1, color: "white"},
    },
    customdata: points.map(p => [
      p.well, p.overall, p.water, p.oil, p.gas, p.bhp, p.i, p.j
    ]),
    hovertemplate:
      "<b>%{customdata[0]}</b><br>" +
      `${escapeHtml(block.x_label || "X")}: %{x:.3f}<br>` +
      `${escapeHtml(block.y_label || "Y")}: %{y:.3f}<br>` +
      "Overall HM: %{customdata[1]:.1f}<br>" +
      "Water HM: %{customdata[2]:.1f}<br>" +
      "Oil HM: %{customdata[3]:.1f}<br>" +
      "Gas HM: %{customdata[4]:.1f}<br>" +
      "BHP HM: %{customdata[5]:.1f}<br>" +
      "I,J: %{customdata[6]}, %{customdata[7]}<extra></extra>",
  };

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: {color: "#d8e5ff"},
    margin: {l: 70, r: 40, t: 40, b: 70},
    xaxis: {
      title: block.x_label || "X",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.25)",
    },
    yaxis: {
      title: block.y_label || "Y",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.25)",
    },
    hovermode: "closest",
  };

  Plotly.newPlot(uid, [trace], layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}

function ensurePlotlyAvailableV11() {
  if (typeof Plotly === "undefined") {
    const panel = document.getElementById("visualPanel");
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">
        Plotly was not loaded by the browser, so interactive charts cannot be rendered.
        Check internet access or use a local Plotly bundle.
      </div>
    `;
    return false;
  }
  return true;
}


function inferProfileAxisMetaV13(title, root) {
  const t = String(title || "").toLowerCase();
  const variable = String(root?.variable || "").toLowerCase();

  const key = `${t} ${variable}`;

  if (key.includes("wct") || key.includes("water cut")) {
    return {
      yTitle: "Water Cut, fraction",
      hoverUnit: "fraction",
      forceRange: [0, 1],
    };
  }

  if (key.includes("water")) {
    return {
      yTitle: "Water Production Rate, STB/day",
      hoverUnit: "STB/day",
      forceRange: null,
    };
  }

  if (key.includes("oil")) {
    return {
      yTitle: "Oil Production Rate, STB/day",
      hoverUnit: "STB/day",
      forceRange: null,
    };
  }

  if (key.includes("gas") || key.includes("gor")) {
    return {
      yTitle: "Gas Production Rate, Mscf/day",
      hoverUnit: "Mscf/day",
      forceRange: null,
    };
  }

  if (key.includes("bhp") || key.includes("bottom hole") || key.includes("pressure")) {
    return {
      yTitle: "Bottom-Hole Pressure, psi",
      hoverUnit: "psi",
      forceRange: null,
    };
  }

  return {
    yTitle: "Value",
    hoverUnit: "",
    forceRange: null,
  };
}

function renderProfilePlotV11(block) {
  const panel = document.getElementById("visualPanel");
  if (!ensurePlotlyAvailableV11()) return;
  const parsed = normalizeProfilePayload(block);

  const dates = parsed.dates || [];
  const sim = (parsed.simulated || []).map(v => Number(v));
  const obs = (parsed.observed || []).map(v => Number(v));
  const axisMeta = inferProfileAxisMetaV13(parsed.title, parsed.root);

  const n = Math.max(dates.length, sim.length, obs.length);

  // IMPORTANT:
  // Prefer interactive Plotly if any valid simulated/observed data exists.
  // Use PNG/image only as last fallback.
  const hasSeries =
    n >= 2 &&
    (
      sim.some(Number.isFinite) ||
      obs.some(Number.isFinite)
    );

  if (!hasSeries && parsed.imageUrl) {
    let url = parsed.imageUrl;
    if (!url.startsWith("/") && !url.startsWith("http")) {
      url = "/" + url.replaceAll("\\", "/");
    }

    panel.innerHTML = `
      <div class="section-title">${escapeHtml(parsed.title)} - static fallback</div>
      <div class="empty-state" style="padding:10px 0">
        Interactive data arrays were not detected, so I am showing the static fallback image.
      </div>
      <img src="${escapeHtml(url)}" style="width:100%;max-height:520px;object-fit:contain;border-radius:16px;border:1px solid rgba(160,190,255,.14);background:#061022" />
    `;
    return;
  }

  if (!hasSeries) {
    panel.innerHTML = `
      <div class="section-title">Interactive profile not available</div>
      <div class="empty-state">
        I received a profile response, but I could not detect valid simulated/observed arrays.
      </div>
      <pre>${escapeHtml(JSON.stringify(parsed.root, null, 2).slice(0, 5000))}</pre>
    `;
    return;
  }

  const uid = "profile_" + Date.now();
  const x = Array.from({length: n}, (_, i) => dates[i] ?? i);

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(parsed.title)} - interactive profile</div>
    <div id="${uid}" style="width:100%;height:540px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  const traces = [];

  if (obs.some(Number.isFinite)) {
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: "Observed",
      x,
      y: obs,
      line: {width: 3},
      marker: {size: 5},
      hovertemplate: `Observed<br>%{x}<br>%{y:.4f} ${axisMeta.hoverUnit}<extra></extra>`,
    });
  }

  if (sim.some(Number.isFinite)) {
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: "Simulated",
      x,
      y: sim,
      line: {width: 3, dash: "dash"},
      marker: {size: 5},
      hovertemplate: `Simulated<br>%{x}<br>%{y:.4f} ${axisMeta.hoverUnit}<extra></extra>`,
    });
  }

  const finiteVals = obs.concat(sim).filter(Number.isFinite);
  const maxY = Math.max(1, ...finiteVals);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: {color: "#d8e5ff"},
    margin: {l: 70, r: 35, t: 35, b: 85},
    xaxis: {
      title: "Time",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.25)",
      rangeslider: {visible: true},
    },
    yaxis: {
      title: axisMeta.yTitle,
      rangemode: "tozero",
      range: axisMeta.forceRange || [0, maxY * 1.08],
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.25)",
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.32,
    },
    hovermode: "x unified",
  };

  if (axisMeta.forceRange) {
    layout.yaxis.range = axisMeta.forceRange;
  }

  const streamlineTracesV17 = buildStreamlineTracesV17(block);
  const allTracesV17 = traces.concat(streamlineTracesV17);
  Plotly.purge(uid);
  Plotly.newPlot(uid, allTracesV17, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}

// Override existing profile renderer.
window.renderProfilePlot = renderProfilePlotV11;



// ==========================================================
// STREAMLINE FRONTEND HARD FIX V17
// Always render streamlines from the current response block.
// Never reuse cached/global streamline payloads.
// ==========================================================

function extractCurrentStreamlineLinesV17(block) {
  const sp = block?.streamline_payload || {};
  const candidates = [
    sp.lines,
    sp.streamlines,
    sp.data,
    sp.features,
    sp.payload?.lines,
    sp.payload?.streamlines,
  ];

  for (const c of candidates) {
    if (Array.isArray(c) && c.length) return c;
  }

  return [];
}

function normalizeStreamlineLineV17(line) {
  if (!line) return null;

  // Format A: {points:[{i,j},{i,j}]}
  if (Array.isArray(line.points) && line.points.length >= 2) {
    const xs = [];
    const ys = [];

    for (const p of line.points) {
      const x = Number(p.i ?? p.I ?? p.x ?? p.X);
      const y = Number(p.j ?? p.J ?? p.y ?? p.Y);
      if (Number.isFinite(x) && Number.isFinite(y)) {
        xs.push(x);
        ys.push(y);
      }
    }

    if (xs.length >= 2) return {x: xs, y: ys};
  }

  // Format B: {x:[...], y:[...]}
  if (Array.isArray(line.x) && Array.isArray(line.y)) {
    return {
      x: line.x.map(Number).filter(Number.isFinite),
      y: line.y.map(Number).filter(Number.isFinite),
    };
  }

  // Format C: {xs:[...], ys:[...]}
  if (Array.isArray(line.xs) && Array.isArray(line.ys)) {
    return {
      x: line.xs.map(Number).filter(Number.isFinite),
      y: line.ys.map(Number).filter(Number.isFinite),
    };
  }

  // Format D: {i1,j1,i2,j2}
  const i1 = Number(line.i1 ?? line.I1 ?? line.x1 ?? line.X1);
  const j1 = Number(line.j1 ?? line.J1 ?? line.y1 ?? line.Y1);
  const i2 = Number(line.i2 ?? line.I2 ?? line.x2 ?? line.X2);
  const j2 = Number(line.j2 ?? line.J2 ?? line.y2 ?? line.Y2);

  if ([i1, j1, i2, j2].every(Number.isFinite)) {
    return {x: [i1, i2], y: [j1, j2]};
  }

  // Format E: GeoJSON-like coordinates
  if (line.geometry && Array.isArray(line.geometry.coordinates)) {
    const xs = [];
    const ys = [];

    for (const coord of line.geometry.coordinates) {
      if (Array.isArray(coord) && coord.length >= 2) {
        const x = Number(coord[0]);
        const y = Number(coord[1]);
        if (Number.isFinite(x) && Number.isFinite(y)) {
          xs.push(x);
          ys.push(y);
        }
      }
    }

    if (xs.length >= 2) return {x: xs, y: ys};
  }

  return null;
}

function buildStreamlineTracesV17(block) {
  const rawLines = extractCurrentStreamlineLinesV17(block);
  const snapshot = getStreamlineTimeLabelV15 ? getStreamlineTimeLabelV15(block) : (block.streamline_time || "Streamlines");

  const traces = [];

  for (let idx = 0; idx < rawLines.length; idx++) {
    const norm = normalizeStreamlineLineV17(rawLines[idx]);
    if (!norm || norm.x.length < 2 || norm.y.length < 2) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: idx === 0 ? `Streamlines - ${snapshot}` : undefined,
      showlegend: idx === 0,
      x: norm.x,
      y: norm.y,
      line: {
        width: 1.4,
      },
      opacity: 0.55,
      hoverinfo: "skip",
    });
  }

  return traces;
}

function debugStreamlinePayloadV17(block) {
  try {
    const lines = extractCurrentStreamlineLinesV17(block);
    console.log("[V17 Streamline Debug]", {
      title: block.title,
      streamline_time: block.streamline_time,
      requested_streamline_time: block.streamline_payload?.requested_streamline_time,
      label: block.streamline_payload?.streamline_snapshot_label,
      files: block.streamline_payload?.selected_streamline_files_order,
      lineCount: lines.length,
      firstLine: lines[0],
    });
  } catch (e) {
    console.warn("[V17 Streamline Debug failed]", e);
  }
}



// ==========================================================
// CELL PROPERTY MAP HARD OVERRIDE V18
// Fully redraw property map + current streamline payload.
// This bypasses older map renderers that may keep final streamlines.
// ==========================================================

function extractCellPropertyPointsV18(payload) {
  payload = payload || {};

  const candidates = [
    payload.cells,
    payload.points,
    payload.data,
    payload.values,
    payload.cell_values,
    payload.layer,
  ];

  for (const c of candidates) {
    if (Array.isArray(c) && c.length) {
      const pts = [];

      for (const item of c) {
        if (!item || typeof item !== "object") continue;

        const i = Number(item.i ?? item.I ?? item.x ?? item.X ?? item.col ?? item.COL);
        const j = Number(item.j ?? item.J ?? item.y ?? item.Y ?? item.row ?? item.ROW);

        const v = Number(
          item.value ??
          item.val ??
          item.z ??
          item.Z ??
          item.property_value ??
          item.mean ??
          item.avg
        );

        if (Number.isFinite(i) && Number.isFinite(j) && Number.isFinite(v)) {
          pts.push({
            i,
            j,
            value: v,
            raw: item,
          });
        }
      }

      if (pts.length) return pts;
    }
  }

  // 2D grid fallback
  if (Array.isArray(payload.grid) && payload.grid.length) {
    const pts = [];
    for (let j = 0; j < payload.grid.length; j++) {
      const row = payload.grid[j];
      if (!Array.isArray(row)) continue;
      for (let i = 0; i < row.length; i++) {
        const v = Number(row[i]);
        if (Number.isFinite(v)) {
          pts.push({i, j, value: v, raw: {}});
        }
      }
    }
    return pts;
  }

  return [];
}

function extractWellsV18(payload) {
  payload = payload || {};
  const wells = payload.wells || payload.well_points || [];
  if (!Array.isArray(wells)) return [];

  return wells
    .map(w => {
      const i = Number(w.i ?? w.I ?? w.x ?? w.X);
      const j = Number(w.j ?? w.J ?? w.y ?? w.Y);
      if (!Number.isFinite(i) || !Number.isFinite(j)) return null;

      return {
        ...w,
        i,
        j,
        well: w.well || w.name || w.WELL || "",
      };
    })
    .filter(Boolean);
}

function extractCurrentStreamlineLinesV18(block) {
  const sp = block?.streamline_payload || {};
  const candidates = [
    sp.lines,
    sp.streamlines,
    sp.data,
    sp.features,
    sp.payload?.lines,
    sp.payload?.streamlines,
  ];

  for (const c of candidates) {
    if (Array.isArray(c) && c.length) return c;
  }

  return [];
}

function normalizeStreamlineLineV18(line) {
  if (!line) return null;

  // {points:[{i,j}, ...]}
  if (Array.isArray(line.points) && line.points.length >= 2) {
    const x = [];
    const y = [];

    for (const p of line.points) {
      const px = Number(p.i ?? p.I ?? p.x ?? p.X);
      const py = Number(p.j ?? p.J ?? p.y ?? p.Y);

      if (Number.isFinite(px) && Number.isFinite(py)) {
        x.push(px);
        y.push(py);
      }
    }

    if (x.length >= 2) return {x, y};
  }

  // {x:[...], y:[...]}
  if (Array.isArray(line.x) && Array.isArray(line.y)) {
    const x = line.x.map(Number);
    const y = line.y.map(Number);
    if (x.length >= 2 && y.length >= 2) return {x, y};
  }

  // {xs:[...], ys:[...]}
  if (Array.isArray(line.xs) && Array.isArray(line.ys)) {
    const x = line.xs.map(Number);
    const y = line.ys.map(Number);
    if (x.length >= 2 && y.length >= 2) return {x, y};
  }

  // {ij:[[i,j], ...]} or {coords:[[x,y], ...]}
  const coordList = line.ij || line.coords || line.coordinates;
  if (Array.isArray(coordList) && coordList.length >= 2) {
    const x = [];
    const y = [];

    for (const c of coordList) {
      if (!Array.isArray(c) || c.length < 2) continue;
      const px = Number(c[0]);
      const py = Number(c[1]);
      if (Number.isFinite(px) && Number.isFinite(py)) {
        x.push(px);
        y.push(py);
      }
    }

    if (x.length >= 2) return {x, y};
  }

  // {i1,j1,i2,j2}
  const i1 = Number(line.i1 ?? line.I1 ?? line.x1 ?? line.X1);
  const j1 = Number(line.j1 ?? line.J1 ?? line.y1 ?? line.Y1);
  const i2 = Number(line.i2 ?? line.I2 ?? line.x2 ?? line.X2);
  const j2 = Number(line.j2 ?? line.J2 ?? line.y2 ?? line.Y2);

  if ([i1, j1, i2, j2].every(Number.isFinite)) {
    return {x: [i1, i2], y: [j1, j2]};
  }

  return null;
}

function getStreamlineSnapshotLabelV18(block) {
  const t =
    block?.streamline_time ||
    block?.streamline_payload?.requested_streamline_time ||
    "auto";

  const labels = {
    initial: "Initial History",
    final: "End of History",
    compare: "Initial vs End of History",
    auto: "Default Snapshot",
  };

  return labels[t] || t;
}

function buildCurrentStreamlineTracesV18(block) {
  const rawLines = extractCurrentStreamlineLinesV18(block);
  const label = getStreamlineSnapshotLabelV18(block);
  const traces = [];

  for (let idx = 0; idx < rawLines.length; idx++) {
    const norm = normalizeStreamlineLineV18(rawLines[idx]);
    if (!norm || norm.x.length < 2 || norm.y.length < 2) continue;

    const cleanX = [];
    const cleanY = [];

    for (let k = 0; k < Math.min(norm.x.length, norm.y.length); k++) {
      const x = Number(norm.x[k]);
      const y = Number(norm.y[k]);

      if (Number.isFinite(x) && Number.isFinite(y)) {
        cleanX.push(x);
        cleanY.push(y);
      }
    }

    if (cleanX.length < 2) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      x: cleanX,
      y: cleanY,
      name: idx === 0 ? `Streamlines - ${label}` : `sl-${idx}`,
      showlegend: idx === 0,
      line: {
        width: 1.6,
      },
      opacity: 0.65,
      hoverinfo: "skip",
    });
  }

  return traces;
}

function renderCellPropertyMap(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive maps require Plotly. Check browser/network access.</div>
    `;
    return;
  }

  const payload = block.payload || block.data || {};
  const pts = extractCellPropertyPointsV18(payload);
  const wells = extractWellsV18(payload);
  const streamlineTraces = buildCurrentStreamlineTracesV18(block);

  const title =
    block.title ||
    payload.label ||
    payload.property_label ||
    payload.requested_property ||
    payload.property ||
    "Property Map";

  const uid = "cellmap_" + Date.now();

  const sp = block.streamline_payload || {};
  console.log("[V18 Cell Map]", {
    title,
    requested_property: block.requested_property || payload.requested_property || payload.property,
    streamline_time: block.streamline_time,
    streamline_payload_time: sp.requested_streamline_time,
    streamline_label: sp.streamline_snapshot_label,
    selected_files: sp.selected_streamline_files_order,
    property_points: pts.length,
    wells: wells.length,
    raw_streamline_lines: extractCurrentStreamlineLinesV18(block).length,
    rendered_streamline_traces: streamlineTraces.length,
    first_streamline: extractCurrentStreamlineLinesV18(block)[0],
  });

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div class="empty-state" style="padding:8px 0">
      Cells: ${pts.length} | Wells: ${wells.length} | Streamline traces: ${streamlineTraces.length}
    </div>
    <div id="${uid}" style="width:100%;height:620px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  if (!pts.length) {
    panel.innerHTML += `
      <div class="empty-state">No cell property points found in the current payload.</div>
      <pre>${escapeHtml(JSON.stringify(payload, null, 2).slice(0, 5000))}</pre>
    `;
    return;
  }

  const traces = [];

  traces.push({
    type: "scattergl",
    mode: "markers",
    name: payload.label || block.requested_property || "Property",
    x: pts.map(p => p.i),
    y: pts.map(p => p.j),
    marker: {
      size: 6,
      color: pts.map(p => p.value),
      colorscale: "Viridis",
      showscale: true,
      colorbar: {
        title: payload.label || block.requested_property || payload.property || "Value",
      },
      opacity: 0.78,
    },
    customdata: pts.map(p => [p.value]),
    hovertemplate:
      "I: %{x}<br>J: %{y}<br>Value: %{customdata[0]:.4f}<extra></extra>",
  });

  if (streamlineTraces.length) {
    traces.push(...streamlineTraces);
  }

  if (wells.length) {
    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: "Wells",
      x: wells.map(w => w.i),
      y: wells.map(w => w.j),
      text: wells.map(w => w.well),
      textposition: "top center",
      marker: {
        size: 11,
        symbol: "circle",
        line: {
          width: 1.5,
          color: "white",
        },
      },
      customdata: wells.map(w => [
        w.well,
        w.overall_score,
        w.water_score,
        w.oil_score,
        w.gas_score,
        w.bhp_score,
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "I: %{x}<br>J: %{y}<br>" +
        "Overall HM: %{customdata[1]:.1f}<br>" +
        "Water HM: %{customdata[2]:.1f}<br>" +
        "Oil HM: %{customdata[3]:.1f}<br>" +
        "Gas HM: %{customdata[4]:.1f}<br>" +
        "BHP HM: %{customdata[5]:.1f}<extra></extra>",
    });
  }

  const xs = pts.map(p => p.i).filter(Number.isFinite);
  const ys = pts.map(p => p.j).filter(Number.isFinite);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: {color: "#d8e5ff"},
    margin: {l: 60, r: 40, t: 35, b: 60},
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.22)",
      range: [Math.min(...xs) - 3, Math.max(...xs) + 3],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.22)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [Math.max(...ys) + 3, Math.min(...ys) - 3],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.15,
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// CELL PROPERTY MAP V20 - forced current-payload renderer
// This renderer is called explicitly by renderVisualResponse.
// It uses only the current block.streamline_payload.
// ==========================================================

function renderCellPropertyMapV20(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive maps require Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || block.data || {};
  const streamlinePayload = block.streamline_payload || {};
  const streamlineLines = streamlinePayload.lines || [];

  const title =
    block.title ||
    payload.label ||
    payload.requested_property ||
    payload.property ||
    "Property Map";

  const requestedProperty =
    block.requested_property ||
    payload.requested_property ||
    payload.property ||
    "unknown";

  const streamlineTime =
    block.streamline_time ||
    streamlinePayload.requested_streamline_time ||
    "auto";

  const snapshotLabel =
    streamlinePayload.streamline_snapshot_label ||
    ({
      initial: "Initial History",
      final: "End of History",
      auto: "Default Snapshot",
      compare: "Initial vs End of History",
    }[streamlineTime] || streamlineTime);

  const selectedFile =
    (streamlinePayload.selected_streamline_files_order || [])[0] || "N/A";

  console.log("[V20 MAP INPUT]", {
    title,
    requestedProperty,
    streamlineTime,
    snapshotLabel,
    selectedFile,
    streamlineLineCount: streamlineLines.length,
    firstLine: streamlineLines[0],
    payloadKeys: Object.keys(payload || {}),
  });

  function getCells(p) {
    const candidates = [
      p.cells,
      p.points,
      p.data,
      p.values,
      p.cell_values,
      p.layer,
    ];

    for (const c of candidates) {
      if (!Array.isArray(c) || !c.length) continue;

      const out = [];

      for (const item of c) {
        if (!item || typeof item !== "object") continue;

        const i = Number(item.i ?? item.I ?? item.x ?? item.X ?? item.col ?? item.COL);
        const j = Number(item.j ?? item.J ?? item.y ?? item.Y ?? item.row ?? item.ROW);
        const value = Number(
          item.value ??
          item.val ??
          item.z ??
          item.Z ??
          item.property_value ??
          item.mean ??
          item.avg
        );

        if (Number.isFinite(i) && Number.isFinite(j) && Number.isFinite(value)) {
          out.push({ i, j, value, raw: item });
        }
      }

      if (out.length) return out;
    }

    return [];
  }

  function getWells(p) {
    const wells = p.wells || p.well_points || [];
    if (!Array.isArray(wells)) return [];

    return wells.map(w => {
      const i = Number(w.i ?? w.I ?? w.x ?? w.X);
      const j = Number(w.j ?? w.J ?? w.y ?? w.Y);
      if (!Number.isFinite(i) || !Number.isFinite(j)) return null;

      return {
        ...w,
        i,
        j,
        well: w.well || w.name || w.WELL || "",
      };
    }).filter(Boolean);
  }

  function normalizeLine(line) {
    if (!line) return null;

    if (Array.isArray(line.points) && line.points.length >= 2) {
      const x = [];
      const y = [];

      for (const p of line.points) {
        const px = Number(p.i ?? p.I ?? p.x ?? p.X);
        const py = Number(p.j ?? p.J ?? p.y ?? p.Y);

        if (Number.isFinite(px) && Number.isFinite(py)) {
          x.push(px);
          y.push(py);
        }
      }

      if (x.length >= 2) return { x, y };
    }

    if (Array.isArray(line.x) && Array.isArray(line.y)) {
      return { x: line.x.map(Number), y: line.y.map(Number) };
    }

    if (Array.isArray(line.xs) && Array.isArray(line.ys)) {
      return { x: line.xs.map(Number), y: line.ys.map(Number) };
    }

    const i1 = Number(line.i1 ?? line.I1 ?? line.x1 ?? line.X1);
    const j1 = Number(line.j1 ?? line.J1 ?? line.y1 ?? line.Y1);
    const i2 = Number(line.i2 ?? line.I2 ?? line.x2 ?? line.X2);
    const j2 = Number(line.j2 ?? line.J2 ?? line.y2 ?? line.Y2);

    if ([i1, j1, i2, j2].every(Number.isFinite)) {
      return { x: [i1, i2], y: [j1, j2] };
    }

    return null;
  }

  const cells = getCells(payload);
  const wells = getWells(payload);

  const uid = "cellmap_v20_" + Date.now() + "_" + Math.floor(Math.random() * 100000);

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div class="empty-state" style="padding:6px 0 10px 0">
      Each point is a well. Color indicates the dominant mismatch family. Hover a well to inspect scores and diagnostic signals.
    </div>
    <div id="${uid}" style="width:100%;height:640px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  if (!cells.length) {
    panel.innerHTML += `
      <div class="empty-state">No cell property points were found in this payload.</div>
      <pre>${escapeHtml(JSON.stringify(payload, null, 2).slice(0, 5000))}</pre>
    `;
    return;
  }

  const traces = [];

  traces.push({
    type: "scattergl",
    mode: "markers",
    name: payload.label || requestedProperty,
    x: cells.map(p => p.i),
    y: cells.map(p => p.j),
    marker: {
      size: 6,
      color: cells.map(p => p.value),
      colorscale: "Viridis",
      showscale: true,
      colorbar: { title: payload.label || requestedProperty },
      opacity: 0.75,
    },
    customdata: cells.map(p => [p.value]),
    hovertemplate: "I: %{x}<br>J: %{y}<br>Value: %{customdata[0]:.4f}<extra></extra>",
  });

  // Streamlines from the CURRENT response only.
  const lineStyle = { width: 2.2, dash: "solid" };

  for (let idx = 0; idx < streamlineLines.length; idx++) {
    const norm = normalizeLine(streamlineLines[idx]);
    if (!norm || !norm.x || !norm.y) continue;

    const x = [];
    const y = [];

    for (let k = 0; k < Math.min(norm.x.length, norm.y.length); k++) {
      const px = Number(norm.x[k]);
      const py = Number(norm.y[k]);

      if (Number.isFinite(px) && Number.isFinite(py)) {
        x.push(px);
        y.push(py);
      }
    }

    if (x.length < 2) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: idx === 0 ? `Streamlines - ${snapshotLabel}` : `sl-${idx}`,
      showlegend: idx === 0,
      x,
      y,
      line: lineStyle,
      opacity: 0.85,
      hoverinfo: "skip",
    });
  }

  if (wells.length) {
    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: "Wells",
      x: wells.map(w => w.i),
      y: wells.map(w => w.j),
      text: wells.map(w => w.well),
      textposition: "top center",
      marker: {
        size: 11,
        symbol: "circle",
        line: { width: 1.5, color: "white" },
      },
      customdata: wells.map(w => [
        w.well,
        w.overall_score,
        w.water_score,
        w.oil_score,
        w.gas_score,
        w.bhp_score,
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "I: %{x}<br>J: %{y}<br>" +
        "Overall HM: %{customdata[1]:.1f}<br>" +
        "Water HM: %{customdata[2]:.1f}<br>" +
        "Oil HM: %{customdata[3]:.1f}<br>" +
        "Gas HM: %{customdata[4]:.1f}<br>" +
        "BHP HM: %{customdata[5]:.1f}<extra></extra>",
    });
  }

  const allX = [];
  const allY = [];

  for (const tr of traces) {
    if (Array.isArray(tr.x)) allX.push(...tr.x.map(Number).filter(Number.isFinite));
    if (Array.isArray(tr.y)) allY.push(...tr.y.map(Number).filter(Number.isFinite));
  }

  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 40, t: 35, b: 70 },
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      range: [minX - 4, maxX + 4],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [maxY + 4, minY - 4],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.16,
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// FORCE CELL MAP ALIAS V21
// Any legacy call to renderCellPropertyMap is redirected to V20.
// ==========================================================
try {
  renderCellPropertyMap = renderCellPropertyMapV20;
  window.renderCellPropertyMap = renderCellPropertyMapV20;
  console.log("[V21] renderCellPropertyMap forced to V20");
} catch (e) {
  console.warn("[V21] Could not force renderCellPropertyMap alias", e);
}



// ==========================================================
// WELL DETAIL CLEANUP V27
// Converts raw diagnostic flags into readable reservoir-engineering text.
// This is UI-only: it does not change scores or calculations.
// ==========================================================

function cleanDiagnosticTextV27(text) {
  if (!text) return text;

  let s = String(text);

  const replacements = {
    "Criticalities": "Key Findings",
    "Recommended Action": "Recommended Next Step",

    "BHP HM is Poor": "Pressure match is weak",
    "BHP HM is Fair": "Pressure match is acceptable but not perfect",
    "BHP HM is Good": "Pressure match is good",

    "Oil HM is Poor": "Oil-rate match is weak",
    "Oil HM is Fair": "Oil-rate match is acceptable but not perfect",
    "Oil HM is Good": "Oil-rate match is good",

    "Water HM is Poor": "Water match is weak",
    "Water HM is Fair": "Water match is acceptable but not perfect",
    "Water HM is Good": "Water match is good",

    "Gas HM is Poor": "Gas match is weak",
    "Gas HM is Fair": "Gas match is acceptable but not perfect",
    "Gas HM is Good": "Gas match is good",

    "Water timing signal: not_applicable_negligible_water.": "Water timing: not relevant because water production is negligible.",
    "Water direction signal: negligible_water_both_sim_and_observed.": "Water direction: no material issue; both observed and simulated water are negligible.",

    "Likely driver: no_material_water_mismatch.": "Likely driver: water is not a material mismatch for this well.",
    "Driver family: no_action_required.": "Driver family: no water-specific tuning required.",

    "no_material_water_mismatch": "water is not a material mismatch",
    "no_action_required": "no water-specific tuning required",
    "not_applicable_negligible_water": "not relevant because water is negligible",
    "negligible_water_both_sim_and_observed": "water is negligible in both observed and simulated profiles",

    "simulated_too_low": "model underpredicts the observed response",
    "simulated_too_high": "model overpredicts the observed response",
    "breakthrough_timing_close": "breakthrough timing is reasonably close",
    "no_breakthrough_detected": "no clear breakthrough is detected",

    "water_mobility_or_local_connectivity": "water mobility or local connectivity",
    "high_swat_but_low_simulated_water_production": "water exists near the well, but the model does not produce it effectively",
  };

  for (const [raw, clean] of Object.entries(replacements)) {
    s = s.replaceAll(raw, clean);
  }

  // Generic underscore cleanup for anything still raw.
  s = s.replace(/\b[a-z]+(?:_[a-z0-9]+){1,}\b/g, function(match) {
    return match.replaceAll("_", " ");
  });

  // Improve score formatting.
  s = s.replace(/\((\d+(?:\.\d+)?)\)\./g, "($1/100).");

  return s;
}

function enhanceWellDetailCardsV27(root = document) {
  const candidates = Array.from(root.querySelectorAll("div, p, li, span"));

  for (const el of candidates) {
    if (!el || !el.childNodes || el.childNodes.length !== 1) continue;

    const node = el.childNodes[0];
    if (!node || node.nodeType !== Node.TEXT_NODE) continue;

    const oldText = node.nodeValue;
    const newText = cleanDiagnosticTextV27(oldText);

    if (newText !== oldText) {
      node.nodeValue = newText;
    }
  }

  // Add small visual styling to headings if present.
  for (const el of candidates) {
    const t = (el.textContent || "").trim();

    if (t === "Key Findings" || t === "Recommended Next Step") {
      el.style.fontWeight = "700";
      el.style.color = "#d8e5ff";
      el.style.marginTop = "10px";
      el.style.marginBottom = "6px";
      el.style.letterSpacing = "0.2px";
    }

    if (t.includes("Pressure match is weak") || t.includes("match is weak")) {
      el.style.color = "#ffb4a8";
    }

    if (t.includes("no material issue") || t.includes("not a material mismatch") || t.includes("no water-specific")) {
      el.style.color = "#9ee6b8";
    }
  }
}

// Observe UI changes after well click and clean the panel automatically.
if (!window.__wellDetailCleanupObserverV27) {
  window.__wellDetailCleanupObserverV27 = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.addedNodes && m.addedNodes.length) {
        enhanceWellDetailCardsV27(document);
        break;
      }
    }
  });

  window.__wellDetailCleanupObserverV27.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => enhanceWellDetailCardsV27(document), 500);
  console.log("[V27] Well detail cleanup active");
}



// ==========================================================
// ACTIONABLE WELL CARD TEXT V28
// Converts generic HM recommendations into prioritized,
// evidence-based guidance. UI-only.
// ==========================================================

function makeWellRecommendationActionableV28(text) {
  if (!text) return text;

  let s = String(text);

  // Main generic sentence currently shown in the card.
  s = s.replaceAll(
    "Review relperm/SATNUM, water contact, aquifer support, fault transmissibility, and non-local connectivity. No strong injector/local TRAN driver was detected.",
    "Do not start with a local TRAN multiplier. The current evidence does not show a strong nearby-injector or local transmissibility-corridor driver. The next useful step is to discriminate whether this is a water-front/timing issue or a broader mobility/region issue: first inspect the water profile together with ΔSWAT around the well, then compare nearby wells with the same early-water signature."
  );

  s = s.replaceAll(
    "Review relperm/SATNUM, water contact, aquifer support, fault transmissibility, and non-local connectivity.",
    "Avoid checking everything at once. First use the profile and maps to decide whether the issue is local or regional. Start with the water profile, ΔSWAT around the well, and similar wells with the same water-timing signature."
  );

  s = s.replaceAll(
    "No strong injector/local TRAN driver was detected.",
    "The tool does not see strong evidence that a nearby injector or a local transmissibility corridor is the main driver."
  );

  s = s.replaceAll(
    "Likely driver: unexplained early or high water.",
    "Likely issue: the model is bringing water too early or too strongly, but the available local evidence does not yet isolate the cause."
  );

  s = s.replaceAll(
    "Driver family: unresolved.",
    "Driver confidence: unresolved. More evidence is needed before choosing a tuning parameter."
  );

  s = s.replaceAll(
    "Water timing signal: early breakthrough.",
    "Water timing: the model shows water breakthrough too early or too strongly."
  );

  return s;
}

function enhanceActionableWellCardsV28(root = document) {
  const candidates = Array.from(root.querySelectorAll("div, p, li, span"));

  for (const el of candidates) {
    if (!el || !el.childNodes || el.childNodes.length !== 1) continue;

    const node = el.childNodes[0];
    if (!node || node.nodeType !== Node.TEXT_NODE) continue;

    const oldText = node.nodeValue;
    const newText = makeWellRecommendationActionableV28(oldText);

    if (newText !== oldText) {
      node.nodeValue = newText;
    }
  }
}

if (!window.__actionableWellCardsObserverV28) {
  window.__actionableWellCardsObserverV28 = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.addedNodes && m.addedNodes.length) {
        enhanceActionableWellCardsV28(document);
        break;
      }
    }
  });

  window.__actionableWellCardsObserverV28.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => enhanceActionableWellCardsV28(document), 500);
  console.log("[V28] Actionable well-card text cleanup active");
}



// ==========================================================
// CLUSTER MAP RENDERER V30
// Interactive spatial mismatch cluster map.
// ==========================================================

function renderClusterMapV30(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive cluster maps require Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || block.data || {};
  const wells = payload.wells || [];
  const title = block.title || "Dominant Mismatch Pattern Map";

  const uid = "cluster_map_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div class="empty-state" style="padding:6px 0 10px 0">
      Each point is a well. Color indicates the dominant mismatch family. Hover a well to inspect scores and diagnostic signals.
    </div>
    <div id="${uid}" style="width:100%;height:640px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  if (!Array.isArray(wells) || !wells.length) {
    panel.innerHTML += `<div class="empty-state">No wells available for cluster map.</div>`;
    return;
  }

  const issueOrder = [
    "Good match",
    "Water issue",
    "Oil issue",
    "Gas issue",
    "BHP issue",
    "Multi-variable issue",
    "Not evaluated",
    "Inactive / excluded",
  ];

  const issueDisplayName = {
    "Good match": "Good match",
    "Water issue": "Water mismatch",
    "Oil issue": "Oil mismatch",
    "Gas issue": "Gas mismatch",
    "BHP issue": "Pressure/BHP mismatch",
    "Multi-variable issue": "Multi-variable mismatch",
    "Not evaluated": "Not evaluated",
    "Inactive / excluded": "Inactive / excluded",
  };

  const traces = [];

  for (const issue of issueOrder) {
    const pts = wells.filter(w => w.issue === issue);
    if (!pts.length) continue;

    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: issueDisplayName[issue] || issue,
      x: pts.map(w => w.i),
      y: pts.map(w => w.j),
      text: pts.map(w => w.well),
      textposition: "top center",
      marker: {
        size: issue === "Good match" ? 11 : 14,
        symbol: issue === "Inactive / excluded" ? "x" : "circle",
        line: {
          width: 1.4,
          color: "white",
        },
      },
      customdata: pts.map(w => [
        w.well,
        w.issue,
        w.issue_score,
        w.overall_score,
        w.oil_score,
        w.water_score,
        w.gas_score,
        w.bhp_score,
        w.water_timing,
        w.water_direction,
        w.delta_swat,
        w.delta_pressure,
        w.tran_percentile,
        w.driver,
        w.driver_family,
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "Dominant issue: %{customdata[1]}<br>" +
        "Dominant issue score: %{customdata[2]:.1f}/100<br>" +
        "Overall HM: %{customdata[3]:.1f}/100<br>" +
        "Oil HM: %{customdata[4]:.1f}/100<br>" +
        "Water HM: %{customdata[5]:.1f}/100<br>" +
        "Gas HM: %{customdata[6]:.1f}/100<br>" +
        "BHP HM: %{customdata[7]:.1f}/100<br>" +
        "Water timing: %{customdata[8]}<br>" +
        "Water direction: %{customdata[9]}<br>" +
        "ΔSWAT: %{customdata[10]:.4f}<br>" +
        "ΔPressure: %{customdata[11]:.1f}<br>" +
        "TRAN percentile: %{customdata[12]:.1f}<br>" +
        "Driver: %{customdata[13]}<br>" +
        "Driver family: %{customdata[14]}<extra></extra>",
    });
  }


  const xs = wells.map(w => Number(w.i)).filter(Number.isFinite);
  const ys = wells.map(w => Number(w.j)).filter(Number.isFinite);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 40, t: 35, b: 70 },
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      range: [Math.min(...xs) - 8, Math.max(...xs) + 8],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [Math.max(...ys) + 8, Math.min(...ys) - 8],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.16,
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// SIMILARITY CLUSTER MAP RENDERER V32
// Renders diagnostic similarity clusters, not only issue categories.
// ==========================================================

function renderSimilarityClusterMapV32(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive cluster maps require Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || block.data || {};
  const wells = payload.wells || [];
  const clusters = payload.clusters || [];
  const title = block.title || "Diagnostic Similarity Cluster Map";

  const uid = "similarity_cluster_map_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div class="empty-state" style="padding:6px 0 10px 0">
      Wells are grouped by similar diagnostic signature: HM scores, mismatch direction/timing, ΔSWAT, pressure depletion, TRAN/PERM/PORO percentiles and spatial proximity.
    </div>
    <div id="${uid}" style="width:100%;height:650px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  if (!Array.isArray(wells) || !wells.length) {
    panel.innerHTML += `<div class="empty-state">No wells available for similarity cluster map.</div>`;
    return;
  }

  const clusterIds = [...new Set(wells.map(w => w.cluster_id))].sort((a, b) => a - b);
  const traces = [];

  for (const cid of clusterIds) {
    const pts = wells.filter(w => w.cluster_id === cid);
    if (!pts.length) continue;

    const label = pts[0].cluster_label || `Cluster ${cid}`;
    const evidence = pts[0].common_evidence || "";

    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: `${label} (${pts.length})`,
      x: pts.map(w => w.i),
      y: pts.map(w => w.j),
      text: pts.map(w => w.well),
      textposition: "top center",
      marker: {
        size: 15,
        symbol: "circle",
        line: {
          width: 1.5,
          color: "white",
        },
      },
      customdata: pts.map(w => [
        w.well,
        w.cluster_label,
        w.common_evidence,
        w.issue,
        w.issue_score,
        w.overall_score,
        w.oil_score,
        w.water_score,
        w.gas_score,
        w.bhp_score,
        w.water_timing,
        w.water_direction,
        w.delta_swat,
        w.delta_pressure,
        w.tran_percentile,
        w.perm_percentile,
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "Similarity cluster: %{customdata[1]}<br>" +
        "Common evidence: %{customdata[2]}<br>" +
        "Dominant issue: %{customdata[3]}<br>" +
        "Issue score: %{customdata[4]:.1f}/100<br>" +
        "Overall HM: %{customdata[5]:.1f}/100<br>" +
        "Oil HM: %{customdata[6]:.1f}/100<br>" +
        "Water HM: %{customdata[7]:.1f}/100<br>" +
        "Gas HM: %{customdata[8]:.1f}/100<br>" +
        "BHP HM: %{customdata[9]:.1f}/100<br>" +
        "Water timing: %{customdata[10]}<br>" +
        "Water direction: %{customdata[11]}<br>" +
        "ΔSWAT: %{customdata[12]:.4f}<br>" +
        "ΔPressure: %{customdata[13]:.1f}<br>" +
        "TRAN percentile: %{customdata[14]:.1f}<br>" +
        "PERM percentile: %{customdata[15]:.1f}<extra></extra>",
    });
  }

  const xs = wells.map(w => Number(w.i)).filter(Number.isFinite);
  const ys = wells.map(w => Number(w.j)).filter(Number.isFinite);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 40, t: 35, b: 85 },
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      range: [Math.min(...xs) - 8, Math.max(...xs) + 8],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [Math.max(...ys) + 8, Math.min(...ys) - 8],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.18,
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// SMART WELL RECOMMENDATION PANEL V40
// Adds pattern-aware recommendations to well click panels.
// ==========================================================

window.__smartWellRecommendationsV40 = null;

async function loadSmartWellRecommendationsV40() {
  if (window.__smartWellRecommendationsV40) return window.__smartWellRecommendationsV40;

  try {
    const res = await fetch("/artifacts/diagnosis/smart_well_recommendations.json?ts=" + Date.now());
    if (!res.ok) throw new Error("smart recommendations not found");
    window.__smartWellRecommendationsV40 = await res.json();
  } catch (e) {
    console.warn("[V40] Smart well recommendations unavailable", e);
    window.__smartWellRecommendationsV40 = {};
  }

  return window.__smartWellRecommendationsV40;
}

function detectWellNameInPanelV40(root = document) {
  const txt = root.innerText || "";
  const m = txt.match(/\bHW[-_\s]?\d+[A-Z]?\b/i);
  if (!m) return null;
  return m[0].toUpperCase().replace(/\s+/, "-").replace("_", "-");
}

function buildSmartWellRecommendationHTMLV40(rec) {
  if (!rec) return "";

  const confidence = rec.smart_confidence || "Medium";

  return `
    <div class="smart-well-card-v40" style="
      margin-top:14px;
      padding:14px;
      border:1px solid rgba(160,190,255,.18);
      border-radius:16px;
      background:rgba(8,18,38,.72);
      box-shadow:0 12px 28px rgba(0,0,0,.22);
    ">
      <div style="font-size:14px;font-weight:800;color:#d8e5ff;margin-bottom:8px;">
        Pattern-aware recommendation
      </div>

      <div style="font-size:12px;color:#9fb3d9;margin-bottom:10px;">
        Confidence: <b style="color:#d8e5ff">${escapeHtml(confidence)}</b>
        ${rec.smart_similar_wells ? ` · Similar wells: <b style="color:#d8e5ff">${escapeHtml(rec.smart_similar_wells)}</b>` : ""}
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">What this means</div>
        <div style="color:#c7d7f2;line-height:1.45">${escapeHtml(rec.smart_key_findings || "")}</div>
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Pattern context</div>
        <div style="color:#c7d7f2;line-height:1.45">${escapeHtml(rec.smart_pattern_context || "")}</div>
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Evidence used</div>
        <div style="color:#c7d7f2;line-height:1.45">${escapeHtml(rec.smart_local_evidence || "")}</div>
      </div>

      <div>
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Recommended action</div>
        <div style="color:#bfe7c8;line-height:1.45">${escapeHtml(rec.smart_recommended_action || "")}</div>
      </div>
    </div>
  `;
}

async function injectSmartWellRecommendationV40() {
  const recs = await loadSmartWellRecommendationsV40();
  const well = detectWellNameInPanelV40(document);

  if (!well || !recs || !recs[well]) return;

  const existing = document.querySelector(".smart-well-card-v40");
  if (existing) existing.remove();

  // Try to place in the right-side well detail panel if possible.
  const candidates = Array.from(document.querySelectorAll("div"))
    .filter(el => {
      const t = el.innerText || "";
      return t.includes(well) && (
        t.includes("Recommended") ||
        t.includes("Key Findings") ||
        t.includes("Criticalities") ||
        t.includes("Water match") ||
        t.includes("BHP")
      );
    });

  const target = candidates[candidates.length - 1];

  if (!target) return;

  target.insertAdjacentHTML("beforeend", buildSmartWellRecommendationHTMLV40(recs[well]));
}

if (!window.__smartWellRecommendationObserverV40) {
  window.__smartWellRecommendationObserverV40 = new MutationObserver(() => {
    clearTimeout(window.__smartWellRecommendationTimerV40);
    window.__smartWellRecommendationTimerV40 = setTimeout(() => {
      injectSmartWellRecommendationV40();
    }, 250);
  });

  window.__smartWellRecommendationObserverV40.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => injectSmartWellRecommendationV40(), 800);
  console.log("[V40] Smart well recommendation panel active");
}



// ==========================================================
// SMART WELL PANEL REPLACEMENT V41
// Replaces generic well recommended action with pattern-aware recommendation.
// ==========================================================

window.__smartWellRecommendationsV41 = null;

async function loadSmartWellRecommendationsV41() {
  if (window.__smartWellRecommendationsV41) return window.__smartWellRecommendationsV41;

  try {
    const res = await fetch("/api/smart-well-recommendations?ts=" + Date.now());
    const data = await res.json();
    window.__smartWellRecommendationsV41 = data.recommendations || {};
  } catch (e) {
    console.warn("[V41] Could not load smart well recommendations", e);
    window.__smartWellRecommendationsV41 = {};
  }

  return window.__smartWellRecommendationsV41;
}

function normalizeWellNameV41(well) {
  if (!well) return null;
  const m = String(well).toUpperCase().match(/\bHW[-_\s]?(\d+[A-Z]?)\b/);
  if (!m) return null;
  return `HW-${m[1]}`;
}

function findSelectedWellV41() {
  const txt = document.body.innerText || "";
  const matches = Array.from(txt.matchAll(/\bHW[-_\s]?\d+[A-Z]?\b/gi)).map(m => normalizeWellNameV41(m[0]));
  if (!matches.length) return null;

  // Prefer wells appearing near a well detail panel.
  const candidates = Array.from(document.querySelectorAll("div"))
    .filter(el => {
      const t = el.innerText || "";
      return /\bHW[-_\s]?\d+[A-Z]?\b/i.test(t) &&
        (
          t.includes("Key Findings") ||
          t.includes("Recommended Next Step") ||
          t.includes("Criticalities") ||
          t.includes("Water match") ||
          t.includes("Pressure match")
        );
    });

  if (candidates.length) {
    const t = candidates[candidates.length - 1].innerText || "";
    const m = t.match(/\bHW[-_\s]?\d+[A-Z]?\b/i);
    if (m) return normalizeWellNameV41(m[0]);
  }

  return matches[matches.length - 1];
}

function smartRecommendationHTMLV41(rec) {
  const similar = rec.smart_similar_wells || "";
  const confidence = rec.smart_confidence || "Medium";

  return `
    <div class="smart-well-recommendation-v41" style="
      margin-top:12px;
      padding:14px;
      border-radius:16px;
      border:1px solid rgba(120,180,255,.22);
      background:linear-gradient(180deg, rgba(12,27,55,.92), rgba(8,18,38,.92));
      box-shadow:0 12px 28px rgba(0,0,0,.25);
    ">
      <div style="font-size:14px;font-weight:800;color:#e8f1ff;margin-bottom:4px;">
        Pattern-Aware Recommendation
      </div>

      <div style="font-size:12px;color:#9fb3d9;margin-bottom:10px;">
        Confidence: <b style="color:#e8f1ff">${escapeHtml(confidence)}</b>
        ${similar ? ` · Similar wells: <b style="color:#e8f1ff">${escapeHtml(similar)}</b>` : ""}
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Interpretation</div>
        <div style="color:#c7d7f2;line-height:1.45">
          ${escapeHtml(rec.smart_key_findings || "")}
        </div>
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Pattern Context</div>
        <div style="color:#c7d7f2;line-height:1.45">
          ${escapeHtml(rec.smart_pattern_context || "")}
        </div>
      </div>

      <div style="margin-bottom:10px;">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Evidence Used</div>
        <div style="color:#c7d7f2;line-height:1.45">
          ${escapeHtml(rec.smart_local_evidence || "")}
        </div>
      </div>

      <div>
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:4px;">Action</div>
        <div style="color:#bfe7c8;line-height:1.45">
          ${escapeHtml(rec.smart_recommended_action || "")}
        </div>
      </div>

      <div class="tran-corridor-export-embedded-v46" style="
        margin-top:14px;
        padding-top:12px;
        border-top:1px solid rgba(160,190,255,.16);
      ">
        <div style="font-weight:700;color:#d8e5ff;margin-bottom:6px;">Candidate model edit</div>
        <div class="tran-corridor-status-v46" style="color:#9fb3d9;line-height:1.45;margin-bottom:10px;">
          Export an IXF only if the agent confirms that a TRAN corridor edit is defensible for this well.
        </div>
        <button class="exportTranCorridorBtnV46" style="
          cursor:pointer;
          border:1px solid rgba(130,190,255,.35);
          background:rgba(30,80,150,.55);
          color:#e8f1ff;
          border-radius:12px;
          padding:8px 12px;
          font-weight:700;
        ">
          Evaluate / Export IXF
        </button>
        <div style="font-size:11px;color:#9fb3d9;margin-top:8px;">
          The include is a first-trial HM candidate and must be reviewed before simulation.
        </div>
      </div>
    </div>
  `;
}

function findWellDetailPanelV41(well) {
  const panels = Array.from(document.querySelectorAll("div"))
    .filter(el => {
      const t = el.innerText || "";
      return t.includes(well) || (
        t.includes("Key Findings") &&
        t.includes("Recommended Next Step")
      );
    })
    .filter(el => {
      const t = el.innerText || "";
      return (
        t.includes("Key Findings") ||
        t.includes("Recommended Next Step") ||
        t.includes("Water match") ||
        t.includes("Pressure match")
      );
    });

  if (!panels.length) return null;

  // Pick the smallest relevant panel, not the whole page.
  panels.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);
  return panels[0];
}

async function applySmartWellRecommendationV41() {
  const recs = await loadSmartWellRecommendationsV41();
  const well = findSelectedWellV41();

  if (!well || !recs || !recs[well]) return;

  const panel = findWellDetailPanelV41(well);
  if (!panel) return;

  const old = panel.querySelector(".smart-well-recommendation-v41");
  if (old) old.remove();

  // Make the original generic recommendation less prominent.
  const children = Array.from(panel.querySelectorAll("div, p, span, li"));
  for (const el of children) {
    const t = (el.innerText || "").trim();

    if (
      t.includes("First review the relevant water relative permeability") ||
      t.includes("Review relperm/SATNUM") ||
      t.includes("Avoid using PI multiplier") ||
      t.includes("Do not start with a local TRAN multiplier")
    ) {
      el.style.opacity = "0.38";
      el.style.fontSize = "11px";
      el.style.marginTop = "8px";
      el.title = "Raw diagnostic recommendation replaced by pattern-aware recommendation above.";
    }
  }

  // Insert smart card before the old Recommended Next Step text if possible.
  const recommendedNode = children.find(el => (el.innerText || "").trim() === "Recommended Next Step");
  if (recommendedNode && recommendedNode.parentElement) {
    recommendedNode.parentElement.insertAdjacentHTML("afterend", smartRecommendationHTMLV41(recs[well]));
  } else {
    panel.insertAdjacentHTML("beforeend", smartRecommendationHTMLV41(recs[well]));
  }

  console.log("[V41] Smart recommendation applied for", well, recs[well]);
}

if (!window.__smartWellRecommendationObserverV41) {
  window.__smartWellRecommendationObserverV41 = new MutationObserver(() => {
    clearTimeout(window.__smartWellRecommendationTimerV41);
    window.__smartWellRecommendationTimerV41 = setTimeout(() => {
      applySmartWellRecommendationV41();
    }, 300);
  });

  window.__smartWellRecommendationObserverV41.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => applySmartWellRecommendationV41(), 1000);
  console.log("[V41] Smart well recommendation replacement active");
}



// ==========================================================
// SMART WELL PANEL DEDUPLICATION V42
// Prevents repeated Pattern-Aware Recommendation boxes.
// ==========================================================

window.__smartWellRecommendationApplyingV42 = false;
window.__lastSmartWellAppliedV42 = null;

function removeDuplicateSmartWellCardsV42() {
  const cards = Array.from(document.querySelectorAll(
    ".smart-well-recommendation-v41, .smart-well-card-v40"
  ));

  if (cards.length <= 1) return;

  // Keep only the first visible card, remove all later duplicates.
  for (let i = 1; i < cards.length; i++) {
    cards[i].remove();
  }
}

async function applySmartWellRecommendationV42() {
  if (window.__smartWellRecommendationApplyingV42) return;

  window.__smartWellRecommendationApplyingV42 = true;

  try {
    const recs = await loadSmartWellRecommendationsV41();
    const well = findSelectedWellV41();

    if (!well || !recs || !recs[well]) {
      removeDuplicateSmartWellCardsV42();
      return;
    }

    const panel = findWellDetailPanelV41(well);
    if (!panel) {
      removeDuplicateSmartWellCardsV42();
      return;
    }

    // If this panel already has the smart card for this well, do not add another one.
    const existingCards = Array.from(panel.querySelectorAll(".smart-well-recommendation-v41"));
    if (existingCards.length > 0) {
      // Keep only one card inside the panel.
      for (let i = 1; i < existingCards.length; i++) {
        existingCards[i].remove();
      }
      removeDuplicateSmartWellCardsV42();
      return;
    }

    // Remove cards elsewhere before inserting a fresh one.
    document.querySelectorAll(".smart-well-recommendation-v41, .smart-well-card-v40")
      .forEach(el => el.remove());

    // Make old generic recommendations less prominent, but do it once.
    if (!panel.dataset.smartRawDimmedV42) {
      const children = Array.from(panel.querySelectorAll("div, p, span, li"));

      for (const el of children) {
        const t = (el.innerText || "").trim();

        if (
          t.includes("First review the relevant water relative permeability") ||
          t.includes("Review relperm/SATNUM") ||
          t.includes("Avoid using PI multiplier") ||
          t.includes("Do not start with a local TRAN multiplier") ||
          t.includes("first inspect the water profile together with ΔSWAT")
        ) {
          el.style.opacity = "0.38";
          el.style.fontSize = "11px";
          el.style.marginTop = "8px";
          el.title = "Raw diagnostic recommendation replaced by pattern-aware recommendation.";
        }
      }

      panel.dataset.smartRawDimmedV42 = "true";
    }

    const children = Array.from(panel.querySelectorAll("div, p, span, li"));
    const recommendedNode = children.find(el => (el.innerText || "").trim() === "Recommended Next Step");

    if (recommendedNode && recommendedNode.parentElement) {
      recommendedNode.parentElement.insertAdjacentHTML(
        "afterend",
        smartRecommendationHTMLV41(recs[well])
      );
    } else {
      panel.insertAdjacentHTML("beforeend", smartRecommendationHTMLV41(recs[well]));
    }

    panel.dataset.smartWellV42 = well;
    window.__lastSmartWellAppliedV42 = well;

    removeDuplicateSmartWellCardsV42();

    console.log("[V42] Smart recommendation applied once for", well);

  } finally {
    setTimeout(() => {
      window.__smartWellRecommendationApplyingV42 = false;
    }, 500);
  }
}

// Disable older observers if present.
try {
  if (window.__smartWellRecommendationObserverV40) {
    window.__smartWellRecommendationObserverV40.disconnect();
    window.__smartWellRecommendationObserverV40 = null;
  }
} catch (e) {}

try {
  if (window.__smartWellRecommendationObserverV41) {
    window.__smartWellRecommendationObserverV41.disconnect();
    window.__smartWellRecommendationObserverV41 = null;
  }
} catch (e) {}

// Install clean observer.
if (!window.__smartWellRecommendationObserverV42) {
  window.__smartWellRecommendationObserverV42 = new MutationObserver(() => {
    if (window.__smartWellRecommendationApplyingV42) return;

    clearTimeout(window.__smartWellRecommendationTimerV42);
    window.__smartWellRecommendationTimerV42 = setTimeout(() => {
      applySmartWellRecommendationV42();
    }, 600);
  });

  window.__smartWellRecommendationObserverV42.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => applySmartWellRecommendationV42(), 1200);
  console.log("[V42] Smart well recommendation deduplicated observer active");
}



// ==========================================================
// HIDE RAW WELL RECOMMENDATION V43
// Keeps Key Findings, removes the old generic Recommended Next Step block.
// ==========================================================

function hideRawRecommendedNextStepV43(panel) {
  if (!panel) return;

  const nodes = Array.from(panel.querySelectorAll("div, p, span, li"));

  for (let i = 0; i < nodes.length; i++) {
    const t = (nodes[i].innerText || "").trim();

    if (t === "Recommended Next Step") {
      nodes[i].style.display = "none";

      // Hide following generic recommendation text until the smart card starts.
      for (let j = i + 1; j < Math.min(nodes.length, i + 8); j++) {
        const tj = (nodes[j].innerText || "").trim();

        if (
          tj.includes("Pattern-Aware Recommendation") ||
          nodes[j].classList.contains("smart-well-recommendation-v41")
        ) {
          break;
        }

        if (
          tj.includes("Do not start with a local TRAN multiplier") ||
          tj.includes("Review relperm/SATNUM") ||
          tj.includes("First review the relevant water relative permeability") ||
          tj.includes("High SWAT is present") ||
          tj.includes("Avoid using PI multiplier") ||
          tj.length > 80
        ) {
          nodes[j].style.display = "none";
        }
      }
    }
  }
}

// Wrap V42 apply function if present.
if (typeof applySmartWellRecommendationV42 === "function" && !window.__hideRawRecommendationWrappedV43) {
  const __oldApplySmartWellRecommendationV42 = applySmartWellRecommendationV42;

  applySmartWellRecommendationV42 = async function() {
    await __oldApplySmartWellRecommendationV42();

    const well = findSelectedWellV41 ? findSelectedWellV41() : null;
    const panel = well && findWellDetailPanelV41 ? findWellDetailPanelV41(well) : null;
    hideRawRecommendedNextStepV43(panel);
  };

  window.__hideRawRecommendationWrappedV43 = true;
  console.log("[V43] Raw Recommended Next Step will be hidden after smart recommendation insertion");
}

// Also run periodically once after DOM changes.
if (!window.__hideRawRecommendationObserverV43) {
  window.__hideRawRecommendationObserverV43 = new MutationObserver(() => {
    clearTimeout(window.__hideRawRecommendationTimerV43);
    window.__hideRawRecommendationTimerV43 = setTimeout(() => {
      const well = findSelectedWellV41 ? findSelectedWellV41() : null;
      const panel = well && findWellDetailPanelV41 ? findWellDetailPanelV41(well) : null;
      hideRawRecommendedNextStepV43(panel);
    }, 400);
  });

  window.__hideRawRecommendationObserverV43.observe(document.body, {
    childList: true,
    subtree: true,
  });
}



// ==========================================================
// TRAN CORRIDOR EXPORT BUTTON V44
// Adds IXF export button only when backend considers TRAN corridor edit eligible.
// ==========================================================

async function attachTranCorridorExportButtonV44() {
  const well = findSelectedWellV41 ? findSelectedWellV41() : null;
  if (!well) return;

  const card = document.querySelector(".smart-well-recommendation-v41");
  if (!card) return;

  if (card.querySelector(".tran-corridor-export-v44")) return;

  let candidate = null;

  try {
    const res = await fetch(`/api/tran-corridor-candidate/${encodeURIComponent(well)}?ts=${Date.now()}`);
    candidate = await res.json();
  } catch (e) {
    console.warn("[V44] Could not evaluate TRAN corridor candidate", e);
    return;
  }

  if (!candidate || !candidate.eligible) {
    return;
  }

  const btnHtml = `
    <div class="tran-corridor-export-v44" style="
      margin-top:14px;
      padding-top:12px;
      border-top:1px solid rgba(160,190,255,.16);
    ">
      <div style="font-weight:700;color:#d8e5ff;margin-bottom:6px;">Candidate model edit</div>
      <div style="color:#c7d7f2;line-height:1.45;margin-bottom:10px;">
        The agent identified a plausible TRAN corridor candidate for this well.
        Suggested multiplier: <b>${escapeHtml(String(candidate.multiplier || ""))}</b>.
        Candidate cells: <b>${escapeHtml(String(candidate.cell_count || ""))}</b>.
      </div>
      <button id="exportTranCorridorBtnV44" style="
        cursor:pointer;
        border:1px solid rgba(130,190,255,.35);
        background:rgba(30,80,150,.55);
        color:#e8f1ff;
        border-radius:12px;
        padding:8px 12px;
        font-weight:700;
      ">
        Export candidate IXF
      </button>
      <div style="font-size:11px;color:#9fb3d9;margin-top:8px;">
        Review the include before running. This is a first-trial HM candidate, not an automatic final tuning.
      </div>
    </div>
  `;

  card.insertAdjacentHTML("beforeend", btnHtml);

  const btn = card.querySelector("#exportTranCorridorBtnV44");

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerText = "Generating IXF...";

    try {
      const res = await fetch(`/api/export-tran-corridor-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
      const data = await res.json();

      if (!data.ok || !data.content) {
        alert(data.message || "Could not generate IXF.");
        btn.disabled = false;
        btn.innerText = "Export candidate IXF";
        return;
      }

      const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename || `TRAN_CORRIDOR_${well}.ixf`;
      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(url);

      btn.innerText = "IXF exported";
    } catch (e) {
      console.error("[V44] IXF export failed", e);
      alert("IXF export failed. Check console/logs.");
      btn.disabled = false;
      btn.innerText = "Export candidate IXF";
    }
  });
}

if (!window.__tranCorridorExportObserverV44) {
  window.__tranCorridorExportObserverV44 = new MutationObserver(() => {
    clearTimeout(window.__tranCorridorExportTimerV44);
    window.__tranCorridorExportTimerV44 = setTimeout(() => {
      attachTranCorridorExportButtonV44();
    }, 700);
  });

  window.__tranCorridorExportObserverV44.observe(document.body, {
    childList: true,
    subtree: true,
  });

  setTimeout(() => attachTranCorridorExportButtonV44(), 1500);
  console.log("[V44] TRAN corridor export button active");
}



// ==========================================================
// DISABLE FLOATING TRAN BUTTON OBSERVERS V46
// Button is now embedded directly in the smart recommendation card.
// ==========================================================
try {
  if (window.__tranCorridorExportObserverV44) {
    window.__tranCorridorExportObserverV44.disconnect();
    window.__tranCorridorExportObserverV44 = null;
  }
} catch (e) {}

try {
  if (window.__tranCorridorStableObserverV45) {
    window.__tranCorridorStableObserverV45.disconnect();
    window.__tranCorridorStableObserverV45 = null;
  }
} catch (e) {}

console.log("[V46] Floating TRAN corridor observers disabled");



// ==========================================================
// EMBEDDED TRAN CORRIDOR EXPORT HANDLER V46
// Stable button: no mutation add/remove loop.
// ==========================================================

async function handleEmbeddedTranExportV46(button) {
  const well = findSelectedWellV41 ? findSelectedWellV41() : null;
  const card = button.closest(".smart-well-recommendation-v41");
  const status = card ? card.querySelector(".tran-corridor-status-v46") : null;

  if (!well) {
    alert("No selected well detected.");
    return;
  }

  button.disabled = true;
  button.innerText = "Evaluating candidate...";

  try {
    const candidateRes = await fetch(`/api/tran-corridor-candidate/${encodeURIComponent(well)}?ts=${Date.now()}`);
    const candidate = await candidateRes.json();

    if (!candidate || !candidate.eligible) {
      if (status) {
        status.innerHTML = `
          TRAN corridor export is <b>not recommended</b> for ${escapeHtml(well)} as a first action.
          ${candidate && candidate.reasons ? `<br>${escapeHtml(candidate.reasons.join("; "))}` : ""}
        `;
      }
      button.disabled = false;
      button.innerText = "Not eligible for IXF";
      return;
    }

    if (status) {
      status.innerHTML = `
        Eligible candidate for ${escapeHtml(well)}.
        Suggested multiplier: <b>${escapeHtml(String(candidate.multiplier || ""))}</b>.
        Candidate cells: <b>${escapeHtml(String(candidate.cell_count || ""))}</b>.
      `;
    }

    button.innerText = "Generating IXF...";

    const res = await fetch(`/api/export-tran-corridor-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
    const data = await res.json();

    if (!data.ok || !data.content) {
      alert(data.message || "Could not generate IXF.");
      button.disabled = false;
      button.innerText = "Evaluate / Export IXF";
      return;
    }

    const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename || `TRAN_CORRIDOR_${well}.ixf`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);

    button.innerText = "IXF exported";
  } catch (e) {
    console.error("[V46] Embedded IXF export failed", e);
    alert("IXF export failed. Check console/logs.");
    button.disabled = false;
    button.innerText = "Evaluate / Export IXF";
  }
}

if (!window.__embeddedTranExportHandlerV46) {
  document.addEventListener("click", function(e) {
    const btn = e.target.closest(".exportTranCorridorBtnV46");
    if (!btn) return;
    e.preventDefault();
    handleEmbeddedTranExportV46(btn);
  });

  window.__embeddedTranExportHandlerV46 = true;
  console.log("[V46] Embedded TRAN export handler active");
}



// ==========================================================
// TRAN CORRIDOR MAP RENDERER V47
// Shows proposed corridor cells on top of TRAN_H and final streamlines.
// ==========================================================

function normalizeTranCorridorLineV47(line) {
  if (!line) return null;

  if (Array.isArray(line.points) && line.points.length >= 2) {
    const x = [];
    const y = [];

    for (const p of line.points) {
      const px = Number(p.i ?? p.I ?? p.x ?? p.X);
      const py = Number(p.j ?? p.J ?? p.y ?? p.Y);
      if (Number.isFinite(px) && Number.isFinite(py)) {
        x.push(px);
        y.push(py);
      }
    }

    if (x.length >= 2) return { x, y };
  }

  if (Array.isArray(line.x) && Array.isArray(line.y)) {
    return { x: line.x.map(Number), y: line.y.map(Number) };
  }

  return null;
}

function extractTranBaseCellsV47(baseLayer) {
  const candidates = [
    baseLayer?.cells,
    baseLayer?.points,
    baseLayer?.data,
    baseLayer?.values,
    baseLayer?.layer,
  ];

  for (const c of candidates) {
    if (!Array.isArray(c) || !c.length) continue;

    const pts = [];

    for (const item of c) {
      if (!item || typeof item !== "object") continue;

      const i = Number(item.i ?? item.I ?? item.x ?? item.X);
      const j = Number(item.j ?? item.J ?? item.y ?? item.Y);
      const value = Number(item.value ?? item.val ?? item.z ?? item.Z ?? item.property_value ?? item.mean ?? item.avg);

      if (Number.isFinite(i) && Number.isFinite(j) && Number.isFinite(value)) {
        pts.push({ i, j, value });
      }
    }

    if (pts.length) return pts;
  }

  return [];
}

function renderTRANCorridorMapV47(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive corridor map requires Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "Proposed TRAN Corridor";
  const baseLayer = payload.base_layer || {};
  const baseCells = extractTranBaseCellsV47(baseLayer);
  const corridor = payload.corridor_cells || [];
  const streamlines = payload.streamline_payload?.lines || [];
  const candidate = payload.candidate || {};
  const well = payload.well || "";

  const uid = "tran_corridor_map_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div class="empty-state" style="padding:6px 0 10px 0">
      Background: TRAN_H · highlighted cells: proposed corridor · streamlines: end of history.
      Suggested multiplier: <b>${escapeHtml(String(candidate.multiplier || "N/A"))}</b>
      · Candidate cells: <b>${escapeHtml(String(candidate.cell_count || corridor.length || "N/A"))}</b>
    </div>
    <div id="${uid}" style="width:100%;height:650px;border-radius:16px;overflow:hidden;border:1px solid rgba(160,190,255,.14);background:#061022"></div>
  `;

  if (!baseCells.length && !corridor.length) {
    panel.innerHTML += `<div class="empty-state">No TRAN/corridor cells available for this map.</div>`;
    return;
  }

  const traces = [];

  if (baseCells.length) {
    traces.push({
      type: "scattergl",
      mode: "markers",
      name: "TRAN_H",
      x: baseCells.map(p => p.i),
      y: baseCells.map(p => p.j),
      marker: {
        size: 5,
        color: baseCells.map(p => p.value),
        colorscale: "Viridis",
        showscale: true,
        colorbar: { title: "TRAN_H" },
        opacity: 0.55,
      },
      customdata: baseCells.map(p => [p.value]),
      hovertemplate: "I: %{x}<br>J: %{y}<br>TRAN_H: %{customdata[0]:.4f}<extra></extra>",
    });
  }

  for (let idx = 0; idx < streamlines.length; idx++) {
    const norm = normalizeTranCorridorLineV47(streamlines[idx]);
    if (!norm || norm.x.length < 2) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: idx === 0 ? "Final streamlines" : `sl-${idx}`,
      showlegend: idx === 0,
      x: norm.x,
      y: norm.y,
      line: {
        width: 1.1,
      },
      opacity: 0.35,
      hoverinfo: "skip",
    });
  }

  if (corridor.length) {
    traces.push({
      type: "scattergl",
      mode: "markers",
      name: "Proposed TRAN corridor",
      x: corridor.map(p => p.i),
      y: corridor.map(p => p.j),
      marker: {
        size: 11,
        symbol: "square",
        opacity: 0.92,
        line: {
          width: 1.6,
          color: "white",
        },
      },
      hovertemplate: "Candidate corridor cell<br>I: %{x}<br>J: %{y}<extra></extra>",
    });
  }

  const allX = [];
  const allY = [];

  for (const tr of traces) {
    if (Array.isArray(tr.x)) allX.push(...tr.x.map(Number).filter(Number.isFinite));
    if (Array.isArray(tr.y)) allY.push(...tr.y.map(Number).filter(Number.isFinite));
  }

  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 40, t: 35, b: 80 },
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      range: [minX - 6, maxX + 6],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [maxY + 6, minY - 6],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.17,
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// GENERIC PROPERTY MAP RENDERER V49
// Nvidia-style interactive map for single/delta property maps.
// ==========================================================

function extractGenericLayerCellsV49(layer) {
  const candidates = [
    layer?.cells,
    layer?.points,
    layer?.data,
    layer?.values,
    layer?.cell_values,
    layer?.layer,
  ];

  for (const arr of candidates) {
    if (!Array.isArray(arr) || !arr.length) continue;

    const pts = [];

    for (const item of arr) {
      if (!item || typeof item !== "object") continue;

      const i = Number(item.i ?? item.I ?? item.x ?? item.X);
      const j = Number(item.j ?? item.J ?? item.y ?? item.Y);
      const value = Number(item.value ?? item.val ?? item.z ?? item.Z ?? item.property_value ?? item.mean ?? item.avg);

      if (Number.isFinite(i) && Number.isFinite(j) && Number.isFinite(value)) {
        pts.push({ i, j, value, raw: item });
      }
    }

    if (pts.length) return pts;
  }

  return [];
}

function normalizeGenericLineV49(line) {
  if (!line) return null;

  if (Array.isArray(line.points) && line.points.length >= 2) {
    const x = [];
    const y = [];

    for (const p of line.points) {
      const px = Number(p.i ?? p.I ?? p.x ?? p.X);
      const py = Number(p.j ?? p.J ?? p.y ?? p.Y);
      if (Number.isFinite(px) && Number.isFinite(py)) {
        x.push(px);
        y.push(py);
      }
    }

    if (x.length >= 2) return { x, y };
  }

  if (Array.isArray(line.x) && Array.isArray(line.y)) {
    return { x: line.x.map(Number), y: line.y.map(Number) };
  }

  return null;
}

function renderGenericPropertyMapV49(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive maps require Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || {};
  const layer = payload.layer || {};
  const title = block.title || layer.label || "Property Map";
  const operation = payload.operation || layer.operation || "auto";
  const cells = extractGenericLayerCellsV49(layer);
  const wells = layer.wells || payload.wells || [];
  const streamlines = payload.streamline_payload?.lines || [];
  const uid = "generic_property_map_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div id="${uid}" style="
      width:100%;
      height:680px;
      border-radius:18px;
      overflow:hidden;
      border:1px solid rgba(160,190,255,.14);
      background:#061022;
      box-shadow:0 18px 42px rgba(0,0,0,.28);
    "></div>
  `;

  if (!cells.length) {
    panel.innerHTML += `<div class="empty-state">No cells available for this property map.</div>`;
    return;
  }

  const values = cells.map(p => p.value).filter(Number.isFinite);
  const maxAbs = Math.max(...values.map(v => Math.abs(v)), 1e-9);
  const isDelta = operation === "difference" || String(title).includes("Difference") || String(title).includes("Δ");

  const traces = [];

  traces.push({
    type: "scattergl",
    mode: "markers",
    name: layer.label || payload.property || "Property",
    x: cells.map(p => p.i),
    y: cells.map(p => p.j),
    marker: {
      size: 6,
      color: cells.map(p => p.value),
      colorscale: isDelta ? "RdBu" : "Viridis",
      reversescale: isDelta ? true : false,
      cmin: isDelta ? -maxAbs : undefined,
      cmax: isDelta ? maxAbs : undefined,
      showscale: true,
      colorbar: {
        title: {
          text: layer.label || payload.property || "Value",
          side: "right",
        },
        thickness: 14,
        len: 0.78,
        x: 1.02,
      },
      opacity: 0.78,
    },
    customdata: cells.map(p => [
      p.value,
      p.raw?.initial,
      p.raw?.eoh,
    ]),
    hovertemplate:
      "I: %{x}<br>J: %{y}<br>" +
      "Value: %{customdata[0]:.5f}<br>" +
      "Initial: %{customdata[1]:.5f}<br>" +
      "EOH: %{customdata[2]:.5f}<extra></extra>",
  });

  for (let idx = 0; idx < streamlines.length; idx++) {
    const norm = normalizeGenericLineV49(streamlines[idx]);
    if (!norm || norm.x.length < 2) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: idx === 0 ? "Streamlines" : `sl-${idx}`,
      showlegend: idx === 0,
      x: norm.x,
      y: norm.y,
      line: { width: 1.15 },
      opacity: 0.35,
      hoverinfo: "skip",
    });
  }

  if (Array.isArray(wells) && wells.length) {
    const validWells = wells
      .map(w => {
        const i = Number(w.i ?? w.I ?? w.x ?? w.X);
        const j = Number(w.j ?? w.J ?? w.y ?? w.Y);
        if (!Number.isFinite(i) || !Number.isFinite(j)) return null;
        return { ...w, i, j, well: w.well || w.name || w.WELL || "" };
      })
      .filter(Boolean);

    if (validWells.length) {
      traces.push({
        type: "scattergl",
        mode: "markers+text",
        name: "Wells",
        x: validWells.map(w => w.i),
        y: validWells.map(w => w.j),
        text: validWells.map(w => w.well),
        textposition: "top center",
        marker: {
          size: 12,
          symbol: "circle",
          line: { width: 1.6, color: "white" },
        },
        customdata: validWells.map(w => [
          w.well,
          w.overall_score,
          w.water_score,
          w.oil_score,
          w.gas_score,
          w.bhp_score,
        ]),
        hovertemplate:
          "<b>%{customdata[0]}</b><br>" +
          "I: %{x}<br>J: %{y}<br>" +
          "Overall HM: %{customdata[1]:.1f}/100<br>" +
          "Water HM: %{customdata[2]:.1f}/100<br>" +
          "Oil HM: %{customdata[3]:.1f}/100<br>" +
          "Gas HM: %{customdata[4]:.1f}/100<br>" +
          "BHP HM: %{customdata[5]:.1f}/100<extra></extra>",
      });
    }
  }

  const allX = [];
  const allY = [];

  for (const tr of traces) {
    if (Array.isArray(tr.x)) allX.push(...tr.x.map(Number).filter(Number.isFinite));
    if (Array.isArray(tr.y)) allY.push(...tr.y.map(Number).filter(Number.isFinite));
  }

  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 95, t: 35, b: 70 },
    xaxis: {
      title: "I index",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.18)",
      range: [minX - 5, maxX + 5],
    },
    yaxis: {
      title: "J index",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.18)",
      scaleanchor: "x",
      scaleratio: 1,
      range: [maxY + 5, minY - 5],
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.13,
      bgcolor: "rgba(6,16,34,.65)",
    },
    hovermode: "closest",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// PROFILE ENSEMBLE RENDERER V49
// Interactive all-wells profiles with P10/P50/P90 envelopes.
// ==========================================================

function profileVariableUnitV49(variable) {
  const v = String(variable || "").toLowerCase();
  if (v === "water") return "Water / WCT";
  if (v === "oil") return "Oil rate";
  if (v === "gas") return "Gas rate";
  if (v === "bhp") return "BHP / Pressure";
  return variable || "Value";
}

function renderProfileEnsembleV49(block) {
  const panel = document.getElementById("visualPanel");

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `
      <div class="section-title">Plotly not loaded</div>
      <div class="empty-state">Interactive profiles require Plotly.</div>
    `;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "Profile Ensemble";
  const variable = payload.variable || "profile";
  const series = payload.series || [];
  const simPct = payload.sim_percentiles || [];
  const obsPct = payload.obs_percentiles || [];
  const uid = "profile_ensemble_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div id="${uid}" style="
      width:100%;
      height:650px;
      border-radius:18px;
      overflow:hidden;
      border:1px solid rgba(160,190,255,.14);
      background:#061022;
      box-shadow:0 18px 42px rgba(0,0,0,.28);
    "></div>
  `;

  if (!Array.isArray(series) || !series.length) {
    panel.innerHTML += `<div class="empty-state">No profile arrays were found for this ensemble.</div>`;
    return;
  }

  const traces = [];

  // Individual simulated profiles: thin, low opacity.
  for (const s of series) {
    const y = (s.simulated || []).map(Number);
    if (!y.length) continue;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: s.well || "well",
      x: y.map((_, idx) => idx),
      y,
      line: { width: 0.8 },
      opacity: 0.18,
      hovertemplate: `<b>${escapeHtml(s.well || "")}</b><br>Step: %{x}<br>Simulated: %{y:.4f}<extra></extra>`,
      showlegend: false,
    });
  }

  function addPctTrace(rows, key, name, width, dash) {
    const y = rows.map(r => Number(r[key]));
    const x = rows.map(r => Number(r.x));
    const valid = y.some(Number.isFinite);
    if (!valid) return;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name,
      x,
      y,
      line: {
        width,
        dash,
      },
      opacity: 0.98,
      hovertemplate: `${name}<br>Step: %{x}<br>Value: %{y:.4f}<extra></extra>`,
    });
  }

  addPctTrace(simPct, "p10", "Sim P10", 2.4, "dot");
  addPctTrace(simPct, "p50", "Sim P50", 3.8, "solid");
  addPctTrace(simPct, "p90", "Sim P90", 2.4, "dot");

  // Observed percentiles, if present, dashed.
  addPctTrace(obsPct, "p10", "Observed P10", 2.0, "dash");
  addPctTrace(obsPct, "p50", "Observed P50", 3.2, "dash");
  addPctTrace(obsPct, "p90", "Observed P90", 2.0, "dash");

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 70, r: 40, t: 35, b: 70 },
    xaxis: {
      title: "Time step / aligned profile index",
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.18)",
    },
    yaxis: {
      title: profileVariableUnitV49(variable),
      gridcolor: "rgba(160,190,255,.14)",
      zerolinecolor: "rgba(160,190,255,.18)",
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.16,
      bgcolor: "rgba(6,16,34,.65)",
    },
    hovermode: "x unified",
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
  });
}



// ==========================================================
// FORCE GENERIC PROPERTY MAP ROUTING V50
// Ensures generic_property_map blocks are rendered before tables/suggestions.
// ==========================================================

function renderVisualBlockForcedV50(block) {
  if (!block || !block.type) return false;

  if (block.type === "plotly_chart" && typeof renderPlotlyChartBlockV505A === "function") { renderPlotlyChartBlockV505A(block); return true; }

  if (block.type === "generic_property_map") {
    renderGenericPropertyMapV49(block);
    return true;
  }

  if (block.type === "profile_ensemble") {
    renderProfileEnsembleV49(block);
    return true;
  }

  if (block.type === "tran_corridor_map") {
    renderTRANCorridorMapV47(block);
    return true;
  }

  if (block.type === "wct_bias_cluster_map") {
    renderWCTBiasClusterMapV33(block);
    return true;
  }

  if (block.type === "cluster_map") {
    renderSimilarityClusterMapV32(block);
    return true;
  }

  if (block.type === "cell_property_map") {
    renderCellPropertyMapV20(block);
    return true;
  }

  if (block.type === "profile_series") {
    renderProfilePlotV11(block);
    return true;
  }

  if (block.type === "correlation_scatter") {
    renderCorrelationScatterV11(block);
    return true;
  }

  return false;
}



// ==========================================================
// ROBUST GENERIC PROPERTY MAP RENDERER V51
// Overrides previous renderGenericPropertyMapV49 with error-safe implementation.
// ==========================================================

function renderGenericPropertyMapV49(block) {
  const panel = document.getElementById("visualPanel");

  try {
    console.log("[V51] renderGenericPropertyMapV49 called", block);

    if (!panel) {
      console.error("[V51] visualPanel not found");
      return;
    }

    if (typeof Plotly === "undefined") {
      panel.innerHTML = `
        <div class="section-title">Plotly not loaded</div>
        <div class="empty-state">Interactive maps require Plotly.</div>
      `;
      return;
    }

    const payload = block?.payload || {};
    const layer = payload.layer || {};
    const title = block.title || layer.label || "Property Map";
    const operation = payload.operation || layer.operation || "auto";

    let cells = [];

    const cellCandidates = [
      layer.cells,
      layer.points,
      layer.data,
      layer.values,
      layer.cell_values,
      layer.layer,
    ];

    for (const arr of cellCandidates) {
      if (!Array.isArray(arr) || !arr.length) continue;

      cells = arr.map(item => {
        const i = Number(item?.i ?? item?.I ?? item?.x ?? item?.X);
        const j = Number(item?.j ?? item?.J ?? item?.y ?? item?.Y);
        const value = Number(
          item?.value ??
          item?.val ??
          item?.z ??
          item?.Z ??
          item?.property_value ??
          item?.mean ??
          item?.avg
        );

        return {
          i,
          j,
          value,
          initial: Number(item?.initial),
          eoh: Number(item?.eoh),
        };
      }).filter(p =>
        Number.isFinite(p.i) &&
        Number.isFinite(p.j) &&
        Number.isFinite(p.value)
      );

      if (cells.length) break;
    }

    const wellsRaw = layer.wells || payload.wells || [];
    const wells = Array.isArray(wellsRaw) ? wellsRaw.map(w => {
      const i = Number(w?.i ?? w?.I ?? w?.x ?? w?.X);
      const j = Number(w?.j ?? w?.J ?? w?.y ?? w?.Y);
      return {
        well: w?.well || w?.name || w?.WELL || "",
        i,
        j,
        overall_score: Number(w?.overall_score),
        water_score: Number(w?.water_score),
        oil_score: Number(w?.oil_score),
        gas_score: Number(w?.gas_score),
        bhp_score: Number(w?.bhp_score),
      };
    }).filter(w => Number.isFinite(w.i) && Number.isFinite(w.j)) : [];

    const uid = "generic_property_map_v51_" + Date.now();

    panel.innerHTML = `
      <div class="section-title">${escapeHtml(title)}</div>
      <div style="
        color:#9fb3d9;
        font-size:12px;
        margin:4px 0 8px 0;
      ">
        ${operation === "difference" ? "Computed as End of History minus Initial." : ""}
        Cells: <b>${cells.length}</b>${wells.length ? ` · Wells: <b>${wells.length}</b>` : ""}
      </div>
      <div id="${uid}" style="
        width:100%;
        height:690px;
        border-radius:18px;
        overflow:hidden;
        border:1px solid rgba(160,190,255,.14);
        background:#061022;
        box-shadow:0 18px 42px rgba(0,0,0,.28);
      "></div>
    `;

    if (!cells.length) {
      panel.innerHTML += `
        <div class="empty-state">
          No valid cells found in generic_property_map payload.
          Check layer.cells / points / data in backend response.
        </div>
      `;
      return;
    }

    const values = cells.map(p => p.value).filter(Number.isFinite);
    const isDelta =
      operation === "difference" ||
      String(title).toLowerCase().includes("difference") ||
      String(title).includes("Δ") ||
      String(layer.label || "").includes("Δ");

    const maxAbs = Math.max(...values.map(v => Math.abs(v)), 1e-9);
    const traces = [];

    traces.push({
      type: "scattergl",
      mode: "markers",
      name: layer.label || payload.property || "Property",
      x: cells.map(p => p.i),
      y: cells.map(p => p.j),
      marker: {
        size: 6,
        color: cells.map(p => p.value),
        colorscale: isDelta ? "RdBu" : "Viridis",
        reversescale: isDelta ? true : false,
        cmin: isDelta ? -maxAbs : undefined,
        cmax: isDelta ? maxAbs : undefined,
        showscale: true,
        colorbar: {
          title: layer.label || payload.property || "Value",
          thickness: 12,
          len: 0.62,
          x: 1.015,
          y: 0.52,
        },
        opacity: 0.82,
      },
      customdata: cells.map(p => [
        p.value,
        Number.isFinite(p.initial) ? p.initial : null,
        Number.isFinite(p.eoh) ? p.eoh : null,
      ]),
      hovertemplate:
        "I: %{x}<br>J: %{y}<br>" +
        "Value: %{customdata[0]:.5f}<br>" +
        "Initial: %{customdata[1]:.5f}<br>" +
        "EOH: %{customdata[2]:.5f}<extra></extra>",
    });

    if (wells.length) {
      traces.push({
        type: "scattergl",
        mode: "markers+text",
        name: "Wells",
        x: wells.map(w => w.i),
        y: wells.map(w => w.j),
        text: wells.map(w => w.well),
        textposition: "top center",
        marker: {
          size: 12,
          symbol: "circle",
          line: { width: 1.7, color: "white" },
        },
        customdata: wells.map(w => [
          w.well,
          w.overall_score,
          w.water_score,
          w.oil_score,
          w.gas_score,
          w.bhp_score,
        ]),
        hovertemplate:
          "<b>%{customdata[0]}</b><br>" +
          "I: %{x}<br>J: %{y}<br>" +
          "Overall HM: %{customdata[1]:.1f}/100<br>" +
          "Water HM: %{customdata[2]:.1f}/100<br>" +
          "Oil HM: %{customdata[3]:.1f}/100<br>" +
          "Gas HM: %{customdata[4]:.1f}/100<br>" +
          "BHP HM: %{customdata[5]:.1f}/100<extra></extra>",
      });
    }

    const xs = [];
    const ys = [];

    for (const tr of traces) {
      if (Array.isArray(tr.x)) xs.push(...tr.x.map(Number).filter(Number.isFinite));
      if (Array.isArray(tr.y)) ys.push(...tr.y.map(Number).filter(Number.isFinite));
    }

    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const layout = {
      paper_bgcolor: "#061022",
      plot_bgcolor: "#061022",
      font: { color: "#d8e5ff" },
      margin: { l: 62, r: 82, t: 28, b: 68 },
      xaxis: {
        title: "I index",
        gridcolor: "rgba(160,190,255,.13)",
        zerolinecolor: "rgba(160,190,255,.18)",
        range: [minX - 5, maxX + 5],
      },
      yaxis: {
        title: "J index",
        gridcolor: "rgba(160,190,255,.13)",
        zerolinecolor: "rgba(160,190,255,.18)",
        scaleanchor: "x",
        scaleratio: 1,
        range: [maxY + 5, minY - 5],
      },
      legend: {
        orientation: "h",
        x: 0,
        y: -0.12,
        bgcolor: "rgba(6,16,34,.65)",
      },
      hovermode: "closest",
    };

    Plotly.purge(uid);
    Plotly.newPlot(uid, traces, layout, {
      responsive: true,
      displaylogo: false,
      scrollZoom: true,
    });

    console.log("[V51] Generic property map rendered", {
      title,
      cells: cells.length,
      wells: wells.length,
      operation,
      isDelta,
    });

  } catch (err) {
    console.error("[V51] renderGenericPropertyMapV49 failed", err);

    if (panel) {
      panel.innerHTML = `
        <div class="section-title">Generic map rendering failed</div>
        <div class="empty-state">
          ${escapeHtml(String(err && err.stack ? err.stack : err))}
        </div>
      `;
    }
  }
}



// ==========================================================
// ABSOLUTE VISUAL BLOCK AUTO-RENDER V51
// If a response contains visual blocks, render the first supported one.
// ==========================================================

function tryRenderFirstSupportedVisualBlockV51(response) {
  try {
    const blocks = response?.ui_blocks || response?.blocks || response?.visual_blocks || [];
    if (!Array.isArray(blocks) || !blocks.length) return false;

    for (const block of blocks) {
      if (!block || !block.type) continue;

      if (block.type === "plotly_chart" && typeof renderPlotlyChartBlockV505A === "function") { renderPlotlyChartBlockV505A(block); return true; }

  if (block.type === "generic_property_map") {
        renderGenericPropertyMapV49(block);
        return true;
      }

      if (block.type === "profile_ensemble") {
        renderProfileEnsembleV49(block);
        return true;
      }

      if (block.type === "tran_corridor_map") {
        renderTRANCorridorMapV47(block);
        return true;
      }

      if (block.type === "wct_bias_cluster_map") {
        renderWCTBiasClusterMapV33(block);
        return true;
      }

      if (block.type === "cluster_map") {
        renderSimilarityClusterMapV32(block);
        return true;
      }

      if (block.type === "cell_property_map") {
        renderCellPropertyMapV20(block);
        return true;
      }

      if (block.type === "profile_series") {
        renderProfilePlotV11(block);
        return true;
      }
    }

    return false;
  } catch (e) {
    console.error("[V51] tryRenderFirstSupportedVisualBlockV51 failed", e);
    return false;
  }
}



// ==========================================================
// GENERIC VISUAL AUTORENDER HARD FIX V52
// Explicitly renders generic_property_map/profile_ensemble blocks.
// ==========================================================

function forceRenderChatVisualsV52(data) {
  try {
    const blocks = data?.ui_blocks || [];
    console.log("[V52] forceRenderChatVisualsV52 blocks:", blocks.map(b => b.type));

    if (!Array.isArray(blocks) || !blocks.length) return false;

    const preferredOrder = [
      "generic_property_map",
      "profile_ensemble",
      "tran_corridor_map",
      "wct_bias_cluster_map",
      "cluster_map",
      "cell_property_map",
      "profile_series",
      "correlation_scatter",
    ];

    for (const type of preferredOrder) {
      const block = blocks.find(b => b && b.type === type);
      if (!block) continue;

      console.log("[V52] Rendering visual block:", type, block);

      if (type === "generic_property_map") {
        renderGenericPropertyMapV49(block);
        return true;
      }

      if (type === "profile_ensemble") {
        renderProfileEnsembleV49(block);
        return true;
      }

      if (type === "tran_corridor_map") {
        renderTRANCorridorMapV47(block);
        return true;
      }

      if (type === "wct_bias_cluster_map") {
        renderWCTBiasClusterMapV33(block);
        return true;
      }

      if (type === "cluster_map") {
        renderSimilarityClusterMapV32(block);
        return true;
      }

      if (type === "cell_property_map") {
        renderCellPropertyMapV20(block);
        return true;
      }

      if (type === "profile_series") {
        renderProfilePlotV11(block);
        return true;
      }

      if (type === "correlation_scatter") {
        renderCorrelationScatterV11(block);
        return true;
      }
    }

    return false;

  } catch (e) {
    console.error("[V52] forceRenderChatVisualsV52 failed", e);
    const panel = document.getElementById("visualPanel");
    if (panel) {
      panel.innerHTML = `
        <div class="section-title">Visual rendering failed</div>
        <div class="empty-state">${escapeHtml(String(e && e.stack ? e.stack : e))}</div>
      `;
    }
    return false;
  }
}



// ==========================================================
// HM_WELL_MAP_RENDER_FALLBACK_V393
// UI-only fallback for the KPI well map.
// If the main renderer filters out all wells and leaves the map empty,
// this renders all wells with valid I/J coordinates from /api/dashboard/hm-map.
// ==========================================================
(function () {
  const MARK = "HM_WELL_MAP_RENDER_FALLBACK_V393";
  if (window[MARK]) return;
  window[MARK] = true;

  function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[c]));
  }

  function fmt(v, n = 1) {
    const x = Number(v);
    return Number.isFinite(x) ? x.toFixed(n) : "N/A";
  }

  function scoreInfo(w, variable) {
    const v = variable || "overall";
    let score = null;

    if (v === "overall") {
      score = w.overall_score ?? w.score;
    } else {
      score = w[`${v}_score`] ?? w.overall_score ?? w.score;
    }

    score = Number(score);

    if (!Number.isFinite(score)) {
      return {
        score: null,
        klass: w.class || w.overall_class || "N/A",
        color: "#94a3b8"
      };
    }

    if (score >= 80) return { score, klass: "Good", color: "#22c55e" };
    if (score >= 60) return { score, klass: "Fair", color: "#facc15" };
    return { score, klass: "Poor", color: "#ef4444" };
  }

  async function renderFallbackWellDetail(wellName) {
    const panel = document.getElementById("wellInsight");
    if (!panel) return;

    try {
      const r = await fetch("/api/dashboard/well/" + encodeURIComponent(wellName) + "?t=" + Date.now());
      const d = await r.json();
      const data = d.data || d || {};
      const scores = data.scores || {};

      panel.innerHTML = `
        <div class="section-title">${esc(wellName)}</div>
        <div class="empty-state" style="text-align:left">
          <b>Well KPI detail</b><br><br>
          Overall: ${fmt(scores.overall ?? data.overall_score)}<br>
          Oil: ${fmt(scores.oil ?? data.oil_score)}<br>
          Water: ${fmt(scores.water ?? data.water_score)}<br>
          Gas: ${fmt(scores.gas ?? data.gas_score)}<br>
          BHP: ${fmt(scores.bhp ?? data.bhp_score)}<br><br>
          Clicked from HM KPI well map fallback V393.
        </div>
      `;
    } catch (err) {
      panel.innerHTML = `
        <div class="section-title">${esc(wellName)}</div>
        <div class="empty-state">Well selected. Detail endpoint unavailable.</div>
      `;
    }
  }

  async function renderHmWellMapFallbackV393(force = false) {
  /* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */
  if (window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER === true) {
    // V393 fallback renderer intentionally skipped silently.
return;
  }
  /* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */

    const map = document.getElementById("mapCanvas");
    if (!map) return;

    const currentText = map.innerText || "";
    const hasSvg = !!map.querySelector("svg");
    const needsFallback = force || !hasSvg || currentText.includes("No wells available for current filters");

    if (!needsFallback) return;

    const variable = document.getElementById("hmVariable")?.value || "overall";

    let payload = null;
    try {
      const r = await fetch("/api/dashboard/hm-map?t=" + Date.now());
      payload = await r.json();
    } catch (err) {
      console.warn("[V393] Could not load /api/dashboard/hm-map", err);
      return;
    }

    const wells = (payload?.wells || []).filter(w =>
      Number.isFinite(Number(w.i)) &&
      Number.isFinite(Number(w.j))
    );

    if (!wells.length) {
      map.innerHTML = `<div class="empty-state">No wells with valid I/J coordinates.</div>`;
      return;
    }

    const W = 920;
    const H = 600;
    const padL = 70;
    const padR = 40;
    const padT = 75;
    const padB = 65;

    const is = wells.map(w => Number(w.i));
    const js = wells.map(w => Number(w.j));

    const minI = Math.min(...is);
    const maxI = Math.max(...is);
    const minJ = Math.min(...js);
    const maxJ = Math.max(...js);

    const spanI = Math.max(1, maxI - minI);
    const spanJ = Math.max(1, maxJ - minJ);

    function x(i) {
      return padL + ((Number(i) - minI) / spanI) * (W - padL - padR);
    }

    function y(j) {
return H - padB - ((Number(j) - minJ) / spanJ) * (H - padT - padB);
    }

    const points = wells.map(w => {
      const s = scoreInfo(w, variable);
      const cx = x(w.i);
      const cy = y(w.j);
      const name = esc(w.well);
      const scoreLabel = s.score === null ? "N/A" : fmt(s.score);

      return `
        <g class="hm-well-point-v393" data-well-v393="${name}" style="cursor:pointer">
          <circle cx="${cx}" cy="${cy}" r="10"
                  fill="${s.color}"
                  stroke="rgba(255,255,255,0.85)"
                  stroke-width="2">
            <title>${name} | ${variable.toUpperCase()} ${scoreLabel} | ${s.klass}</title>
          </circle>
          <text x="${cx + 13}" y="${cy + 4}"
                fill="#dbeafe"
                font-size="11"
                font-weight="700">${name}</text>
        </g>
      `;
    }).join("");

    map.innerHTML = `
      <svg viewBox="0 0 ${W} ${H}" class="hm-map-svg" role="img">
        <rect x="0" y="0" width="${W}" height="${H}" fill="rgba(3,10,24,0.20)"></rect>

        <text x="${padL}" y="35" fill="#e5f0ff" font-size="18" font-weight="900">
          History Match KPI Well Map
        </text>
        <text x="${padL}" y="58" fill="#9fb2d0" font-size="12">
          Color by ${variable.toUpperCase()} score. Green = Good, Yellow = Fair, Red = Poor. Click a well to inspect detail.
        </text>

        <line x1="${padL}" y1="${H-padB}" x2="${W-padR}" y2="${H-padB}" stroke="rgba(180,210,255,0.25)"></line>
        <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H-padB}" stroke="rgba(180,210,255,0.25)"></line>

        <text x="${W/2}" y="${H-22}" fill="#94a3b8" font-size="12" text-anchor="middle">Grid I</text>
        <text x="22" y="${H/2}" fill="#94a3b8" font-size="12" transform="rotate(-90 22 ${H/2})" text-anchor="middle">Grid J</text>

        ${points}
      </svg>
    `;

    map.querySelectorAll("[data-well-v393]").forEach(el => {
      el.addEventListener("click", () => {
        const well = el.getAttribute("data-well-v393");
        if (well) renderFallbackWellDetail(well);
      });
    });

    console.log("[V393] HM KPI well map fallback rendered", {
      wells: wells.length,
      variable
    });
  }

  window.renderHmWellMapFallbackV393 = renderHmWellMapFallbackV393;

  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => renderHmWellMapFallbackV393(false), 800);
    setTimeout(() => renderHmWellMapFallbackV393(false), 1800);
    setTimeout(() => renderHmWellMapFallbackV393(false), 3500);
  });

  document.addEventListener("change", ev => {
    if (ev.target && ev.target.id === "hmVariable") {
      setTimeout(() => renderHmWellMapFallbackV393(true), 100);
    }
  });

  setTimeout(() => renderHmWellMapFallbackV393(false), 1500);
})();






// ==========================================================
// V423 GENERIC DIAGNOSTIC CLUSTER MAP RENDERER
// Flexible renderer for reservoir diagnostic cluster maps.
// Supports WCT now and is prepared for gas/oil/BHP/pressure
// if future ui_blocks provide the same payload.wells structure.
// ==========================================================

function renderDiagnosticClusterMapV423(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  const payload = (block && (block.payload || block.data)) || {};
  const wells = Array.isArray(payload.wells) ? payload.wells : [];

  const variableRaw = String(
    payload.variable ||
    block?.variable ||
    block?.diagnostic_variable ||
    "water"
  ).toLowerCase();

  const title =
    block?.title ||
    payload.title ||
    (
      variableRaw.includes("gas") ? "Gas Bias Diagnostic Cluster Map" :
      variableRaw.includes("oil") ? "Oil Bias Diagnostic Cluster Map" :
      variableRaw.includes("bhp") || variableRaw.includes("pressure") ? "BHP / Pressure Diagnostic Cluster Map" :
      "WCT Bias Pattern Map"
    );

  function escV423(x) {
    return String(x ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function getScoreV423(w) {
    if (variableRaw.includes("gas")) return Number(w.gas_score ?? w.score ?? w.overall_score ?? 50);
    if (variableRaw.includes("oil")) return Number(w.oil_score ?? w.score ?? w.overall_score ?? 50);
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return Number(w.bhp_score ?? w.pressure_score ?? w.score ?? w.overall_score ?? 50);
    return Number(w.water_score ?? w.wct_score ?? w.score ?? w.overall_score ?? 50);
  }

  function getDirectionV423(w) {
    if (variableRaw.includes("gas")) return w.gas_direction || w.direction || "";
    if (variableRaw.includes("oil")) return w.oil_direction || w.direction || "";
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return w.bhp_direction || w.pressure_direction || w.direction || "";
    return deriveDiagnosticDirectionV503(w);
  }

  function getVariableLabelV423() {
    if (variableRaw.includes("gas")) return "Gas / GOR";
    if (variableRaw.includes("oil")) return "Oil";
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return "BHP / Pressure";
    return "Water / WCT";
  }

  function biasLabelV423(w) {
    return String(
      w.bias ||
      w.cluster ||
      w.bias_label ||
      getDirectionV423(w) ||
      "Unclassified diagnostic pattern"
    );
  }

  function biasColorV423(w) {
    const b = biasLabelV423(w).toLowerCase();

    if (b.includes("under") || b.includes("too low") || b.includes("late") || b.includes("delayed")) return "#ffb000";
    if (b.includes("over") || b.includes("too high") || b.includes("early") || b.includes("excess")) return "#00b4ff";
    if (b.includes("match") || b.includes("close") || b.includes("good")) return "#2ecc71";
    if (b.includes("weak") || b.includes("poor")) return "#ff5757";

    const score = getScoreV423(w);
    if (score < 40) return "#ff5757";
    if (score < 70) return "#ffb000";
    return "#2ecc71";
  }

  if (!wells.length) {
    panel.innerHTML = `
      <div class="section-title">${escV423(title)}</div>
      <div class="empty-state">
        No diagnostic cluster well data available for this view.
      </div>
    `;
    return false;
  }

  const x = wells.map(w => Number(w.i ?? w.I ?? w.x ?? w.X ?? 0));
  const y = wells.map(w => Number(w.j ?? w.J ?? w.y ?? w.Y ?? 0));

  const colors = wells.map(biasColorV423);
  const sizes = wells.map(w => {
    const score = getScoreV423(w);
    const weakness = Math.max(0, 100 - score);
    return Math.max(12, Math.min(32, 10 + weakness / 4));
  });

  const hoverText = wells.map(w => {
    const well = escV423(w.well || w.name || "Unknown well");
    const bias = escV423(biasLabelV423(w));
    const score = Number.isFinite(getScoreV423(w)) ? getScoreV423(w).toFixed(1) : "N/A";
    const overall = w.overall_score != null ? Number(w.overall_score).toFixed(1) : "N/A";
    const water = w.water_score != null ? Number(w.water_score).toFixed(1) : "N/A";
    const oil = w.oil_score != null ? Number(w.oil_score).toFixed(1) : "N/A";
    const gas = w.gas_score != null ? Number(w.gas_score).toFixed(1) : "N/A";
    const bhp = w.bhp_score != null ? Number(w.bhp_score).toFixed(1) : "N/A";
    const direction = escV423(getDirectionV423(w));
    const timing = escV423(w.water_timing || w.timing || "");

    return (
      "<b>" + well + "</b><br>" +
      "Diagnostic variable: " + escV423(getVariableLabelV423()) + "<br>" +
      "Cluster / bias: " + bias + "<br>" +
      "Selected score: " + score + "<br>" +
      "Water / Oil / Gas / BHP: " + water + " / " + oil + " / " + gas + " / " + bhp + "<br>" +
      "Overall HM: " + overall + "<br>" +
      (direction ? "Direction: " + direction + "<br>" : "") +
      (timing ? "Timing: " + timing + "<br>" : "")
    );
  });

  const counts = {};
  wells.forEach(w => {
    const k = biasLabelV423(w);
    counts[k] = (counts[k] || 0) + 1;
  });

  const summaryHtml = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `
      <span style="display:inline-block;margin:4px 8px 4px 0;padding:5px 9px;border:1px solid rgba(255,255,255,.18);border-radius:999px;">
        ${escV423(k)}: <b>${v}</b>
      </span>
    `)
    .join("");

  const weakest = [...wells]
    .sort((a, b) => getScoreV423(a) - getScoreV423(b))
    .slice(0, 8);

  const tableRows = weakest.map(w => `
    <tr>
      <td>${escV423(w.well || w.name || "")}</td>
      <td>${escV423(biasLabelV423(w))}</td>
      <td style="text-align:right;">${Number.isFinite(getScoreV423(w)) ? getScoreV423(w).toFixed(1) : "N/A"}</td>
      <td style="text-align:right;">${w.overall_score != null ? Number(w.overall_score).toFixed(1) : "N/A"}</td>
      <td>${escV423(deriveDiagnosticDirectionV503(w))}</td>
    </tr>
  `).join("");

  const plotId = "diagnosticClusterMapV423_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escV423(title)}</div>

    <div class="empty-state" style="text-align:left;margin-bottom:10px;">
      <b>Diagnostic interpretation:</b>
      this cluster view groups wells by mismatch behaviour for <b>${escV423(getVariableLabelV423())}</b>.
      It should be interpreted together with oil, gas, water and BHP scores to decide whether the likely model-edit direction is connectivity/TRAN, RelPerm, or pressure-support/aquifer behaviour.
      <div style="margin-top:8px;">${summaryHtml}</div>
    </div>

    <div id="${plotId}" style="width:100%;height:560px;"></div>

    <div class="empty-state" style="text-align:left;margin-top:10px;">
      <b>Weakest examples for selected diagnostic variable</b>
      <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:12px;">
        <thead>
          <tr>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Well</th>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Cluster / bias</th>
            <th style="text-align:right;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Score</th>
            <th style="text-align:right;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Overall</th>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Direction</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so the diagnostic cluster map cannot be rendered interactively.</div>';
    }
    return false;
  }

  const trace = {
    type: "scatter",
    mode: "markers+text",
    x,
    y,
    text: wells.map(w => String(w.well || w.name || "")),
    textposition: "top center",
    hovertext: hoverText,
    hoverinfo: "text",
    marker: {
      size: sizes,
      color: colors,
      line: { width: 1.5, color: "#ffffff" },
      opacity: 0.9
    },
    name: getVariableLabelV423() + " diagnostic cluster"
  };

  const layout = {
    title: title,
    xaxis: { title: "Grid I", zeroline: false },
    yaxis: { title: "Grid J", zeroline: false, scaleanchor: "x", scaleratio: 1 },
    margin: { l: 60, r: 25, t: 60, b: 60 },
    height: 560,
    hovermode: "closest",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)"
  };

  const config = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true
  };

  Plotly.newPlot(plotId, [trace], layout, config);
  console.log("[V423] Diagnostic cluster map rendered", {
    variable: variableRaw,
    wells: wells.length,
    plotId
  });

  return true;
}

// Backward-compatible alias expected by existing V33/V52 render paths.
function renderWCTBiasClusterMapV33(block) {
  return renderDiagnosticClusterMapV423(block);
}

window.renderDiagnosticClusterMapV423 = renderDiagnosticClusterMapV423;
window.renderWCTBiasClusterMapV33 = renderWCTBiasClusterMapV33;


// ==========================================================
// V424 DIAGNOSTIC CLUSTER MAP RENDERER
// Visual-only improvement: no Plotly axes, same I/J orientation
// convention as the HM map canvas above: I grows to the right,
// J grows downward on screen.
// ==========================================================

function renderDiagnosticClusterMapV424(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  const payload = (block && (block.payload || block.data)) || {};
  const wells = Array.isArray(payload.wells) ? payload.wells : [];

  const variableRaw = String(payload.variable || block?.variable || "water").toLowerCase();

  const title =
    block?.title ||
    payload.title ||
    (
      variableRaw.includes("gas") ? "Gas Bias Diagnostic Cluster Map" :
      variableRaw.includes("oil") ? "Oil Bias Diagnostic Cluster Map" :
      variableRaw.includes("bhp") || variableRaw.includes("pressure") ? "BHP / Pressure Diagnostic Cluster Map" :
      "WCT Bias Pattern Map"
    );

  function escV424(x) {
    return String(x ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function variableLabelV424() {
    if (variableRaw.includes("gas")) return "Gas / GOR";
    if (variableRaw.includes("oil")) return "Oil";
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return "BHP / Pressure";
    return "Water / WCT";
  }

  function scoreV424(w) {
    if (variableRaw.includes("gas")) return Number(w.gas_score ?? w.score ?? w.overall_score ?? 50);
    if (variableRaw.includes("oil")) return Number(w.oil_score ?? w.score ?? w.overall_score ?? 50);
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return Number(w.bhp_score ?? w.pressure_score ?? w.score ?? w.overall_score ?? 50);
    return Number(w.water_score ?? w.wct_score ?? w.score ?? w.overall_score ?? 50);
  }

  function directionV424(w) {
    if (variableRaw.includes("gas")) return w.gas_direction || w.direction || "";
    if (variableRaw.includes("oil")) return w.oil_direction || w.direction || "";
    if (variableRaw.includes("bhp") || variableRaw.includes("pressure")) return w.bhp_direction || w.pressure_direction || w.direction || "";
    return deriveDiagnosticDirectionV503(w);
  }

  function labelV424(w) {
    return String(w.bias || w.cluster || w.bias_label || directionV424(w) || "Unclassified");
  }

  function colorV424(w) {
    const b = labelV424(w).toLowerCase();

    if (b.includes("under") || b.includes("too low") || b.includes("late") || b.includes("delayed")) return "#ffb000";
    if (b.includes("over") || b.includes("too high") || b.includes("early") || b.includes("excess")) return "#00b4ff";
    if (b.includes("match") || b.includes("close") || b.includes("good")) return "#2ecc71";

    const s = scoreV424(w);
    if (s < 40) return "#ff5757";
    if (s < 70) return "#ffb000";
    return "#2ecc71";
  }

  function getI(w) { return Number(w.i ?? w.I ?? w.x ?? w.X ?? 0); }
  function getJ(w) { return Number(w.j ?? w.J ?? w.y ?? w.Y ?? 0); }

  function collectReferenceWellsV424() {
    const refs = [];

    try {
      const mp = (window.state && window.state.mapPayload) || (typeof state !== "undefined" ? state.mapPayload : null);

      const candidates = [
        mp?.wells,
        mp?.data?.wells,
        mp?.payload?.wells,
        mp?.points,
        mp?.data?.points
      ];

      candidates.forEach(arr => {
        if (Array.isArray(arr)) {
          arr.forEach(w => {
            if (w && (w.i != null || w.I != null || w.x != null || w.X != null) && (w.j != null || w.J != null || w.y != null || w.Y != null)) {
              refs.push(w);
            }
          });
        }
      });
    } catch (e) {}

    return refs;
  }

  const referenceWells = collectReferenceWellsV424();
  const extentWells = [...referenceWells, ...wells].filter(w => Number.isFinite(getI(w)) && Number.isFinite(getJ(w)));

  if (!wells.length || !extentWells.length) {
    panel.innerHTML = `
      <div class="section-title">${escV424(title)}</div>
      <div class="empty-state">No diagnostic cluster well coordinates available for this view.</div>
    `;
    return false;
  }

  const iVals = extentWells.map(getI);
  const jVals = extentWells.map(getJ);

  let iMin = Math.min(...iVals), iMax = Math.max(...iVals);
  let jMin = Math.min(...jVals), jMax = Math.max(...jVals);

  if (iMax === iMin) { iMax += 1; iMin -= 1; }
  if (jMax === jMin) { jMax += 1; jMin -= 1; }

  const counts = {};
  wells.forEach(w => {
    const k = labelV424(w);
    counts[k] = (counts[k] || 0) + 1;
  });

  const summaryHtml = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `
      <span style="display:inline-block;margin:4px 8px 4px 0;padding:5px 9px;border:1px solid rgba(255,255,255,.16);border-radius:999px;background:rgba(255,255,255,.04);">
        ${escV424(k)}: <b>${v}</b>
      </span>
    `)
    .join("");

  const weakest = [...wells].sort((a, b) => scoreV424(a) - scoreV424(b)).slice(0, 8);

  const tableRows = weakest.map(w => `
    <tr>
      <td>${escV424(w.well || w.name || "")}</td>
      <td>${escV424(labelV424(w))}</td>
      <td style="text-align:right;">${Number.isFinite(scoreV424(w)) ? scoreV424(w).toFixed(1) : "N/A"}</td>
      <td style="text-align:right;">${w.overall_score != null ? Number(w.overall_score).toFixed(1) : "N/A"}</td>
      <td>${escV424(deriveDiagnosticDirectionV503(w))}</td>
    </tr>
  `).join("");

  const canvasId = "diagnosticClusterCanvasV424_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escV424(title)}</div>

    <div class="empty-state" style="text-align:left;margin-bottom:10px;">
      <b>Diagnostic interpretation:</b>
      this view groups wells by mismatch behaviour for <b>${escV424(variableLabelV424())}</b>.
      It uses the same visual convention as the HM map: <b>I increases to the right</b>, <b>J increases downward</b>.
      <div style="margin-top:8px;">${summaryHtml}</div>
    </div>

    <div style="position:relative;width:100%;height:520px;border:1px solid rgba(255,255,255,.10);border-radius:14px;background:radial-gradient(circle at 30% 20%, rgba(31,78,121,.18), rgba(5,12,20,.96));overflow:hidden;">
      <canvas id="${canvasId}" style="width:100%;height:100%;display:block;"></canvas>
      <div style="position:absolute;right:12px;top:10px;font-size:11px;opacity:.72;background:rgba(0,0,0,.35);padding:5px 8px;border-radius:999px;">
        I → &nbsp;&nbsp; J ↓
      </div>
    </div>

    <div class="empty-state" style="text-align:left;margin-top:10px;">
      <b>Weakest examples for selected diagnostic variable</b>
      <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:12px;">
        <thead>
          <tr>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Well</th>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Cluster / bias</th>
            <th style="text-align:right;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Score</th>
            <th style="text-align:right;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Overall</th>
            <th style="text-align:left;border-bottom:1px solid rgba(255,255,255,.15);padding:5px;">Direction</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
  `;

  const canvas = document.getElementById(canvasId);
  const box = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.max(800, Math.floor(box.width * dpr));
  canvas.height = Math.max(480, Math.floor(box.height * dpr));

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const W = box.width;
  const H = box.height;
  const pad = 42;

  function project(w) {
    const x = pad + ((getI(w) - iMin) / (iMax - iMin)) * (W - 2 * pad);
    // J grows downward to match the HM map canvas convention.
    const y = pad + ((getJ(w) - jMin) / (jMax - jMin)) * (H - 2 * pad);
    return { x, y };
  }

  // subtle reference grid, no axes
  ctx.save();
  ctx.strokeStyle = "rgba(255,255,255,0.045)";
  ctx.lineWidth = 1;
  for (let k = 1; k < 6; k++) {
    const gx = pad + k * (W - 2 * pad) / 6;
    const gy = pad + k * (H - 2 * pad) / 6;
    ctx.beginPath(); ctx.moveTo(gx, pad); ctx.lineTo(gx, H - pad); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(W - pad, gy); ctx.stroke();
  }
  ctx.restore();

  // background reference wells from HM map, if available
  referenceWells.forEach(w => {
    const p = project(w);
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.16)";
    ctx.fill();
  });

  // diagnostic wells
  wells.forEach(w => {
    const p = project(w);
    const s = scoreV424(w);
    const r = Math.max(8, Math.min(18, 8 + (100 - Math.max(0, Math.min(100, s))) / 8));
    const c = colorV424(w);

    ctx.beginPath();
    ctx.arc(p.x, p.y, r + 3, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.42)";
    ctx.fill();

    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fillStyle = c;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.stroke();

    const name = String(w.well || w.name || "");
    ctx.font = "11px Arial";
    ctx.fillStyle = "rgba(255,255,255,0.92)";
    ctx.textAlign = "center";
    ctx.fillText(name, p.x, p.y - r - 7);
  });

  console.log("[V424] Diagnostic cluster canvas rendered", {
    variable: variableRaw,
    wells: wells.length,
    referenceWells: referenceWells.length,
    iMin, iMax, jMin, jMax
  });

  return true;
}

// Existing code expects this V33 function name.
// Keep it as an alias, but render with the flexible V424 renderer.
function renderWCTBiasClusterMapV33(block) {
  return renderDiagnosticClusterMapV424(block);
}

window.renderDiagnosticClusterMapV424 = renderDiagnosticClusterMapV424;
window.renderWCTBiasClusterMapV33 = renderWCTBiasClusterMapV33;


// ==========================================================
// V425 ROBUST PROFILE SERIES RENDERER
// Fixes water/WWPR/WCT profile blocks that already contain
// dates/simulated/observed arrays but were falling back to static.
// ==========================================================

function renderProfileSeriesRobustV425(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  const data = (block && (block.data || block.payload)) || {};

  const dates = Array.isArray(data.dates) ? data.dates : [];
  const simulated = Array.isArray(data.simulated) ? data.simulated : [];
  const observed = Array.isArray(data.observed) ? data.observed : [];

  const n = Math.min(dates.length, simulated.length, observed.length);

  if (!n) {
    return false;
  }

  const rows = [];
  for (let i = 0; i < n; i++) {
    const d = dates[i];
    const sim = simulated[i];
    const obs = observed[i];

    const simNum = sim === null || sim === undefined || sim === "" ? null : Number(sim);
    const obsNum = obs === null || obs === undefined || obs === "" ? null : Number(obs);

    if (d && (Number.isFinite(simNum) || Number.isFinite(obsNum))) {
      rows.push({
        date: d,
        simulated: Number.isFinite(simNum) ? simNum : null,
        observed: Number.isFinite(obsNum) ? obsNum : null
      });
    }
  }

  if (!rows.length) {
    return false;
  }

  const title = data.title || block.title || "Simulated vs observed profile";
  const well = data.well || "";
  const variable = String(data.variable || "").toLowerCase();

  function labelV425() {
    if (variable.includes("oil")) return "Oil production";
    if (variable.includes("gas")) return "Gas production";
    if (variable.includes("water")) return "Water production";
    if (variable.includes("wct")) return "Water cut";
    if (variable.includes("bhp") || variable.includes("pressure")) return "BHP / Pressure";
    return variable ? variable.toUpperCase() : "Profile";
  }

  function escV425(x) {
    return String(x ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  const plotId = "profileSeriesV425_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escV425(title)}</div>
    <div class="empty-state" style="text-align:left;margin-bottom:10px;">
      <b>${escV425(well)}</b> — ${escV425(labelV425())}. 
      Interactive simulated-vs-observed profile generated from backend arrays.
    </div>
    <div id="${plotId}" style="width:100%;height:560px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so the interactive profile cannot be rendered.</div>';
    }
    return false;
  }

  const x = rows.map(r => r.date);

  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: "Observed",
      x,
      y: rows.map(r => r.observed),
      line: { width: 2 }
    },
    {
      type: "scatter",
      mode: "lines",
      name: "Simulated",
      x,
      y: rows.map(r => r.simulated),
      line: { width: 2 }
    }
  ];

  const layout = {
    title: title,
    xaxis: {
      title: "Date",
      rangeslider: { visible: true }
    },
    yaxis: {
      title: labelV425(),
      zeroline: false
    },
    margin: { l: 70, r: 25, t: 60, b: 70 },
    height: 560,
    hovermode: "x unified",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    legend: { orientation: "h", y: -0.25 }
  };

  const config = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true
  };

  Plotly.newPlot(plotId, traces, layout, config);

  console.log("[V425] Robust profile_series rendered", {
    title,
    variable,
    rows: rows.length,
    dates: dates.length,
    simulated: simulated.length,
    observed: observed.length
  });

  return true;
}

window.renderProfileSeriesRobustV425 = renderProfileSeriesRobustV425;


// V425 fetch hook: after /api/agent-chat-v501 response, render profile_series blocks first.
(function installProfileSeriesHookV425() {
  if (window.__profileSeriesHookV425Installed) return;
  window.__profileSeriesHookV425Installed = true;

  const previousFetch = window.fetch;

  window.fetch = async function(...args) {
    const response = await previousFetch.apply(this, args);

    try {
      const url = String(args[0] || "");
      const method = String((args[1] && args[1].method) || "GET").toUpperCase();

      if (url.includes("/api/agent-chat-v501") && method === "POST") {
        const clone = response.clone();

        clone.json().then(data => {
          const blocks = data && Array.isArray(data.ui_blocks) ? data.ui_blocks : [];
          const profileBlock = blocks.find(b => b && b.type === "profile_series");

          if (profileBlock) {
            setTimeout(() => {
              try {
                renderProfileSeriesRobustV425(profileBlock);
              } catch (e) {
                console.warn("[V425] Robust profile render failed:", e);
              }
            }, 80);
          }
        }).catch(() => {});
      }
    } catch (e) {}

    return response;
  };

  console.log("[V425] profile_series robust render hook active");
})();


// ==========================================================
// V426 DIRECT PROFILE SERIES RENDERER
// Robust direct renderer for profile_series blocks.
// Reads block.data.dates / simulated / observed for oil, gas,
// water, WCT, BHP and pressure without falling back to static.
// ==========================================================

function renderProfileSeriesRobustV426(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  const data = (block && (block.data || block.payload)) || {};

  const dates = Array.isArray(data.dates) ? data.dates : [];
  const simulated = Array.isArray(data.simulated) ? data.simulated : [];
  const observed = Array.isArray(data.observed) ? data.observed : [];

  const n = Math.min(dates.length, simulated.length, observed.length);

  if (!n) {
    console.warn("[V426] Missing arrays", {
      dates: dates.length,
      simulated: simulated.length,
      observed: observed.length,
      block
    });
    return false;
  }

  const rows = [];

  for (let i = 0; i < n; i++) {
    const d = dates[i];
    const simRaw = simulated[i];
    const obsRaw = observed[i];

    const sim = simRaw === null || simRaw === undefined || simRaw === "" ? null : Number(simRaw);
    const obs = obsRaw === null || obsRaw === undefined || obsRaw === "" ? null : Number(obsRaw);

    if (d && (Number.isFinite(sim) || Number.isFinite(obs))) {
      rows.push({
        date: d,
        simulated: Number.isFinite(sim) ? sim : null,
        observed: Number.isFinite(obs) ? obs : null
      });
    }
  }

  if (!rows.length) {
    console.warn("[V426] Arrays present but no finite values", {
      dates: dates.length,
      simulated: simulated.length,
      observed: observed.length,
      block
    });
    return false;
  }

  const variable = String(data.variable || "").toLowerCase();
  const title = data.title || block.title || "Simulated vs observed profile";
  const well = data.well || "";

  function escV426(x) {
    return String(x ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function labelV426() {
    if (variable.includes("oil")) return "Oil production";
    if (variable.includes("gas")) return "Gas production";
    if (variable.includes("water")) return "Water production";
    if (variable.includes("wct")) return "Water cut";
    if (variable.includes("bhp") || variable.includes("pressure")) return "BHP / Pressure";
    return variable ? variable.toUpperCase() : "Profile value";
  }

  const plotId = "profileSeriesV426_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escV426(title)}</div>
    <div class="empty-state" style="text-align:left;margin-bottom:10px;">
      <b>${escV426(well)}</b> — ${escV426(labelV426())}.
      Interactive simulated-vs-observed profile generated from backend arrays.
    </div>
    <div id="${plotId}" style="width:100%;height:560px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so the interactive profile cannot be rendered.</div>';
    }
    return false;
  }

  const x = rows.map(r => r.date);

  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: "Observed",
      x: x,
      y: rows.map(r => r.observed),
      line: { width: 2 },
      connectgaps: false
    },
    {
      type: "scatter",
      mode: "lines",
      name: "Simulated",
      x: x,
      y: rows.map(r => r.simulated),
      line: { width: 2 },
      connectgaps: false
    }
  ];

  const layout = {
    title: title,
    xaxis: {
      title: "Date",
      rangeslider: { visible: true },
      type: "date"
    },
    yaxis: {
      title: labelV426(),
      zeroline: false
    },
    margin: { l: 70, r: 25, t: 60, b: 70 },
    height: 560,
    hovermode: "x unified",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    legend: { orientation: "h", y: -0.25 }
  };

  const config = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true
  };

  Plotly.newPlot(plotId, traces, layout, config);

  console.log("[V426] Direct profile_series renderer used", {
    title,
    variable,
    rows: rows.length,
    dates: dates.length,
    simulated: simulated.length,
    observed: observed.length
  });

  return true;
}

window.renderProfileSeriesRobustV426 = renderProfileSeriesRobustV426;




// ==========================================================
// V502 PLOTLY CHART UI_BLOCK RENDERER
// Used by LangGraph V501 property_distribution responses.
// ==========================================================

function renderPlotlyChartBlockV502(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  if (!block || block.type !== "plotly_chart") return false;

  const title = block.title || "Interactive chart";
  const data = Array.isArray(block.data) ? block.data : [];
  const layout = block.layout || {};
  const config = block.config || {responsive: true, displaylogo: false};

  if (!data.length) return false;

  function escV502(x) {
    return String(x ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  const plotId = "plotlyChartV502_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escV502(title)}</div>
    <div id="${plotId}" style="width:100%;height:560px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so this chart cannot be rendered interactively.</div>';
    }
    return false;
  }

  const finalLayout = Object.assign({
    height: 560,
    margin: {l: 70, r: 30, t: 60, b: 70},
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    hovermode: "closest"
  }, layout);

  Plotly.newPlot(plotId, data, finalLayout, Object.assign({responsive: true, displaylogo: false}, config));

  console.log("[V502] Plotly chart block rendered", {title, traces: data.length});
  return true;
}

window.renderPlotlyChartBlockV502 = renderPlotlyChartBlockV502;

(function installPlotlyChartHookV502() {
  if (window.__plotlyChartHookV502Installed) return;
  window.__plotlyChartHookV502Installed = true;

  const previousFetch = window.fetch;

  window.fetch = async function(...args) {
    const response = await previousFetch.apply(this, args);

    try {
      const url = String(args[0] || "");
      const method = String((args[1] && args[1].method) || "GET").toUpperCase();

      if ((url.includes("/api/agent-chat-v501") || url.includes("/api/agent-chat-v501")) && method === "POST") {
        const clone = response.clone();

        clone.json().then(data => {
          const blocks = data && Array.isArray(data.ui_blocks) ? data.ui_blocks : [];
          const plotlyBlock = blocks.find(b => b && b.type === "plotly_chart");

          if (plotlyBlock) {
            setTimeout(() => {
              try {
                renderPlotlyChartBlockV502(plotlyBlock);
              } catch (e) {
                console.warn("[V502] Plotly chart render failed:", e);
              }
            }, 80);
          }
        }).catch(() => {});
      }
    } catch (e) {}

    return response;
  };

  console.log("[V502] plotly_chart hook active");
})();



// ==========================================================
// V503 WCT DIRECTION FALLBACK
// Fixes "unknown" direction in WCT bias tables when the bias
// label already contains the interpretation.
// ==========================================================

function deriveDiagnosticDirectionV503(w) {
  if (!w) return "";

  const explicit =
    w.water_direction ||
    w.wct_direction ||
    w.direction ||
    w.timing_direction ||
    "";

  if (explicit && String(explicit).toLowerCase() !== "unknown") {
    return explicit;
  }

  const bias = String(w.bias || w.cluster || w.bias_label || "").toLowerCase();
  const timing = String(w.water_timing || w.timing || "").toLowerCase();

  if (bias.includes("underestimates") && bias.includes("late")) {
    return "simulated too low / late water";
  }

  if (bias.includes("underestimates")) {
    return "simulated too low";
  }

  if (bias.includes("overestimates") && bias.includes("early")) {
    return "simulated too high / early water";
  }

  if (bias.includes("overestimates")) {
    return "simulated too high";
  }

  if (timing.includes("late") || timing.includes("delayed")) {
    return "late water";
  }

  if (timing.includes("early")) {
    return "early water";
  }

  if (timing.includes("close")) {
    return "final value close";
  }

  return "not explicitly classified";
}

window.deriveDiagnosticDirectionV503 = deriveDiagnosticDirectionV503;




// ==========================================================
// V505A SAFE GLOBAL UI CLEANUP + ROBUST PLOTLY BLOCK RENDERER
// ASCII-safe version: no problematic pasted unicode chars.
// ==========================================================

function sanitizeTextV505A(x) {
  let s = String(x ?? "");

  const repl = {};
  repl["\u00e2\u2020\u2019"] = "\u2192"; // mojibake arrow
  repl["\u00c2\u00b7"] = "\u00b7";     // mojibake middle dot
  repl["\u00c2\u00b0"] = "\u00b0";
  repl["\u00c2\u00b1"] = "\u00b1";
  repl["\u00e2\u2030\u00a5"] = "\u2265";
  repl["\u00e2\u2030\u00a4"] = "\u2264";
  repl["\u00e2\u20ac\u201c"] = "\u2013";
  repl["\u00e2\u20ac\u201d"] = "\u2014";
  repl["\u00e2\u20ac\u02dc"] = "'";
  repl["\u00e2\u20ac\u2122"] = "'";
  repl["\u00e2\u20ac\u0153"] = '"';
  repl["\u00e2\u20ac\u009d"] = '"';
  repl["\u00c3\u0097"] = "\u00d7";
  repl["\u00c2"] = "";

  for (const k in repl) {
    s = s.split(k).join(repl[k]);
  }

  return s;
}

window.sanitizeTextV505A = sanitizeTextV505A;

function sanitizeObjectTextV505A(obj) {
  if (obj == null) return obj;

  if (typeof obj === "string") return sanitizeTextV505A(obj);

  if (Array.isArray(obj)) {
    return obj.map(sanitizeObjectTextV505A);
  }

  if (typeof obj === "object") {
    for (const k of Object.keys(obj)) {
      obj[k] = sanitizeObjectTextV505A(obj[k]);
    }
  }

  return obj;
}

function cleanPlotlyTraceHoverV505A(trace, layoutTitle) {
  if (!trace || typeof trace !== "object") return trace;

  const title = String(layoutTitle || "").toLowerCase();
  const traceType = String(trace.type || "").toLowerCase();

  const looksLikeMap =
    traceType.includes("heatmap") ||
    title.includes("map") ||
    title.includes("property");

  if (trace.hovertemplate && String(trace.hovertemplate).includes("customdata")) {
    if (traceType.includes("heatmap")) {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{z:.4g}<extra></extra>";
    } else if (looksLikeMap) {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{marker.color:.4g}<extra></extra>";
    } else {
      trace.hovertemplate = "%{x}<br>%{y:.4g}<extra></extra>";
    }
  }

  if (trace.name) trace.name = sanitizeTextV505A(trace.name);
  if (trace.hovertemplate) trace.hovertemplate = sanitizeTextV505A(trace.hovertemplate);

  return trace;
}

function cleanPlotlyBlockV505A(block) {
  if (!block || typeof block !== "object") return block;

  sanitizeObjectTextV505A(block);

  const layout = block.layout || {};
  const layoutTitle =
    typeof layout.title === "string"
      ? layout.title
      : layout.title && layout.title.text
        ? layout.title.text
        : block.title || "";

  if (Array.isArray(block.data)) {
    block.data = block.data.map(t => cleanPlotlyTraceHoverV505A(t, layoutTitle));
  }

  block.layout = layout;
  return block;
}

function renderPlotlyChartBlockV505A(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  if (!block || block.type !== "plotly_chart") return false;

  block = cleanPlotlyBlockV505A(block);

  const title = sanitizeTextV505A(block.title || "Interactive chart");
  const data = Array.isArray(block.data) ? block.data : [];
  const layout = block.layout || {};
  const config = block.config || {};

  if (!data.length) {
    panel.innerHTML = `
      <div class="section-title">${title}</div>
      <div class="empty-state">No chart traces were available for this visual.</div>
    `;
    return false;
  }

  const plotId = "plotlyChartV505A_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${title}</div>
    <div id="${plotId}" style="width:100%;height:${Number(layout.height || 560)}px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so this chart cannot be rendered interactively.</div>';
    }
    return false;
  }

  const finalLayout = Object.assign({
    height: 560,
    margin: {l: 70, r: 30, t: 60, b: 70},
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    hovermode: "closest"
  }, layout);

  Plotly.newPlot(
    plotId,
    data,
    finalLayout,
    Object.assign({responsive: true, displaylogo: false, scrollZoom: true}, config)
  );

  console.log("[V505A] plotly_chart rendered", { title, traces: data.length });
  return true;
}

window.renderPlotlyChartBlockV505A = renderPlotlyChartBlockV505A;

(function installPlotlyCleanupV505A() {
  if (window.__plotlyCleanupV505AInstalled) return;
  window.__plotlyCleanupV505AInstalled = true;

  function patchWhenReady() {
    if (typeof Plotly === "undefined" || !Plotly.newPlot) {
      setTimeout(patchWhenReady, 300);
      return;
    }

    if (Plotly.__newPlotPatchedV505A) return;

    const originalNewPlot = Plotly.newPlot.bind(Plotly);

    Plotly.newPlot = function(div, data, layout, config) {
      try {
        const title =
          typeof layout?.title === "string"
            ? layout.title
            : layout?.title?.text || "";

        if (Array.isArray(data)) {
          data = data.map(t => cleanPlotlyTraceHoverV505A(t, title));
        }

        if (layout) sanitizeObjectTextV505A(layout);
      } catch (e) {}

      return originalNewPlot(div, data, layout, config);
    };

    Plotly.__newPlotPatchedV505A = true;
    console.log("[V505A] Plotly cleanup patch active");
  }

  patchWhenReady();
})();

(function installTextCleanupObserverV505A() {
  if (window.__textCleanupObserverV505AInstalled) return;
  window.__textCleanupObserverV505AInstalled = true;

  function cleanTextNodes(root) {
    if (!root) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];

    while (walker.nextNode()) nodes.push(walker.currentNode);

    for (const node of nodes) {
      const oldText = node.nodeValue;
      const newText = sanitizeTextV505A(oldText);
      if (newText !== oldText) node.nodeValue = newText;
    }
  }

  const observer = new MutationObserver(() => {
    cleanTextNodes(document.getElementById("visualPanel"));
    cleanTextNodes(document.getElementById("chatAnswer"));
    cleanTextNodes(document.getElementById("patternAwareContentV311"));
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });

  setTimeout(() => cleanTextNodes(document.body), 500);

  console.log("[V505A] text cleanup observer active");
})();

(function installPlotlyBlockFetchHookV505A() {
  if (window.__plotlyBlockFetchHookV505AInstalled) return;
  window.__plotlyBlockFetchHookV505AInstalled = true;

  const previousFetch = window.fetch;

  window.fetch = async function(...args) {
    const response = await previousFetch.apply(this, args);

    try {
      const url = String(args[0] || "");
      const method = String((args[1] && args[1].method) || "GET").toUpperCase();

      if ((url.includes("/api/agent-chat-v501") || url.includes("/api/chat-final")) && method === "POST") {
        const clone = response.clone();

        clone.json().then(data => {
          const blocks = data && Array.isArray(data.ui_blocks) ? data.ui_blocks : [];
          const plotlyBlock = blocks.find(b => b && b.type === "plotly_chart");

          if (plotlyBlock) {
            setTimeout(() => {
              try {
                renderPlotlyChartBlockV505A(plotlyBlock);
              } catch (e) {
                console.warn("[V505A] plotly_chart render failed", e);
              }
            }, 180);
          }
        }).catch(() => {});
      }
    } catch (e) {}

    return response;
  };

  console.log("[V505A] plotly_chart fetch hook active");
})();



// ==========================================================
// V507 PLOTLY DARK STYLE + CLEAN MAP HOVER
// Frontend-only visual cleanup.
// ==========================================================

function applyDarkPlotlyLayoutV507(layout, titleFallback) {
  layout = layout || {};

  const titleText =
    typeof layout.title === "string"
      ? layout.title
      : layout.title && layout.title.text
        ? layout.title.text
        : titleFallback || "";

  layout.paper_bgcolor = "rgba(0,0,0,0)";
  layout.plot_bgcolor = "rgba(0,0,0,0)";

  layout.font = Object.assign({
    color: "#ffffff",
    family: "Arial, sans-serif",
    size: 13
  }, layout.font || {});

  layout.title = {
    text: titleText ? "<b>" + String(titleText).replace(/<[^>]*>/g, "") + "</b>" : "",
    font: {
      color: "#ffffff",
      family: "Arial Black, Arial, sans-serif",
      size: 18
    }
  };

  function cleanAxis(axis, fallbackTitle) {
    axis = axis || {};

    const oldTitle =
      typeof axis.title === "string"
        ? axis.title
        : axis.title && axis.title.text
          ? axis.title.text
          : fallbackTitle || "";

    axis.title = {
      text: oldTitle ? "<b>" + String(oldTitle).replace(/<[^>]*>/g, "") + "</b>" : "",
      font: {
        color: "#ffffff",
        family: "Arial Black, Arial, sans-serif",
        size: 14
      }
    };

    axis.tickfont = Object.assign({
      color: "#ffffff",
      family: "Arial Black, Arial, sans-serif",
      size: 12
    }, axis.tickfont || {});

    // Remove internal grid, keep only main axes.
    axis.showgrid = false;
    axis.zeroline = false;
    axis.showline = true;
    axis.linecolor = "#ffffff";
    axis.tickcolor = "#ffffff";
    axis.ticks = "outside";

    return axis;
  }

  layout.xaxis = cleanAxis(layout.xaxis, "X");
  layout.yaxis = cleanAxis(layout.yaxis, "Y");

  if (layout.legend !== false) {
    layout.legend = Object.assign({
      font: {color: "#ffffff"},
      bgcolor: "rgba(0,0,0,0)",
      bordercolor: "rgba(255,255,255,0.15)",
      borderwidth: 0,
      orientation: "h",
      y: -0.25
    }, layout.legend || {});
  }

  return layout;
}

function cleanMapHoverTraceV507(trace, layoutTitle) {
  if (!trace || typeof trace !== "object") return trace;

  const title = String(layoutTitle || "").toLowerCase();
  const type = String(trace.type || "").toLowerCase();

  const looksLikeMap =
    title.includes("map") ||
    title.includes("property") ||
    type.includes("heatmap") ||
    type.includes("contour") ||
    type.includes("scattergl");

  if (looksLikeMap) {
    // Make map hover explicit: I, J, Value.
    if (type.includes("heatmap") || trace.z) {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{z:.5g}<extra></extra>";
    } else {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{marker.color:.5g}<extra></extra>";
    }

    trace.hoverinfo = "skip"; // hovertemplate controls it
  }

  // If any old customdata hover survived, override it.
  if (trace.hovertemplate && String(trace.hovertemplate).toLowerCase().includes("customdata")) {
    if (type.includes("heatmap") || trace.z) {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{z:.5g}<extra></extra>";
    } else {
      trace.hovertemplate = "I: %{x}<br>J: %{y}<br>Value: %{marker.color:.5g}<extra></extra>";
    }
  }

  return trace;
}

function cleanEnsembleHoverV507(data, layout) {
  if (!Array.isArray(data)) return data;

  const title =
    typeof layout?.title === "string"
      ? layout.title
      : layout?.title?.text || "";

  const isEnsemble =
    String(title).toLowerCase().includes("p10") ||
    String(title).toLowerCase().includes("p50") ||
    String(title).toLowerCase().includes("p90") ||
    data.some(t => ["P10", "P50", "P90"].includes(String(t?.name || "")));

  if (!isEnsemble) return data;

  for (const trace of data) {
    const name = String(trace.name || "");

    if (["P10", "P50", "P90"].includes(name)) {
      trace.showlegend = true;
      trace.hovertemplate = name + "<br>Date: %{x}<br>Value: %{y:.5g}<extra></extra>";
      trace.line = Object.assign({width: name === "P50" ? 4 : 3}, trace.line || {});
    } else {
      trace.showlegend = false;
      trace.hoverinfo = "skip";
      trace.hovertemplate = null;
      trace.opacity = trace.opacity == null ? 0.18 : Math.min(Number(trace.opacity) || 0.18, 0.22);
      trace.line = Object.assign({width: 1}, trace.line || {});
    }
  }

  if (layout) {
    layout.hovermode = "closest";
    layout.legend = Object.assign({
      orientation: "h",
      y: -0.25,
      font: {color: "#ffffff"}
    }, layout.legend || {});
  }

  return data;
}

function cleanPlotlyBeforeRenderV507(data, layout) {
  layout = applyDarkPlotlyLayoutV507(layout, "");

  const title =
    typeof layout?.title === "string"
      ? layout.title
      : layout?.title?.text || "";

  if (Array.isArray(data)) {
    data = data.map(t => cleanMapHoverTraceV507(t, title));
    data = cleanEnsembleHoverV507(data, layout);
  }

  return {data, layout};
}

(function installPlotlyStylePatchV507() {
  if (window.__plotlyStylePatchV507Installed) return;
  window.__plotlyStylePatchV507Installed = true;

  function patchWhenReady() {
    if (typeof Plotly === "undefined" || !Plotly.newPlot) {
      setTimeout(patchWhenReady, 300);
      return;
    }

    if (Plotly.__newPlotPatchedV507) return;

    const originalNewPlot = Plotly.newPlot.bind(Plotly);

    Plotly.newPlot = function(div, data, layout, config) {
      try {
        const cleaned = cleanPlotlyBeforeRenderV507(data, layout || {});
        data = cleaned.data;
        layout = cleaned.layout;
      } catch (e) {
        console.warn("[V507] Plotly style cleanup failed", e);
      }

      return originalNewPlot(div, data, layout, config);
    };

    Plotly.__newPlotPatchedV507 = true;
    console.log("[V507] Plotly style/hover patch active");
  }

  patchWhenReady();
})();

// Override V505A plotly renderer if present, with same function name,
// so fetch hooks still call the improved renderer.
function renderPlotlyChartBlockV505A(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  if (!block || block.type !== "plotly_chart") return false;

  const title = block.title || "Interactive chart";
  let data = Array.isArray(block.data) ? block.data : [];
  let layout = block.layout || {};
  const config = block.config || {};

  const cleaned = cleanPlotlyBeforeRenderV507(data, layout);
  data = cleaned.data;
  layout = cleaned.layout;

  const plotId = "plotlyChartV507_" + Date.now();

  panel.innerHTML = `
    <div class="section-title" style="color:#fff;font-weight:800;">${title}</div>
    <div id="${plotId}" style="width:100%;height:${Number(layout.height || 560)}px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so this chart cannot be rendered interactively.</div>';
    }
    return false;
  }

  Plotly.newPlot(
    plotId,
    data,
    layout,
    Object.assign({responsive: true, displaylogo: false, scrollZoom: true}, config)
  );

  console.log("[V507] plotly_chart rendered", {title, traces: data.length});
  return true;
}

window.renderPlotlyChartBlockV505A = renderPlotlyChartBlockV505A;
window.applyDarkPlotlyLayoutV507 = applyDarkPlotlyLayoutV507;
window.cleanMapHoverTraceV507 = cleanMapHoverTraceV507;
window.cleanEnsembleHoverV507 = cleanEnsembleHoverV507;



// ==========================================================
// V508 PLOT UNITS + NO RANGE SLIDER + CLEAN HOVER
// Applies globally before Plotly rendering.
// ==========================================================

function inferYAxisTitleV508(layout, data, titleFallback) {
  const title =
    String(titleFallback || "") + " " +
    String(typeof layout?.title === "string" ? layout.title : layout?.title?.text || "") + " " +
    String(layout?.yaxis?.title?.text || layout?.yaxis?.title || "") + " " +
    (Array.isArray(data) ? data.map(t => String(t?.name || "")).join(" ") : "");

  const s = title.toLowerCase();

  const isCumulative =
    s.includes("cumulative") ||
    s.includes("cum ") ||
    s.includes(" total produced") ||
    s.includes("integrated");

  const isDistribution =
    s.includes("distribution") ||
    s.includes("histogram") ||
    s.includes("hist ");

  const isMap =
    s.includes("map") ||
    s.includes("property");

  if (isDistribution) return "Count";

  if (s.includes("water cut") || s.includes(" wct") || s.includes("wwct")) {
    return "Water cut (-)";
  }

  if (s.includes("bhp") || s.includes("pressure")) {
    return "Pressure (model units)";
  }

  if (s.includes("gas")) {
    return isCumulative ? "Cumulative gas (MSCF)" : "Gas rate (MSCF/d)";
  }

  if (s.includes("water")) {
    return isCumulative ? "Cumulative water (STB)" : "Water rate (STB/d)";
  }

  if (s.includes("oil")) {
    return isCumulative ? "Cumulative oil (STB)" : "Oil rate (STB/d)";
  }

  if (s.includes("poro") || s.includes("porosity")) {
    return isMap ? "Porosity (-)" : "Porosity (-)";
  }

  if (s.includes("perm") || s.includes("permeability")) {
    return isMap ? "Permeability (mD)" : "Permeability (mD)";
  }

  if (s.includes("swat") || s.includes("saturation")) {
    return "Water saturation (-)";
  }

  if (s.includes("tran") || s.includes("transmissibility")) {
    return "Transmissibility (model units)";
  }

  return "Value";
}

function styleAxisV508(axis, titleText) {
  axis = axis || {};

  axis.title = {
    text: "<b>" + String(titleText || "").replace(/<[^>]*>/g, "") + "</b>",
    font: {
      color: "#ffffff",
      family: "Arial Black, Arial, sans-serif",
      size: 14
    }
  };

  axis.tickfont = {
    color: "#ffffff",
    family: "Arial Black, Arial, sans-serif",
    size: 12
  };

  axis.showgrid = false;
  axis.zeroline = false;
  axis.showline = true;
  axis.linecolor = "#ffffff";
  axis.tickcolor = "#ffffff";
  axis.ticks = "outside";

  // Remove bottom mini range selector / slider.
  if (axis.rangeslider) {
    axis.rangeslider.visible = false;
  }
  delete axis.rangeslider;

  return axis;
}

function stylePlotlyLayoutV508(layout, data, titleFallback) {
  layout = layout || {};

  const titleText =
    typeof layout.title === "string"
      ? layout.title
      : layout.title && layout.title.text
        ? layout.title.text
        : titleFallback || "";

  layout.title = {
    text: "<b>" + String(titleText || "").replace(/<[^>]*>/g, "") + "</b>",
    font: {
      color: "#ffffff",
      family: "Arial Black, Arial, sans-serif",
      size: 18
    }
  };

  layout.paper_bgcolor = "rgba(0,0,0,0)";
  layout.plot_bgcolor = "rgba(0,0,0,0)";

  layout.font = {
    color: "#ffffff",
    family: "Arial, sans-serif",
    size: 13
  };

  const xTitle =
    typeof layout.xaxis?.title === "string"
      ? layout.xaxis.title
      : layout.xaxis?.title?.text || "Date / X";

  const yTitle = inferYAxisTitleV508(layout, data, titleText);

  layout.xaxis = styleAxisV508(layout.xaxis || {}, xTitle);
  layout.yaxis = styleAxisV508(layout.yaxis || {}, yTitle);

  // Global: no range slider.
  if (layout.xaxis) {
    delete layout.xaxis.rangeslider;
  }

  layout.hovermode = "closest";

  layout.legend = Object.assign({
    orientation: "h",
    y: -0.22,
    font: {
      color: "#ffffff",
      family: "Arial, sans-serif",
      size: 12
    },
    bgcolor: "rgba(0,0,0,0)",
    borderwidth: 0
  }, layout.legend || {});

  return layout;
}

function isMapTraceV508(trace, layoutTitle) {
  const type = String(trace?.type || "").toLowerCase();
  const title = String(layoutTitle || "").toLowerCase();

  return (
    title.includes("map") ||
    title.includes("property") ||
    type.includes("heatmap") ||
    type.includes("contour") ||
    type.includes("scattergl")
  );
}

function cleanMapHoverV508(trace, layoutTitle) {
  if (!trace || typeof trace !== "object") return trace;

  if (!isMapTraceV508(trace, layoutTitle)) return trace;

  const type = String(trace.type || "").toLowerCase();

  if (trace.customdata) {
    if (type.includes("heatmap") || trace.z) {
      trace.hovertemplate =
        "I: %{customdata[0]}<br>J: %{customdata[1]}<br>Value: %{z:.5g}<extra></extra>";
    } else {
      trace.hovertemplate =
        "I: %{customdata[0]}<br>J: %{customdata[1]}<br>Value: %{marker.color:.5g}<extra></extra>";
    }
  } else {
    if (type.includes("heatmap") || trace.z) {
      trace.hovertemplate =
        "I: %{x}<br>J: %{y}<br>Value: %{z:.5g}<extra></extra>";
    } else {
      trace.hovertemplate =
        "I: %{x}<br>J: %{y}<br>Value: %{marker.color:.5g}<extra></extra>";
    }
  }

  return trace;
}

function cleanEnsembleHoverAndLegendV508(data, layout) {
  if (!Array.isArray(data)) return data;

  const title =
    typeof layout?.title === "string"
      ? layout.title
      : layout?.title?.text || "";

  const isEnsemble =
    String(title).toLowerCase().includes("p10") ||
    String(title).toLowerCase().includes("p50") ||
    String(title).toLowerCase().includes("p90") ||
    data.some(t => ["P10", "P50", "P90"].includes(String(t?.name || "")));

  if (!isEnsemble) return data;

  for (const trace of data) {
    const name = String(trace.name || "");

    if (["P10", "P50", "P90"].includes(name)) {
      trace.showlegend = true;
      trace.hovertemplate =
        name + "<br>Date: %{x}<br>Value: %{y:.5g}<extra></extra>";
      trace.line = Object.assign(
        {width: name === "P50" ? 4 : 3},
        trace.line || {}
      );
    } else {
      // Individual wells remain visible but do not clutter legend or hover.
      trace.showlegend = false;
      trace.hoverinfo = "skip";
      trace.hovertemplate = null;
      trace.opacity = Math.min(Number(trace.opacity || 0.18), 0.20);
      trace.line = Object.assign({width: 1}, trace.line || {});
    }
  }

  if (layout) {
    layout.hovermode = "closest";
    layout.legend = Object.assign({
      orientation: "h",
      y: -0.22,
      font: {color: "#ffffff"}
    }, layout.legend || {});
  }

  return data;
}

function cleanPlotlyDataAndLayoutV508(data, layout, titleFallback) {
  layout = stylePlotlyLayoutV508(layout || {}, data || [], titleFallback || "");

  const layoutTitle =
    typeof layout.title === "string"
      ? layout.title
      : layout.title?.text || titleFallback || "";

  if (Array.isArray(data)) {
    data = data.map(t => cleanMapHoverV508(t, layoutTitle));
    data = cleanEnsembleHoverAndLegendV508(data, layout);
  }

  return {data, layout};
}

(function installPlotlyPatchV508() {
  if (window.__plotlyPatchV508Installed) return;
  window.__plotlyPatchV508Installed = true;

  function patchWhenReady() {
    if (typeof Plotly === "undefined" || !Plotly.newPlot) {
      setTimeout(patchWhenReady, 300);
      return;
    }

    if (Plotly.__newPlotPatchedV508) return;

    const originalNewPlot = Plotly.newPlot.bind(Plotly);

    Plotly.newPlot = function(div, data, layout, config) {
      try {
        const cleaned = cleanPlotlyDataAndLayoutV508(data, layout || {}, "");
        data = cleaned.data;
        layout = cleaned.layout;
      } catch (e) {
        console.warn("[V508] plot cleanup failed", e);
      }

      return originalNewPlot(div, data, layout, config);
    };

    Plotly.__newPlotPatchedV508 = true;
    console.log("[V508] Plotly global patch active");
  }

  patchWhenReady();
})();

// Override the existing plotly block renderer used by V505A/V507 hooks.
function renderPlotlyChartBlockV505A(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;
  if (!block || block.type !== "plotly_chart") return false;

  let data = Array.isArray(block.data) ? block.data : [];
  let layout = block.layout || {};
  const config = block.config || {};
  const title = block.title || "Interactive chart";

  const cleaned = cleanPlotlyDataAndLayoutV508(data, layout, title);
  data = cleaned.data;
  layout = cleaned.layout;

  const plotId = "plotlyChartV508_" + Date.now();

  panel.innerHTML = `
    <div class="section-title" style="color:#fff;font-weight:800;">${title}</div>
    <div id="${plotId}" style="width:100%;height:${Number(layout.height || 560)}px;"></div>
  `;

  if (typeof Plotly === "undefined") {
    const el = document.getElementById(plotId);
    if (el) {
      el.innerHTML = '<div class="empty-state">Plotly is not loaded, so this chart cannot be rendered interactively.</div>';
    }
    return false;
  }

  Plotly.newPlot(
    plotId,
    data,
    layout,
    Object.assign({responsive: true, displaylogo: false, scrollZoom: true}, config)
  );

  console.log("[V508] plotly_chart rendered", {
    title,
    traces: data.length,
    yaxis: layout.yaxis && layout.yaxis.title
  });

  return true;
}

window.renderPlotlyChartBlockV505A = renderPlotlyChartBlockV505A;
window.cleanPlotlyDataAndLayoutV508 = cleanPlotlyDataAndLayoutV508;
