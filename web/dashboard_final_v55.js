
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
    const data = await postJson("/api/chat", {message: msg});
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
    const data = await postJson("/api/chat?t=" + Date.now(), {message: msg});

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
// V55 LOAD + PLOTLY VISUAL PANEL TEST
// ==========================================================
console.log("[V55] dashboard_final_v55.js loaded successfully");

window.forceTestMapV55 = function() {
  const panel = document.getElementById("visualPanel");
  if (!panel) {
    console.error("[V55] visualPanel not found");
    alert("visualPanel not found");
    return;
  }

  if (typeof Plotly === "undefined") {
    console.error("[V55] Plotly not loaded");
    panel.innerHTML = "<div class='section-title'>Plotly not loaded</div>";
    return;
  }

  panel.innerHTML = `
    <div class="section-title">V55 Test Map</div>
    <div id="v55_test_plot" style="width:100%;height:620px;border-radius:18px;background:#061022;border:1px solid rgba(160,190,255,.14);"></div>
  `;

  Plotly.newPlot("v55_test_plot", [
    {
      type: "scattergl",
      mode: "markers+text",
      x: [10, 20, 30, 40],
      y: [10, 25, 15, 35],
      text: ["A", "B", "C", "D"],
      textposition: "top center",
      marker: {
        size: 16,
        color: [0.1, 0.4, 0.7, 1.0],
        colorscale: "Viridis",
        showscale: true
      }
    }
  ], {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 60, r: 80, t: 30, b: 60 },
    xaxis: { title: "I index", gridcolor: "rgba(160,190,255,.14)" },
    yaxis: { title: "J index", gridcolor: "rgba(160,190,255,.14)" }
  }, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true
  });

  console.log("[V55] Test map rendered");
};



// ==========================================================
// ROBUST PROFILE ENSEMBLE RENDERER V56
// Supports simulated-only, observed-only and both.
// ==========================================================

function renderProfileEnsembleV56(block) {
  const panel = document.getElementById("visualPanel");

  if (!panel) return;

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "Profile Ensemble";
  const variable = payload.variable || "profile";
  const sourceMode = payload.source_mode || "both";
  const series = payload.series || [];
  const simPct = payload.sim_percentiles || [];
  const obsPct = payload.obs_percentiles || [];

  const uid = "profile_ensemble_v56_" + Date.now();

  panel.innerHTML = `
    <div class="section-title">${escapeHtml(title)}</div>
    <div style="color:#9fb3d9;font-size:12px;margin:4px 0 8px 0;">
      Mode: <b>${escapeHtml(sourceMode)}</b> · Wells: <b>${series.length}</b>
    </div>
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

  if (!Array.isArray(series) || !series.length) {
    panel.innerHTML += `<div class="empty-state">No profile arrays were found for this ensemble.</div>`;
    return;
  }

  const traces = [];

  for (const s of series) {
    if (sourceMode !== "observed_only") {
      const y = (s.simulated || []).map(Number).filter(Number.isFinite);
      if (y.length) {
        traces.push({
          type: "scattergl",
          mode: "lines",
          name: `${s.well || "well"} sim`,
          x: y.map((_, idx) => idx),
          y,
          line: { width: 0.75 },
          opacity: 0.18,
          hovertemplate: `<b>${escapeHtml(s.well || "")}</b><br>Step: %{x}<br>Simulated: %{y:.4f}<extra></extra>`,
          showlegend: false,
        });
      }
    }

    if (sourceMode !== "simulated_only") {
      const y = (s.observed || []).map(Number).filter(Number.isFinite);
      if (y.length) {
        traces.push({
          type: "scattergl",
          mode: "lines",
          name: `${s.well || "well"} obs`,
          x: y.map((_, idx) => idx),
          y,
          line: { width: 0.75, dash: "dot" },
          opacity: 0.18,
          hovertemplate: `<b>${escapeHtml(s.well || "")}</b><br>Step: %{x}<br>Observed: %{y:.4f}<extra></extra>`,
          showlegend: false,
        });
      }
    }
  }

  function addPct(rows, key, name, width, dash) {
    const x = [];
    const y = [];

    for (const r of rows || []) {
      const xv = Number(r.x);
      const yv = Number(r[key]);
      if (Number.isFinite(xv) && Number.isFinite(yv)) {
        x.push(xv);
        y.push(yv);
      }
    }

    if (!y.length) return;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name,
      x,
      y,
      line: { width, dash },
      opacity: 1.0,
      hovertemplate: `${name}<br>Step: %{x}<br>Value: %{y:.4f}<extra></extra>`,
    });
  }

  if (sourceMode !== "observed_only") {
    addPct(simPct, "p10", "Sim P10", 2.4, "dot");
    addPct(simPct, "p50", "Sim P50", 4.0, "solid");
    addPct(simPct, "p90", "Sim P90", 2.4, "dot");
  }

  if (sourceMode !== "simulated_only") {
    addPct(obsPct, "p10", "Observed P10", 2.0, "dash");
    addPct(obsPct, "p50", "Observed P50", 3.4, "dash");
    addPct(obsPct, "p90", "Observed P90", 2.0, "dash");
  }

  if (!traces.length) {
    panel.innerHTML += `<div class="empty-state">Profile payload exists, but no numeric arrays were renderable.</div>`;
    return;
  }

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: { color: "#d8e5ff" },
    margin: { l: 76, r: 40, t: 30, b: 76 },
    xaxis: {
      title: "Aligned time step",
      gridcolor: "rgba(160,190,255,.13)",
      zerolinecolor: "rgba(160,190,255,.18)",
    },
    yaxis: {
      title: variable,
      gridcolor: "rgba(160,190,255,.13)",
      zerolinecolor: "rgba(160,190,255,.18)",
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.17,
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

  console.log("[V56] profile ensemble rendered", {
    sourceMode,
    wells: series.length,
    traces: traces.length,
  });
}

// Override old renderer name used by visual router.
renderProfileEnsembleV49 = renderProfileEnsembleV56;



// ==========================================================
// NVIDIA-STYLE GENERIC PROPERTY MAP V57
// Dark diverging map, compact colorbar, better plot area usage.
// Overrides renderGenericPropertyMapV55.
// ==========================================================

function renderGenericPropertyMapV55(block) {
  const panel = document.getElementById("visualPanel");

  if (!panel) {
    console.error("[V57] visualPanel not found");
    return;
  }

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const layer = payload.layer || {};
  const title = block.title || layer.label || "Property Map";
  const operation = payload.operation || layer.operation || "auto";

  const rawCells = layer.cells || layer.points || layer.data || [];
  const cells = rawCells.map(c => ({
    i: Number(c.i ?? c.I ?? c.x ?? c.X),
    j: Number(c.j ?? c.J ?? c.y ?? c.Y),
    value: Number(c.value ?? c.val ?? c.z ?? c.Z ?? c.property_value ?? c.mean ?? c.avg),
    initial: Number(c.initial),
    eoh: Number(c.eoh)
  })).filter(c => Number.isFinite(c.i) && Number.isFinite(c.j) && Number.isFinite(c.value));

  const rawWells = layer.wells || payload.wells || [];
  const wells = rawWells.map(w => ({
    well: w.well || w.name || w.WELL || "",
    i: Number(w.i ?? w.I ?? w.x ?? w.X),
    j: Number(w.j ?? w.J ?? w.y ?? w.Y),
    overall_score: Number(w.overall_score),
    water_score: Number(w.water_score),
    oil_score: Number(w.oil_score),
    gas_score: Number(w.gas_score),
    bhp_score: Number(w.bhp_score)
  })).filter(w => Number.isFinite(w.i) && Number.isFinite(w.j));

  const uid = "generic_property_map_v57_" + Date.now();

  panel.innerHTML = `
    <div class="section-title" style="margin-bottom:4px;">${escapeHtml(title)}</div>
    <div style="
      color:#9fb3d9;
      font-size:12px;
      margin:0 0 8px 0;
      display:flex;
      gap:12px;
      align-items:center;
      flex-wrap:wrap;
    ">
      ${operation === "difference" ? `<span>Computed as <b>End of History − Initial</b></span>` : ""}
      <span>Cells: <b>${cells.length}</b></span>
      ${wells.length ? `<span>Wells: <b>${wells.length}</b></span>` : ""}
    </div>
    <div id="${uid}" style="
      width:100%;
      height:700px;
      border-radius:18px;
      overflow:hidden;
      border:1px solid rgba(90,180,255,.22);
      background:radial-gradient(circle at 30% 20%, rgba(25,72,118,.22), rgba(3,9,22,.96) 60%);
      box-shadow:
        0 18px 42px rgba(0,0,0,.32),
        inset 0 0 36px rgba(0,220,255,.05);
    "></div>
  `;

  if (!cells.length) {
    panel.innerHTML += `<div class="empty-state">No valid cells found for this map.</div>`;
    return;
  }

  const values = cells.map(c => c.value);
  const isDelta =
    operation === "difference" ||
    title.toLowerCase().includes("difference") ||
    title.includes("Δ");

  const maxAbs = Math.max(...values.map(v => Math.abs(v)), 1e-9);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);

  // Dark-friendly colors: negative = amber/red, near zero = dark graphite, positive = cyan/blue.
  const darkDivergingScale = [
    [0.00, "#ff3b1f"],
    [0.18, "#ff8a00"],
    [0.36, "#2b1c18"],
    [0.50, "#07111f"],
    [0.64, "#0b2f46"],
    [0.82, "#00d4ff"],
    [1.00, "#004cff"]
  ];

  const darkSequentialScale = [
    [0.00, "#06111f"],
    [0.20, "#0b2f46"],
    [0.45, "#007a78"],
    [0.70, "#00d46a"],
    [1.00, "#d6ff3f"]
  ];

  const traces = [
    {
      type: "scattergl",
      mode: "markers",
      name: layer.label || payload.property || "Value",
      x: cells.map(c => c.i),
      y: cells.map(c => c.j),
      marker: {
        size: 5.2,
        color: cells.map(c => c.value),
        colorscale: isDelta ? darkDivergingScale : darkSequentialScale,
        cmin: isDelta ? -maxAbs : minVal,
        cmax: isDelta ? maxAbs : maxVal,
        showscale: true,
        colorbar: {
          title: {
            text: layer.label || payload.property || "Value",
            side: "right"
          },
          thickness: 10,
          len: 0.55,
          x: 0.985,
          y: 0.52,
          outlinewidth: 0,
          tickfont: { color: "#d8e5ff", size: 11 },
          titlefont: { color: "#d8e5ff", size: 12 }
        },
        opacity: 0.92
      },
      customdata: cells.map(c => [
        c.value,
        Number.isFinite(c.initial) ? c.initial : null,
        Number.isFinite(c.eoh) ? c.eoh : null
      ]),
      hovertemplate:
        "I: %{x}<br>J: %{y}<br>" +
        "Value: %{customdata[0]:.5f}<br>" +
        "Initial: %{customdata[1]:.5f}<br>" +
        "EOH: %{customdata[2]:.5f}<extra></extra>"
    }
  ];

  if (wells.length) {
    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: "Wells",
      x: wells.map(w => w.i),
      y: wells.map(w => w.j),
      text: wells.map(w => w.well),
      textposition: "top center",
      textfont: {
        color: "#e8f1ff",
        size: 11,
        family: "Inter, Arial, sans-serif"
      },
      marker: {
        size: 12,
        color: "#ff4b1f",
        symbol: "circle",
        line: {
          width: 2.1,
          color: "#ffffff"
        }
      },
      customdata: wells.map(w => [
        w.well,
        w.overall_score,
        w.water_score,
        w.oil_score,
        w.gas_score,
        w.bhp_score
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "I: %{x}<br>J: %{y}<br>" +
        "Overall HM: %{customdata[1]:.1f}/100<br>" +
        "Water HM: %{customdata[2]:.1f}/100<br>" +
        "Oil HM: %{customdata[3]:.1f}/100<br>" +
        "Gas HM: %{customdata[4]:.1f}/100<br>" +
        "BHP HM: %{customdata[5]:.1f}/100<extra></extra>"
    });
  }

  const xs = traces.flatMap(t => t.x || []).map(Number).filter(Number.isFinite);
  const ys = traces.flatMap(t => t.y || []).map(Number).filter(Number.isFinite);

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const padX = Math.max(3, (maxX - minX) * 0.035);
  const padY = Math.max(3, (maxY - minY) * 0.035);

  const layout = {
    paper_bgcolor: "#061022",
    plot_bgcolor: "#061022",
    font: {
      color: "#d8e5ff",
      family: "Inter, Arial, sans-serif"
    },
    margin: {
      l: 58,
      r: 68,
      t: 24,
      b: 58
    },
    xaxis: {
      title: {
        text: "I index",
        font: { size: 12, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.11)",
      zerolinecolor: "rgba(120,190,255,.14)",
      tickfont: { color: "#c7d7f2", size: 11 },
      range: [minX - padX, maxX + padX],
      constrain: "domain"
    },
    yaxis: {
      title: {
        text: "J index",
        font: { size: 12, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.11)",
      zerolinecolor: "rgba(120,190,255,.14)",
      tickfont: { color: "#c7d7f2", size: 11 },
      range: [maxY + padY, minY - padY],
      constrain: "domain"
      // No scaleanchor here: it was making the reservoir map too small in the panel.
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.10,
      bgcolor: "rgba(6,16,34,.62)",
      bordercolor: "rgba(120,190,255,.16)",
      borderwidth: 1,
      font: { size: 11, color: "#d8e5ff" }
    },
    hovermode: "closest"
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  console.log("[V57] generic property map rendered", {
    title,
    cells: cells.length,
    wells: wells.length,
    operation,
    isDelta
  });
}



// ==========================================================
// PREMIUM GENERIC PROPERTY MAP V58
// Dark dashboard style for SWAT/PRESSURE/SOIL difference maps.
// Overrides all generic property map renderers.
// ==========================================================

function renderGenericPropertyMapPremiumV58(block) {
  const panel = document.getElementById("visualPanel");

  if (!panel) {
    console.error("[V58] visualPanel not found");
    return;
  }

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const layer = payload.layer || {};
  const title = block.title || layer.label || "Property Map";
  const operation = payload.operation || layer.operation || "auto";

  const rawCells = layer.cells || layer.points || layer.data || [];
  const cells = rawCells.map(c => ({
    i: Number(c.i ?? c.I ?? c.x ?? c.X),
    j: Number(c.j ?? c.J ?? c.y ?? c.Y),
    value: Number(c.value ?? c.val ?? c.z ?? c.Z ?? c.property_value ?? c.mean ?? c.avg),
    initial: Number(c.initial),
    eoh: Number(c.eoh)
  })).filter(c => Number.isFinite(c.i) && Number.isFinite(c.j) && Number.isFinite(c.value));

  const rawWells = layer.wells || payload.wells || [];
  const wells = rawWells.map(w => ({
    well: w.well || w.name || w.WELL || "",
    i: Number(w.i ?? w.I ?? w.x ?? w.X),
    j: Number(w.j ?? w.J ?? w.y ?? w.Y),
    overall_score: Number(w.overall_score),
    water_score: Number(w.water_score),
    oil_score: Number(w.oil_score),
    gas_score: Number(w.gas_score),
    bhp_score: Number(w.bhp_score)
  })).filter(w => Number.isFinite(w.i) && Number.isFinite(w.j));

  const uid = "generic_property_map_premium_v58_" + Date.now();

  panel.innerHTML = `
    <div style="
      padding:12px 14px 14px 14px;
      border-radius:20px;
      background:
        radial-gradient(circle at 20% 0%, rgba(0,180,255,.12), transparent 34%),
        linear-gradient(180deg, rgba(4,14,32,.96), rgba(2,7,18,.98));
      border:1px solid rgba(95,190,255,.18);
      box-shadow:0 20px 48px rgba(0,0,0,.32), inset 0 0 36px rgba(0,220,255,.035);
    ">
      <div style="
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:8px;
      ">
        <div>
          <div class="section-title" style="margin:0 0 2px 0;">${escapeHtml(title)}</div>
          <div style="color:#9fb3d9;font-size:12px;">
            ${operation === "difference" ? `Computed as <b>End of History − Initial</b>` : `Interactive reservoir property map`}
            · Cells: <b>${cells.length}</b>${wells.length ? ` · Wells: <b>${wells.length}</b>` : ""}
          </div>
        </div>
        <div style="
          font-size:11px;
          color:#9fb3d9;
          border:1px solid rgba(120,190,255,.18);
          border-radius:999px;
          padding:6px 10px;
          background:rgba(5,18,40,.72);
          white-space:nowrap;
        ">
          Pan / zoom enabled
        </div>
      </div>

      <div id="${uid}" style="
        width:100%;
        height:715px;
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(80,165,255,.14);
        background:#020817;
      "></div>
    </div>
  `;

  if (!cells.length) {
    panel.innerHTML += `<div class="empty-state">No valid cells found for this map.</div>`;
    return;
  }

  const values = cells.map(c => c.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const maxAbs = Math.max(...values.map(v => Math.abs(v)), 1e-9);

  const isDelta =
    operation === "difference" ||
    String(title).toLowerCase().includes("difference") ||
    String(title).includes("Δ");

  // For delta maps:
  // negative = orange/red, zero = very dark blue, positive = cyan/blue.
  const deltaScale = [
    [0.00, "#ff3b1f"],
    [0.16, "#ff7a00"],
    [0.34, "#3b2418"],
    [0.50, "#06111f"],
    [0.66, "#07314a"],
    [0.84, "#00d6ff"],
    [1.00, "#1d5cff"]
  ];

  const sequentialScale = [
    [0.00, "#04101f"],
    [0.18, "#06324b"],
    [0.42, "#006b68"],
    [0.68, "#00cc6a"],
    [1.00, "#d9ff42"]
  ];

  const traces = [
    {
      type: "scattergl",
      mode: "markers",
      name: layer.label || payload.property || "Value",
      x: cells.map(c => c.i),
      y: cells.map(c => c.j),
      marker: {
        size: 5.4,
        color: cells.map(c => c.value),
        colorscale: isDelta ? deltaScale : sequentialScale,
        cmin: isDelta ? -maxAbs : minVal,
        cmax: isDelta ? maxAbs : maxVal,
        showscale: true,
        colorbar: {
          title: {
            text: layer.label || payload.property || "Value",
            side: "right"
          },
          thickness: 10,
          len: 0.56,
          x: 0.985,
          y: 0.52,
          outlinewidth: 0,
          tickfont: { color: "#d8e5ff", size: 10 },
          titlefont: { color: "#d8e5ff", size: 11 }
        },
        opacity: 0.94
      },
      customdata: cells.map(c => [
        c.value,
        Number.isFinite(c.initial) ? c.initial : null,
        Number.isFinite(c.eoh) ? c.eoh : null
      ]),
      hovertemplate:
        "I: %{x}<br>J: %{y}<br>" +
        "Value: %{customdata[0]:.5f}<br>" +
        "Initial: %{customdata[1]:.5f}<br>" +
        "EOH: %{customdata[2]:.5f}<extra></extra>"
    }
  ];

  if (wells.length) {
    traces.push({
      type: "scattergl",
      mode: "markers+text",
      name: "Wells",
      x: wells.map(w => w.i),
      y: wells.map(w => w.j),
      text: wells.map(w => w.well),
      textposition: "top center",
      textfont: {
        color: "#e8f1ff",
        size: 11,
        family: "Inter, Arial, sans-serif"
      },
      marker: {
        size: 12,
        color: "#ff4b1f",
        symbol: "circle",
        line: {
          width: 2.0,
          color: "#ffffff"
        }
      },
      customdata: wells.map(w => [
        w.well,
        w.overall_score,
        w.water_score,
        w.oil_score,
        w.gas_score,
        w.bhp_score
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "I: %{x}<br>J: %{y}<br>" +
        "Overall HM: %{customdata[1]:.1f}/100<br>" +
        "Water HM: %{customdata[2]:.1f}/100<br>" +
        "Oil HM: %{customdata[3]:.1f}/100<br>" +
        "Gas HM: %{customdata[4]:.1f}/100<br>" +
        "BHP HM: %{customdata[5]:.1f}/100<extra></extra>"
    });
  }

  const xs = traces.flatMap(t => t.x || []).map(Number).filter(Number.isFinite);
  const ys = traces.flatMap(t => t.y || []).map(Number).filter(Number.isFinite);

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const padX = Math.max(3, (maxX - minX) * 0.025);
  const padY = Math.max(3, (maxY - minY) * 0.025);

  const layout = {
    paper_bgcolor: "#020817",
    plot_bgcolor: "#020817",
    font: {
      color: "#d8e5ff",
      family: "Inter, Arial, sans-serif"
    },
    margin: {
      l: 55,
      r: 58,
      t: 18,
      b: 50
    },
    xaxis: {
      title: {
        text: "I index",
        font: { size: 11, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.09)",
      zerolinecolor: "rgba(120,190,255,.11)",
      tickfont: { color: "#c7d7f2", size: 10 },
      range: [minX - padX, maxX + padX],
      constrain: "domain"
    },
    yaxis: {
      title: {
        text: "J index",
        font: { size: 11, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.09)",
      zerolinecolor: "rgba(120,190,255,.11)",
      tickfont: { color: "#c7d7f2", size: 10 },
      range: [maxY + padY, minY - padY],
      constrain: "domain"
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.09,
      bgcolor: "rgba(2,8,23,.68)",
      bordercolor: "rgba(120,190,255,.12)",
      borderwidth: 1,
      font: { size: 10, color: "#d8e5ff" }
    },
    hovermode: "closest"
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  console.log("[V58] premium generic property map rendered", {
    title,
    cells: cells.length,
    wells: wells.length,
    operation,
    isDelta
  });
}

// Make every existing visual router use the premium version.
renderGenericPropertyMapV55 = renderGenericPropertyMapPremiumV58;
renderGenericPropertyMapV49 = renderGenericPropertyMapPremiumV58;



// ==========================================================
// PREMIUM PROFILE ENSEMBLE RENDERER V58
// All profiles in light gray + P10/P50/P90 highlighted.
// ==========================================================

function renderProfileEnsemblePremiumV58(block) {
  const panel = document.getElementById("visualPanel");

  if (!panel) return;

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "Profile Ensemble";
  const variable = payload.variable || "profile";
  const sourceMode = payload.source_mode || "both";
  const series = payload.series || [];
  const simPct = payload.sim_percentiles || [];
  const obsPct = payload.obs_percentiles || [];

  const uid = "profile_ensemble_premium_v58_" + Date.now();

  panel.innerHTML = `
    <div style="
      padding:12px 14px 14px 14px;
      border-radius:20px;
      background:
        radial-gradient(circle at 20% 0%, rgba(0,180,255,.12), transparent 34%),
        linear-gradient(180deg, rgba(4,14,32,.96), rgba(2,7,18,.98));
      border:1px solid rgba(95,190,255,.18);
      box-shadow:0 20px 48px rgba(0,0,0,.32), inset 0 0 36px rgba(0,220,255,.035);
    ">
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:8px;
      ">
        <div>
          <div class="section-title" style="margin:0 0 2px 0;">${escapeHtml(title)}</div>
          <div style="color:#9fb3d9;font-size:12px;">
            Mode: <b>${escapeHtml(sourceMode)}</b> · Wells: <b>${series.length}</b>
          </div>
        </div>

        <div style="
          display:flex;
          gap:8px;
          align-items:center;
          font-size:11px;
          color:#9fb3d9;
        ">
          <span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:18px;height:2px;background:#ff4040;display:inline-block;"></span>P10</span>
          <span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:18px;height:2px;background:#ffd84a;display:inline-block;"></span>P50</span>
          <span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:18px;height:2px;background:#55ff7a;display:inline-block;"></span>P90</span>
        </div>
      </div>

      <div id="${uid}" style="
        width:100%;
        height:690px;
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(80,165,255,.14);
        background:#020817;
      "></div>
    </div>
  `;

  if (!Array.isArray(series) || !series.length) {
    panel.innerHTML += `<div class="empty-state">No profile arrays were found for this ensemble.</div>`;
    return;
  }

  const traces = [];

  // All profiles: thin light gray.
  for (const s of series) {
    if (sourceMode !== "observed_only") {
      const y = (s.simulated || []).map(Number);
      const x = y.map((_, idx) => idx);
      const valid = y.filter(Number.isFinite);

      if (valid.length) {
        traces.push({
          type: "scattergl",
          mode: "lines",
          name: `${s.well || "well"} simulated`,
          x,
          y,
          line: {
            width: 0.85,
            color: "rgba(220,230,245,.34)"
          },
          opacity: 0.55,
          hovertemplate:
            `<b>${escapeHtml(s.well || "")}</b><br>` +
            "Step: %{x}<br>Simulated: %{y:.4f}<extra></extra>",
          showlegend: false
        });
      }
    }

    if (sourceMode !== "simulated_only") {
      const y = (s.observed || []).map(Number);
      const x = y.map((_, idx) => idx);
      const valid = y.filter(Number.isFinite);

      if (valid.length) {
        traces.push({
          type: "scattergl",
          mode: "lines",
          name: `${s.well || "well"} observed`,
          x,
          y,
          line: {
            width: 0.85,
            color: "rgba(180,200,230,.22)",
            dash: "dot"
          },
          opacity: 0.42,
          hovertemplate:
            `<b>${escapeHtml(s.well || "")}</b><br>` +
            "Step: %{x}<br>Observed: %{y:.4f}<extra></extra>",
          showlegend: false
        });
      }
    }
  }

  function addPct(rows, key, name, color, width, dash) {
    const x = [];
    const y = [];

    for (const r of rows || []) {
      const xv = Number(r.x);
      const yv = Number(r[key]);
      if (Number.isFinite(xv) && Number.isFinite(yv)) {
        x.push(xv);
        y.push(yv);
      }
    }

    if (!y.length) return;

    traces.push({
      type: "scattergl",
      mode: "lines",
      name,
      x,
      y,
      line: {
        color,
        width,
        dash
      },
      opacity: 1.0,
      hovertemplate:
        `${name}<br>` +
        "Step: %{x}<br>Value: %{y:.4f}<extra></extra>"
    });
  }

  if (sourceMode !== "observed_only") {
    addPct(simPct, "p10", "Sim P10", "#ff4040", 3.0, "solid");
    addPct(simPct, "p50", "Sim P50", "#ffd84a", 4.4, "solid");
    addPct(simPct, "p90", "Sim P90", "#55ff7a", 3.0, "solid");
  }

  if (sourceMode !== "simulated_only") {
    addPct(obsPct, "p10", "Obs P10", "#ff4040", 2.2, "dash");
    addPct(obsPct, "p50", "Obs P50", "#ffd84a", 3.2, "dash");
    addPct(obsPct, "p90", "Obs P90", "#55ff7a", 2.2, "dash");
  }

  if (!traces.length) {
    panel.innerHTML += `<div class="empty-state">Profile payload exists, but no numeric arrays were renderable.</div>`;
    return;
  }

  const layout = {
    paper_bgcolor: "#020817",
    plot_bgcolor: "#020817",
    font: {
      color: "#d8e5ff",
      family: "Inter, Arial, sans-serif"
    },
    margin: {
      l: 72,
      r: 34,
      t: 22,
      b: 62
    },
    xaxis: {
      title: {
        text: "Aligned time step",
        font: { size: 12, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 }
    },
    yaxis: {
      title: {
        text: variable,
        font: { size: 12, color: "#9fb3d9" }
      },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 }
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.12,
      bgcolor: "rgba(2,8,23,.68)",
      bordercolor: "rgba(120,190,255,.12)",
      borderwidth: 1,
      font: { size: 11, color: "#d8e5ff" }
    },
    hovermode: "x unified"
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  console.log("[V58] premium profile ensemble rendered", {
    sourceMode,
    wells: series.length,
    traces: traces.length
  });
}

// Force all profile ensemble renderers to this premium one.
renderProfileEnsembleV49 = renderProfileEnsemblePremiumV58;
if (typeof renderProfileEnsembleV56 !== "undefined") {
  renderProfileEnsembleV56 = renderProfileEnsemblePremiumV58;
}



// ==========================================================
// RELPERM CURVE SENSITIVITY RENDERER V60
// Shows original vs proposed Krw curve + export IXF button.
// ==========================================================

function renderRelPermCurveSensitivityV60(block) {
  const panel = document.getElementById("visualPanel");

  if (!panel) return;

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "RelPerm Sensitivity";
  const original = payload.original_curve || [];
  const proposed = payload.proposed_curve || [];
  const well = payload.well || "";
  const model = payload.model || "";
  const factor = payload.factor || 0;
  const action = payload.action || {};
  const uid = "relperm_curve_v60_" + Date.now();

  panel.innerHTML = `
    <div style="
      padding:12px 14px 14px 14px;
      border-radius:20px;
      background:
        radial-gradient(circle at 20% 0%, rgba(0,180,255,.12), transparent 34%),
        linear-gradient(180deg, rgba(4,14,32,.96), rgba(2,7,18,.98));
      border:1px solid rgba(95,190,255,.18);
      box-shadow:0 20px 48px rgba(0,0,0,.32), inset 0 0 36px rgba(0,220,255,.035);
    ">
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:12px;
        margin-bottom:8px;
      ">
        <div>
          <div class="section-title" style="margin:0 0 2px 0;">${escapeHtml(title)}</div>
          <div style="color:#9fb3d9;font-size:12px;line-height:1.45;">
            Well: <b>${escapeHtml(well)}</b> · Model: <b>${escapeHtml(model)}</b>
            · Max conservative factor: <b>${escapeHtml(String(Math.round(factor * 1000) / 10))}%</b>
          </div>
        </div>

        <button id="exportRelpermIXFV60" style="
          cursor:pointer;
          border:1px solid rgba(130,190,255,.35);
          background:rgba(30,80,150,.55);
          color:#e8f1ff;
          border-radius:12px;
          padding:8px 12px;
          font-weight:700;
          white-space:nowrap;
        ">
          Export RelPerm IXF
        </button>
      </div>

      <div style="
        color:#c7d7f2;
        font-size:13px;
        line-height:1.45;
        margin:8px 0 10px 0;
        padding:10px 12px;
        border-radius:14px;
        background:rgba(5,18,40,.64);
        border:1px solid rgba(120,190,255,.12);
      ">
        ${escapeHtml(payload.interpretation || "")}
        <br>
        <span style="color:#9fb3d9">${escapeHtml(payload.risk_statement || "")}</span>
      </div>

      <div id="${uid}" style="
        width:100%;
        height:620px;
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(80,165,255,.14);
        background:#020817;
      "></div>
    </div>
  `;

  if (!original.length || !proposed.length) {
    panel.innerHTML += `<div class="empty-state">No curve arrays available.</div>`;
    return;
  }

  const traces = [
    {
      type: "scattergl",
      mode: "lines+markers",
      name: "Original Krw",
      x: original.map(r => Number(r.saturation)),
      y: original.map(r => Number(r.value)),
      line: {
        color: "rgba(220,230,245,.65)",
        width: 2.6,
        dash: "dot"
      },
      marker: {
        size: 5,
        color: "rgba(220,230,245,.85)"
      },
      hovertemplate: "Original<br>Sw: %{x:.5f}<br>Krw: %{y:.5f}<extra></extra>"
    },
    {
      type: "scattergl",
      mode: "lines+markers",
      name: "Proposed Krw",
      x: proposed.map(r => Number(r.saturation)),
      y: proposed.map(r => Number(r.value)),
      line: {
        color: "#55ff7a",
        width: 4.0
      },
      marker: {
        size: 6,
        color: "#55ff7a"
      },
      hovertemplate: "Proposed<br>Sw: %{x:.5f}<br>Krw: %{y:.5f}<extra></extra>"
    }
  ];

  const layout = {
    paper_bgcolor: "#020817",
    plot_bgcolor: "#020817",
    font: {
      color: "#d8e5ff",
      family: "Inter, Arial, sans-serif"
    },
    margin: {
      l: 72,
      r: 34,
      t: 22,
      b: 62
    },
    xaxis: {
      title: { text: "Water saturation Sw", font: { size: 12, color: "#9fb3d9" } },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 }
    },
    yaxis: {
      title: { text: "Krw", font: { size: 12, color: "#9fb3d9" } },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 },
      rangemode: "tozero"
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.14,
      bgcolor: "rgba(2,8,23,.68)",
      bordercolor: "rgba(120,190,255,.12)",
      borderwidth: 1,
      font: { size: 11, color: "#d8e5ff" }
    },
    hovermode: "closest"
  };

  Plotly.purge(uid);
  Plotly.newPlot(uid, traces, layout, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  const btn = document.getElementById("exportRelpermIXFV60");

  if (btn) {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.innerText = "Generating IXF...";

      try {
        const res = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
        const data = await res.json();

        if (!data.ok || !data.content) {
          alert(data.message || "Could not export RelPerm IXF.");
          btn.disabled = false;
          btn.innerText = "Export RelPerm IXF";
          return;
        }

        const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = data.filename || `RELPERM_${well}.ixf`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);
        btn.innerText = "IXF exported";

      } catch (e) {
        console.error("[V60] RelPerm IXF export failed", e);
        alert("RelPerm IXF export failed. Check console/logs.");
        btn.disabled = false;
        btn.innerText = "Export RelPerm IXF";
      }
    });
  }

  console.log("[V60] relperm curve sensitivity rendered", {well, model, factor});
}

if (typeof directRenderChatVisualV55 === "function" && !window.__relpermRendererV60Patched) {
  const oldDirectRenderChatVisualV55 = directRenderChatVisualV55;

  directRenderChatVisualV55 = function(data) {
    try {
      const blocks = data?.ui_blocks || [];
      const block = blocks.find(b => b && b.type === "relperm_curve_sensitivity");

      if (block) {
        renderRelPermCurveSensitivityV60(block);
        return true;
      }
    } catch (e) {
      console.error("[V60] relperm direct render failed", e);
    }

    return oldDirectRenderChatVisualV55(data);
  };

  window.__relpermRendererV60Patched = true;
  console.log("[V60] RelPerm renderer attached to direct chat visual router");
}



// ==========================================================
// RELPERM CURVE SELECTOR RENDERER V67
// Correct grouped plotting: water-oil, gas-oil, capillary.
// Includes Evaluate/Export buttons for candidate curves.
// ==========================================================

function renderRelPermCurveSelectorV67(block) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return;

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return;
  }

  const payload = block.payload || {};
  const title = block.title || "RelPerm Curves";
  const well = payload.well || "";
  const model = payload.model || "";
  const groups = payload.groups || [];
  const krwAvailable = !!payload.krw_sensitivity_available;

  const uid = "relperm_curve_selector_v67_" + Date.now();
  const controlsId = uid + "_controls";
  const plotId = uid + "_plot";
  const noteId = uid + "_note";

  const groupButtons = groups.map((g, idx) => `
    <button class="relpermGroupBtnV67" data-group-index="${idx}" style="
      cursor:pointer;
      border:1px solid rgba(130,190,255,.25);
      background:${idx === 0 ? "rgba(25,105,180,.78)" : "rgba(5,18,40,.72)"};
      color:#e8f1ff;
      border-radius:999px;
      padding:7px 11px;
      font-size:12px;
      font-weight:700;
    ">
      ${escapeHtml(g.title || g.group)}
    </button>
  `).join("");

  panel.innerHTML = `
    <div style="
      padding:12px 14px 14px 14px;
      border-radius:20px;
      background:
        radial-gradient(circle at 20% 0%, rgba(0,180,255,.12), transparent 34%),
        linear-gradient(180deg, rgba(4,14,32,.96), rgba(2,7,18,.98));
      border:1px solid rgba(95,190,255,.18);
      box-shadow:0 20px 48px rgba(0,0,0,.32), inset 0 0 36px rgba(0,220,255,.035);
    ">
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:12px;
        margin-bottom:8px;
      ">
        <div>
          <div class="section-title" style="margin:0 0 2px 0;">${escapeHtml(title)}</div>
          <div style="color:#9fb3d9;font-size:12px;line-height:1.45;">
            Well: <b>${escapeHtml(well)}</b> · RelPerm model: <b>${escapeHtml(model)}</b>
            · Available curves: <b>${escapeHtml(String(payload.curve_names?.length || 0))}</b>
          </div>
        </div>

        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">
          <button id="evaluateKrwV67" style="
            cursor:pointer;
            border:1px solid rgba(255,216,74,.35);
            background:${krwAvailable ? "rgba(130,95,10,.70)" : "rgba(60,60,70,.45)"};
            color:${krwAvailable ? "#fff2b3" : "#9fb3d9"};
            border-radius:12px;
            padding:8px 12px;
            font-weight:800;
            white-space:nowrap;
          ">
            Evaluate Krw Sensitivity
          </button>

          <button id="exportKrwV67" style="
            cursor:pointer;
            border:1px solid rgba(85,255,122,.35);
            background:${krwAvailable ? "rgba(20,105,55,.72)" : "rgba(60,60,70,.45)"};
            color:${krwAvailable ? "#d8ffe1" : "#9fb3d9"};
            border-radius:12px;
            padding:8px 12px;
            font-weight:800;
            white-space:nowrap;
          ">
            Export Modified Krw IXF
          </button>
        </div>
      </div>

      <div id="${controlsId}" style="
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin:8px 0 10px 0;
      ">
        ${groupButtons}
      </div>

      <div id="${noteId}" style="
        color:#c7d7f2;
        font-size:12px;
        line-height:1.45;
        margin:8px 0 10px 0;
        padding:9px 11px;
        border-radius:14px;
        background:rgba(5,18,40,.64);
        border:1px solid rgba(120,190,255,.12);
      "></div>

      <div id="${plotId}" style="
        width:100%;
        height:640px;
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(80,165,255,.14);
        background:#020817;
      "></div>
    </div>
  `;

  function colorForCurve(name) {
    const n = String(name || "").toLowerCase();
    if (n.includes("krw")) return "#00d6ff";
    if (n.includes("krow") || n.includes("krog")) return "#ffd84a";
    if (n.includes("krg")) return "#55ff7a";
    if (n.includes("pcow")) return "#ff7a00";
    if (n.includes("pcgo")) return "#b46cff";
    return "#d8e5ff";
  }

  function dashForCurve(name) {
    const n = String(name || "").toLowerCase();
    if (n.includes("krow") || n.includes("krog")) return "dot";
    return "solid";
  }

  function renderGroup(groupIndex) {
    const group = groups[groupIndex];
    if (!group) return;

    document.querySelectorAll(".relpermGroupBtnV67").forEach(btn => {
      const active = Number(btn.dataset.groupIndex) === groupIndex;
      btn.style.background = active ? "rgba(25,105,180,.78)" : "rgba(5,18,40,.72)";
    });

    const note = document.getElementById(noteId);
    if (note) {
      if (group.group === "water_oil") {
        note.innerHTML = `
          <b>Water-oil view:</b> Krw is plotted against Sw. Krow is converted to an equivalent Sw axis using
          <b>Sw = 1 − So</b>, so both curves can be inspected together.
        `;
      } else if (group.group === "gas_oil") {
        note.innerHTML = `
          <b>Gas-oil view:</b> Krg is plotted against Sg. Krog is converted to an equivalent Sg axis using
          <b>Sg = 1 − So</b>, so both curves can be inspected together.
        `;
      } else {
        note.innerHTML = `
          <b>Capillary pressure view:</b> Pcow and Pcgo are plotted separately from relperm because they use pressure units
          and should not be mixed on the same y-axis as Kr.
        `;
      }
    }

    const traces = [];

    for (const c of group.curves || []) {
      const rows = c.rows || [];
      const x = rows.map(r => Number(r.saturation)).filter(Number.isFinite);
      const y = rows.map(r => Number(r.value)).filter(Number.isFinite);

      if (!x.length || !y.length) continue;

      traces.push({
        type: "scattergl",
        mode: "lines+markers",
        name: c.label || c.name,
        x,
        y,
        line: {
          color: colorForCurve(c.name),
          width: 3.2,
          dash: dashForCurve(c.name)
        },
        marker: {
          size: 5.5,
          color: colorForCurve(c.name)
        },
        hovertemplate:
          `${escapeHtml(c.label || c.name)}<br>` +
          `${escapeHtml(group.x_axis || "Saturation")}: %{x:.5f}<br>` +
          `${escapeHtml(group.y_axis || "Value")}: %{y:.5f}<extra></extra>`
      });
    }

    const layout = {
      paper_bgcolor: "#020817",
      plot_bgcolor: "#020817",
      font: {
        color: "#d8e5ff",
        family: "Inter, Arial, sans-serif"
      },
      margin: {
        l: 76,
        r: 34,
        t: 30,
        b: 68
      },
      title: {
        text: group.title || "",
        font: { color: "#d8e5ff", size: 15 },
        x: 0.02
      },
      xaxis: {
        title: { text: group.x_axis || "Saturation", font: { size: 12, color: "#9fb3d9" } },
        gridcolor: "rgba(120,190,255,.10)",
        zerolinecolor: "rgba(120,190,255,.13)",
        tickfont: { color: "#c7d7f2", size: 10 }
      },
      yaxis: {
        title: { text: group.y_axis || "Value", font: { size: 12, color: "#9fb3d9" } },
        gridcolor: "rgba(120,190,255,.10)",
        zerolinecolor: "rgba(120,190,255,.13)",
        tickfont: { color: "#c7d7f2", size: 10 },
        rangemode: group.group === "capillary" ? "normal" : "tozero"
      },
      legend: {
        orientation: "h",
        x: 0,
        y: -0.15,
        bgcolor: "rgba(2,8,23,.68)",
        bordercolor: "rgba(120,190,255,.12)",
        borderwidth: 1,
        font: { size: 11, color: "#d8e5ff" }
      },
      hovermode: "closest"
    };

    Plotly.purge(plotId);
    Plotly.newPlot(plotId, traces, layout, {
      responsive: true,
      displaylogo: false,
      scrollZoom: true,
      modeBarButtonsToRemove: ["lasso2d", "select2d"]
    });
  }

  document.querySelectorAll(".relpermGroupBtnV67").forEach(btn => {
    btn.addEventListener("click", () => renderGroup(Number(btn.dataset.groupIndex)));
  });

  const evaluateBtn = document.getElementById("evaluateKrwV67");
  if (evaluateBtn) {
    evaluateBtn.addEventListener("click", async () => {
      const input = document.getElementById("chatInput");
      if (input) input.value = `evaluate Krw sensitivity for ${well}`;
      if (typeof askChatV9 === "function") {
        askChatV9(`evaluate Krw sensitivity for ${well}`);
      } else if (typeof askChat === "function") {
        askChat(`evaluate Krw sensitivity for ${well}`);
      }
    });
  }

  const exportBtn = document.getElementById("exportKrwV67");
  if (exportBtn) {
    exportBtn.addEventListener("click", async () => {
      exportBtn.disabled = true;
      exportBtn.innerText = "Generating IXF...";

      try {
        const res = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
        const data = await res.json();

        if (!data.ok || !data.content) {
          alert(data.message || "Could not export RelPerm IXF. The well may not be eligible for Krw modification.");
          exportBtn.disabled = false;
          exportBtn.innerText = "Export Modified Krw IXF";
          return;
        }

        const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = data.filename || `RELPERM_${well}.ixf`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);
        exportBtn.innerText = "IXF exported";

      } catch (e) {
        console.error("[V67] RelPerm IXF export failed", e);
        alert("RelPerm IXF export failed. Check console/logs.");
        exportBtn.disabled = false;
        exportBtn.innerText = "Export Modified Krw IXF";
      }
    });
  }

  renderGroup(0);

  console.log("[V67] relperm curve selector rendered", {well, model, groups: groups.map(g => g.group)});
}


if (typeof directRenderChatVisualV55 === "function" && !window.__relpermCurveSelectorV67Patched) {
  const oldDirectRenderChatVisualV55_V67 = directRenderChatVisualV55;

  directRenderChatVisualV55 = function(data) {
    try {
      const blocks = data?.ui_blocks || [];
      const selectorBlock = blocks.find(b => b && b.type === "relperm_curve_selector");

      if (selectorBlock) {
        renderRelPermCurveSelectorV67(selectorBlock);
        return true;
      }

      const sensBlock = blocks.find(b => b && b.type === "relperm_curve_sensitivity");

      if (sensBlock && typeof renderRelPermCurveSensitivityV60 === "function") {
        renderRelPermCurveSensitivityV60(sensBlock);
        return true;
      }

    } catch (e) {
      console.error("[V67] RelPerm selector direct render failed", e);
    }

    return oldDirectRenderChatVisualV55_V67(data);
  };

  window.__relpermCurveSelectorV67Patched = true;
  console.log("[V67] RelPerm curve selector renderer attached");
}



// ==========================================================
// RELPERM ABSOLUTE CHAT VISUAL HOOK V69
// Forces relperm visual rendering after every chat response.
// ==========================================================

function forceRelPermVisualRenderV69(data) {
  try {
    const blocks = data?.ui_blocks || [];
    console.log("[V69] checking relperm visual blocks:", blocks.map(b => b.type));

    const selectorBlock = blocks.find(b => b && b.type === "relperm_curve_selector");
    if (selectorBlock && typeof renderRelPermCurveSelectorV67 === "function") {
      console.log("[V69] rendering relperm_curve_selector", selectorBlock);
      renderRelPermCurveSelectorV67(selectorBlock);
      return true;
    }

    const sensitivityBlock = blocks.find(b => b && b.type === "relperm_curve_sensitivity");
    if (sensitivityBlock && typeof renderRelPermCurveSensitivityV60 === "function") {
      console.log("[V69] rendering relperm_curve_sensitivity", sensitivityBlock);
      renderRelPermCurveSensitivityV60(sensitivityBlock);
      return true;
    }

    return false;

  } catch (e) {
    console.error("[V69] forceRelPermVisualRenderV69 failed", e);
    return false;
  }
}




// ==========================================================
// EMBEDDED RELPERM ACTION BUTTONS IN WELL CARD V70
// Adds Evaluate / Export RelPerm buttons only for eligible wells.
// ==========================================================

async function fetchRelPermEligibilityV70(well) {
  try {
    const res = await fetch(`/api/relperm/sensitivity/${encodeURIComponent(well)}?ts=${Date.now()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn("[V70] RelPerm eligibility fetch failed", e);
    return null;
  }
}

function findSelectedWellFromCardTextV70(text) {
  if (!text) return null;

  const m = String(text).match(/\bHW[-_\s]?(\d+[A-Z]?)\b/i);
  if (m) return `HW-${m[1].toUpperCase()}`;

  return null;
}

function createRelPermActionPanelV70(well, payload) {
  const div = document.createElement("div");
  div.className = "relperm-action-panel-v70";
  div.dataset.well = well;

  div.style.marginTop = "12px";
  div.style.padding = "12px";
  div.style.borderRadius = "14px";
  div.style.border = "1px solid rgba(85,255,122,.25)";
  div.style.background = "linear-gradient(180deg, rgba(8,36,34,.82), rgba(4,18,28,.92))";
  div.style.boxShadow = "inset 0 0 22px rgba(85,255,122,.05)";

  const model = payload?.model || "";
  const factor = payload?.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
  const curve = payload?.curve_name || "Krw_v_Sw";
  const interpretation = payload?.interpretation || "";
  const risk = payload?.risk_statement || "";

  div.innerHTML = `
    <div style="
      display:flex;
      justify-content:space-between;
      gap:10px;
      align-items:flex-start;
      margin-bottom:8px;
    ">
      <div>
        <div style="font-weight:800;color:#d8ffe1;font-size:13px;">
          RelPerm candidate available
        </div>
        <div style="color:#9fb3d9;font-size:12px;line-height:1.4;margin-top:2px;">
          Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Conservative factor: <b>${escapeHtml(factor)}</b>` : ""}
        </div>
      </div>
    </div>

    <div style="
      color:#c7d7f2;
      font-size:12px;
      line-height:1.45;
      margin:7px 0 10px 0;
    ">
      ${escapeHtml(interpretation).slice(0, 420)}
      ${risk ? `<br><span style="color:#9fb3d9">${escapeHtml(risk).slice(0, 320)}</span>` : ""}
    </div>

    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="relperm-evaluate-btn-v70" data-well="${escapeHtml(well)}" style="
        cursor:pointer;
        border:1px solid rgba(255,216,74,.42);
        background:rgba(130,95,10,.72);
        color:#fff2b3;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Evaluate RelPerm Curve
      </button>

      <button class="relperm-export-btn-v70" data-well="${escapeHtml(well)}" style="
        cursor:pointer;
        border:1px solid rgba(85,255,122,.42);
        background:rgba(20,105,55,.74);
        color:#d8ffe1;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Export Modified RelPerm IXF
      </button>
    </div>
  `;

  const evaluateBtn = div.querySelector(".relperm-evaluate-btn-v70");
  const exportBtn = div.querySelector(".relperm-export-btn-v70");

  if (evaluateBtn) {
    evaluateBtn.addEventListener("click", () => {
      const q = `evaluate Krw sensitivity for ${well}`;
      const input = document.getElementById("chatInput");
      if (input) input.value = q;

      if (typeof askChatV9 === "function") {
        askChatV9(q);
      } else if (typeof askChat === "function") {
        askChat(q);
      }
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", async () => {
      exportBtn.disabled = true;
      exportBtn.innerText = "Generating IXF...";

      try {
        const res = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
        const data = await res.json();

        if (!data.ok || !data.content) {
          alert(data.message || "RelPerm IXF export is not available for this well.");
          exportBtn.disabled = false;
          exportBtn.innerText = "Export Modified RelPerm IXF";
          return;
        }

        const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = data.filename || `RELPERM_${well}.ixf`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);
        exportBtn.innerText = "IXF exported";

      } catch (e) {
        console.error("[V70] RelPerm IXF export failed", e);
        alert("RelPerm IXF export failed. Check console/logs.");
        exportBtn.disabled = false;
        exportBtn.innerText = "Export Modified RelPerm IXF";
      }
    });
  }

  return div;
}

async function attachRelPermButtonsToWellCardV70() {
  try {
    const candidates = Array.from(document.querySelectorAll("div, section, article"))
      .filter(el => {
        const txt = el.innerText || "";
        return (
          txt.includes("Key Findings") ||
          txt.includes("Recommended") ||
          txt.includes("Pattern-Aware") ||
          txt.includes("Criticalities")
        ) && /\bHW[-_\s]?\d+/i.test(txt);
      });

    if (!candidates.length) return;

    // Prefer the smallest reasonable card containing the selected well info.
    candidates.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);
    const card = candidates[0];

    const well = findSelectedWellFromCardTextV70(card.innerText);
    if (!well) return;

    const existing = card.querySelector(`.relperm-action-panel-v70[data-well="${well}"]`);
    if (existing) return;

    // Avoid stacking panels for other wells.
    card.querySelectorAll(".relperm-action-panel-v70").forEach(x => x.remove());

    const payload = await fetchRelPermEligibilityV70(well);

    if (!payload || !payload.eligible) {
      console.log("[V70] RelPerm not eligible for", well, payload?.message || "");
      return;
    }

    const panel = createRelPermActionPanelV70(well, payload);
    card.appendChild(panel);

    console.log("[V70] RelPerm buttons attached for", well, payload);

  } catch (e) {
    console.error("[V70] attachRelPermButtonsToWellCardV70 failed", e);
  }
}

if (false && !window.__relpermWellCardObserverV70) {
  let relpermObserverTimerV70 = null;

  const observer = new MutationObserver(() => {
    clearTimeout(relpermObserverTimerV70);
    relpermObserverTimerV70 = setTimeout(() => {
      attachRelPermButtonsToWellCardV70();
    }, 250);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });

  // Initial attempt.
  setTimeout(() => attachRelPermButtonsToWellCardV70(), 800);

  window.__relpermWellCardObserverV70 = true;
  console.log("[V70] Embedded RelPerm well-card buttons observer active");
}




// ==========================================================
// RELPERM FLOATING ACTION PANEL V72
// Robust fallback: if a selected/visible well is eligible,
// show RelPerm buttons directly in visualPanel.
// ==========================================================

function findVisibleWellV72() {
  const txt = document.body.innerText || "";
  const matches = Array.from(txt.matchAll(/\bHW[-_\s]?(\d+[A-Z]?)\b/gi))
    .map(m => `HW-${String(m[1]).toUpperCase()}`);

  // Prefer wells visible near recommendation/card text.
  const cards = Array.from(document.querySelectorAll("div, section, article"))
    .filter(el => {
      const t = el.innerText || "";
      return (
        /\bHW[-_\s]?\d+/i.test(t) &&
        (
          t.includes("Key Findings") ||
          t.includes("Recommended") ||
          t.includes("Criticalities") ||
          t.includes("Pattern-Aware") ||
          t.includes("Water match") ||
          t.includes("RelPerm")
        )
      );
    });

  for (const c of cards) {
    const m = (c.innerText || "").match(/\bHW[-_\s]?(\d+[A-Z]?)\b/i);
    if (m) return `HW-${String(m[1]).toUpperCase()}`;
  }

  return matches.length ? matches[matches.length - 1] : null;
}

async function showFloatingRelPermPanelV72(well=null) {
  try {
    const selectedWell = well || findVisibleWellV72();
    if (!selectedWell) {
      console.log("[V72] No visible well detected for RelPerm panel");
      return false;
    }

    const panel = document.getElementById("visualPanel");
    if (!panel) {
      console.log("[V72] visualPanel not found");
      return false;
    }

    const res = await fetch(`/api/relperm/sensitivity/${encodeURIComponent(selectedWell)}?ts=${Date.now()}`);
    const payload = await res.json();

    // Remove old floating panels.
    panel.querySelectorAll(".relperm-floating-panel-v72").forEach(x => x.remove());

    if (!payload || !payload.eligible) {
      console.log("[V72] RelPerm not eligible for", selectedWell, payload?.message || "");
      return false;
    }

    const model = payload.model || "";
    const curve = payload.curve_name || "Krw_v_Sw";
    const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
    const same = payload.impacted_wells_summary?.same_direction || [];
    const opp = payload.impacted_wells_summary?.opposite_direction || [];

    const box = document.createElement("div");
    box.className = "relperm-floating-panel-v72";
    box.style.cssText = `
      position: sticky;
      top: 8px;
      z-index: 999;
      margin: 0 0 12px 0;
      padding: 12px;
      border-radius: 16px;
      border: 1px solid rgba(85,255,122,.34);
      background: linear-gradient(180deg, rgba(8,36,34,.95), rgba(4,18,28,.96));
      box-shadow: 0 16px 38px rgba(0,0,0,.32), inset 0 0 22px rgba(85,255,122,.06);
      color: #d8ffe1;
    `;

    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div>
          <div style="font-size:13px;font-weight:900;color:#d8ffe1;">
            RelPerm candidate available for ${escapeHtml(selectedWell)}
          </div>
          <div style="font-size:12px;color:#9fb3d9;margin-top:3px;line-height:1.45;">
            Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Conservative uplift: <b>${escapeHtml(factor)}</b>` : ""}
            <br>
            Same-direction wells: <b>${escapeHtml(same.join(", ") || "None")}</b>
            ${opp.length ? `<br><span style="color:#ffd18a;">Risk: opposite-direction wells ${escapeHtml(opp.join(", "))}</span>` : ""}
          </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;">
          <button id="relpermFloatEvaluateV72" style="
            cursor:pointer;
            border:1px solid rgba(255,216,74,.42);
            background:rgba(130,95,10,.72);
            color:#fff2b3;
            border-radius:12px;
            padding:8px 11px;
            font-weight:800;
            font-size:12px;
            white-space:nowrap;
          ">
            Evaluate RelPerm Curve
          </button>

          <button id="relpermFloatExportV72" style="
            cursor:pointer;
            border:1px solid rgba(85,255,122,.42);
            background:rgba(20,105,55,.74);
            color:#d8ffe1;
            border-radius:12px;
            padding:8px 11px;
            font-weight:800;
            font-size:12px;
            white-space:nowrap;
          ">
            Export Modified RelPerm IXF
          </button>
        </div>
      </div>
    `;

    panel.prepend(box);

    const evalBtn = document.getElementById("relpermFloatEvaluateV72");
    const expBtn = document.getElementById("relpermFloatExportV72");

    if (evalBtn) {
      evalBtn.onclick = () => {
        const q = `evaluate Krw sensitivity for ${selectedWell}`;
        const input = document.getElementById("chatInput");
        if (input) input.value = q;

        if (typeof askChatV9 === "function") askChatV9(q);
        else if (typeof askChat === "function") askChat(q);
      };
    }

    if (expBtn) {
      expBtn.onclick = async () => {
        expBtn.disabled = true;
        expBtn.innerText = "Generating IXF...";

        try {
          const r = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(selectedWell)}?ts=${Date.now()}`);
          const data = await r.json();

          if (!data.ok || !data.content) {
            alert(data.message || "RelPerm IXF export is not available for this well.");
            expBtn.disabled = false;
            expBtn.innerText = "Export Modified RelPerm IXF";
            return;
          }

          const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
          const url = URL.createObjectURL(blob);

          const a = document.createElement("a");
          a.href = url;
          a.download = data.filename || `RELPERM_${selectedWell}.ixf`;
          document.body.appendChild(a);
          a.click();
          a.remove();

          URL.revokeObjectURL(url);
          expBtn.innerText = "IXF exported";

        } catch (e) {
          console.error("[V72] RelPerm IXF export failed", e);
          alert("RelPerm IXF export failed. Check console/logs.");
          expBtn.disabled = false;
          expBtn.innerText = "Export Modified RelPerm IXF";
        }
      };
    }

    console.log("[V72] Floating RelPerm panel shown for", selectedWell, payload);
    return true;

  } catch (e) {
    console.error("[V72] showFloatingRelPermPanelV72 failed", e);
    return false;
  }
}

if (false && !window.__relpermFloatingPanelV72) {
  let relpermFloatingTimerV72 = null;

  const relpermFloatingObserverV72 = new MutationObserver(() => {
    clearTimeout(relpermFloatingTimerV72);
    relpermFloatingTimerV72 = setTimeout(() => {
      showFloatingRelPermPanelV72();
    }, 500);
  });

  relpermFloatingObserverV72.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });

  window.showFloatingRelPermPanelV72 = showFloatingRelPermPanelV72;
  window.__relpermFloatingPanelV72 = true;

  setTimeout(() => showFloatingRelPermPanelV72(), 1200);

  console.log("[V72] Floating RelPerm panel observer active. You can run showFloatingRelPermPanelV72('HW-28')");
}




// ==========================================================
// LIGHTWEIGHT RELPERM PLOTLY CLICK HOOK V73
// No MutationObserver scan. Hooks Plotly clicks and shows buttons only for eligible wells.
// ==========================================================

function extractWellNameDeepV73(obj) {
  try {
    const raw = JSON.stringify(obj);
    const m = raw.match(/\bHW[-_\s]?(\d+[A-Z]?)\b/i);
    if (m) return `HW-${String(m[1]).toUpperCase()}`;
  } catch (e) {}

  return null;
}

async function getRelPermCandidateV73(well) {
  try {
    const res = await fetch(`/api/relperm/sensitivity/${encodeURIComponent(well)}?ts=${Date.now()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn("[V73] RelPerm candidate fetch failed", e);
    return null;
  }
}

function removeRelPermPanelV73() {
  document.querySelectorAll(".relperm-action-panel-v73").forEach(x => x.remove());
}

function buildRelPermPanelV73(well, payload) {
  const model = payload.model || "";
  const curve = payload.curve_name || "Krw_v_Sw";
  const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
  const same = payload.impacted_wells_summary?.same_direction || [];
  const opp = payload.impacted_wells_summary?.opposite_direction || [];

  const box = document.createElement("div");
  box.className = "relperm-action-panel-v73";
  box.style.cssText = `
    margin: 0 0 12px 0;
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(85,255,122,.34);
    background: linear-gradient(180deg, rgba(8,36,34,.95), rgba(4,18,28,.96));
    box-shadow: 0 16px 38px rgba(0,0,0,.32), inset 0 0 22px rgba(85,255,122,.06);
    color: #d8ffe1;
  `;

  box.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
      <div style="min-width:260px;flex:1;">
        <div style="font-size:13px;font-weight:900;color:#d8ffe1;">
          RelPerm candidate available for ${escapeHtml(well)}
        </div>
        <div style="font-size:12px;color:#9fb3d9;margin-top:3px;line-height:1.45;">
          Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Conservative uplift: <b>${escapeHtml(factor)}</b>` : ""}
          <br>
          Same-direction wells: <b>${escapeHtml(same.join(", ") || "None")}</b>
          ${opp.length ? `<br><span style="color:#ffd18a;">Risk: opposite-direction wells ${escapeHtml(opp.join(", "))}</span>` : ""}
        </div>
      </div>

      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button id="relpermEvaluateV73" style="
          cursor:pointer;
          border:1px solid rgba(255,216,74,.42);
          background:rgba(130,95,10,.72);
          color:#fff2b3;
          border-radius:12px;
          padding:8px 11px;
          font-weight:800;
          font-size:12px;
          white-space:nowrap;
        ">
          Evaluate RelPerm Curve
        </button>

        <button id="relpermExportV73" style="
          cursor:pointer;
          border:1px solid rgba(85,255,122,.42);
          background:rgba(20,105,55,.74);
          color:#d8ffe1;
          border-radius:12px;
          padding:8px 11px;
          font-weight:800;
          font-size:12px;
          white-space:nowrap;
        ">
          Export Modified RelPerm IXF
        </button>
      </div>
    </div>
  `;

  const evalBtn = box.querySelector("#relpermEvaluateV73");
  const expBtn = box.querySelector("#relpermExportV73");

  evalBtn.onclick = () => {
    const q = `evaluate Krw sensitivity for ${well}`;
    const input = document.getElementById("chatInput");
    if (input) input.value = q;

    if (typeof askChatV9 === "function") askChatV9(q);
    else if (typeof askChat === "function") askChat(q);
  };

  expBtn.onclick = async () => {
    expBtn.disabled = true;
    expBtn.innerText = "Generating IXF...";

    try {
      const r = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
      const data = await r.json();

      if (!data.ok || !data.content) {
        alert(data.message || "RelPerm IXF export is not available for this well.");
        expBtn.disabled = false;
        expBtn.innerText = "Export Modified RelPerm IXF";
        return;
      }

      const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename || `RELPERM_${well}.ixf`;
      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(url);
      expBtn.innerText = "IXF exported";

    } catch (e) {
      console.error("[V73] RelPerm IXF export failed", e);
      alert("RelPerm IXF export failed. Check console/logs.");
      expBtn.disabled = false;
      expBtn.innerText = "Export Modified RelPerm IXF";
    }
  };

  return box;
}

async function showRelPermPanelForWellV73(well) {
  if (!well) return false;

  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  const payload = await getRelPermCandidateV73(well);

  removeRelPermPanelV73();

  if (!payload || !payload.eligible) {
    console.log("[V73] RelPerm not eligible for", well, payload?.message || "");
    return false;
  }

  const box = buildRelPermPanelV73(well, payload);
  panel.prepend(box);

  console.log("[V73] RelPerm panel shown for", well, payload);
  return true;
}

function hookPlotlyRelPermClicksV73() {
  if (typeof Plotly === "undefined") {
    console.log("[V73] Plotly not ready yet");
    return;
  }

  const plots = Array.from(document.querySelectorAll(".js-plotly-plot"));
  let hooked = 0;

  for (const plot of plots) {
    if (plot.dataset.relpermClickHookedV73 === "true") continue;

    plot.dataset.relpermClickHookedV73 = "true";
    hooked += 1;

    plot.on("plotly_click", function(evt) {
      try {
        const point = evt?.points?.[0];
        const well =
          extractWellNameDeepV73(point?.customdata) ||
          extractWellNameDeepV73(point?.text) ||
          extractWellNameDeepV73(point?.data) ||
          extractWellNameDeepV73(point);

        console.log("[V73] Plotly click detected well:", well, point);

        if (well) {
          window.lastSelectedWellV73 = well;
          showRelPermInlineActionsV75(well);
        }

      } catch (e) {
        console.error("[V73] plotly_click handler failed", e);
      }
    });
  }

  if (hooked) console.log("[V73] Hooked Plotly relperm clicks on plots:", hooked);
}

if (!window.__relpermPlotlyClickHookV73) {
  window.showRelPermPanelForWellV73 = showRelPermPanelForWellV73;
  window.hookPlotlyRelPermClicksV73 = hookPlotlyRelPermClicksV73;

  // Hook a few times after page load / redraws, without heavy DOM scanning.
  setTimeout(hookPlotlyRelPermClicksV73, 800);
  setTimeout(hookPlotlyRelPermClicksV73, 1800);
  setTimeout(hookPlotlyRelPermClicksV73, 3500);

  // Re-hook after chat renders or map redraws.
  document.addEventListener("click", function() {
    setTimeout(hookPlotlyRelPermClicksV73, 300);
  }, true);

  window.__relpermPlotlyClickHookV73 = true;
  console.log("[V73] Lightweight RelPerm Plotly click hook active. Manual test: showRelPermPanelForWellV73('HW-28')");
}




// ==========================================================
// GLOBAL RELPERM FLOATING PANEL V74
// Appends to document.body, not visualPanel, so it cannot be hidden by Plotly redraws.
// ==========================================================

async function showRelPermGlobalPanelV74(well) {
  try {
    if (!well) return false;

    const payload = await getRelPermCandidateV73(well);

    document.querySelectorAll(".relperm-global-panel-v74").forEach(x => x.remove());

    if (!payload || !payload.eligible) {
      console.log("[V74] RelPerm not eligible for", well, payload?.message || "");
      return false;
    }

    const model = payload.model || "";
    const curve = payload.curve_name || "Krw_v_Sw";
    const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
    const same = payload.impacted_wells_summary?.same_direction || [];
    const opp = payload.impacted_wells_summary?.opposite_direction || [];

    const box = document.createElement("div");
    box.className = "relperm-global-panel-v74";

    box.style.cssText = `
      position: fixed;
      right: 22px;
      bottom: 22px;
      width: min(520px, calc(100vw - 44px));
      z-index: 2147483000;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid rgba(85,255,122,.42);
      background:
        radial-gradient(circle at 15% 0%, rgba(85,255,122,.16), transparent 34%),
        linear-gradient(180deg, rgba(8,36,34,.98), rgba(4,18,28,.98));
      box-shadow:
        0 24px 70px rgba(0,0,0,.55),
        inset 0 0 26px rgba(85,255,122,.07);
      color: #d8ffe1;
      font-family: Inter, Arial, sans-serif;
    `;

    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;">
        <div>
          <div style="font-size:14px;font-weight:900;color:#d8ffe1;">
            RelPerm candidate available for ${escapeHtml(well)}
          </div>
          <div style="font-size:12px;color:#9fb3d9;margin-top:4px;line-height:1.45;">
            Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Uplift: <b>${escapeHtml(factor)}</b>` : ""}
            <br>
            Same-direction wells: <b>${escapeHtml(same.join(", ") || "None")}</b>
            ${opp.length ? `<br><span style="color:#ffd18a;">Risk: opposite-direction wells ${escapeHtml(opp.join(", "))}</span>` : ""}
          </div>
        </div>

        <button id="relpermCloseV74" style="
          cursor:pointer;
          border:1px solid rgba(255,255,255,.16);
          background:rgba(255,255,255,.06);
          color:#d8e5ff;
          border-radius:999px;
          width:28px;
          height:28px;
          font-weight:900;
        ">×</button>
      </div>

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
        <button id="relpermEvaluateV74" style="
          cursor:pointer;
          border:1px solid rgba(255,216,74,.46);
          background:rgba(130,95,10,.78);
          color:#fff2b3;
          border-radius:12px;
          padding:9px 12px;
          font-weight:850;
          font-size:12px;
          white-space:nowrap;
        ">
          Evaluate RelPerm Curve
        </button>

        <button id="relpermExportV74" style="
          cursor:pointer;
          border:1px solid rgba(85,255,122,.46);
          background:rgba(20,105,55,.80);
          color:#d8ffe1;
          border-radius:12px;
          padding:9px 12px;
          font-weight:850;
          font-size:12px;
          white-space:nowrap;
        ">
          Export Modified RelPerm IXF
        </button>
      </div>
    `;

    document.body.appendChild(box);

    const closeBtn = document.getElementById("relpermCloseV74");
    const evalBtn = document.getElementById("relpermEvaluateV74");
    const expBtn = document.getElementById("relpermExportV74");

    if (closeBtn) {
      closeBtn.onclick = () => box.remove();
    }

    if (evalBtn) {
      evalBtn.onclick = () => {
        const q = `evaluate Krw sensitivity for ${well}`;
        const input = document.getElementById("chatInput");
        if (input) input.value = q;

        if (typeof askChatV9 === "function") askChatV9(q);
        else if (typeof askChat === "function") askChat(q);
      };
    }

    if (expBtn) {
      expBtn.onclick = async () => {
        expBtn.disabled = true;
        expBtn.innerText = "Generating IXF...";

        try {
          const r = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
          const data = await r.json();

          if (!data.ok || !data.content) {
            alert(data.message || "RelPerm IXF export is not available for this well.");
            expBtn.disabled = false;
            expBtn.innerText = "Export Modified RelPerm IXF";
            return;
          }

          const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
          const url = URL.createObjectURL(blob);

          const a = document.createElement("a");
          a.href = url;
          a.download = data.filename || `RELPERM_${well}.ixf`;
          document.body.appendChild(a);
          a.click();
          a.remove();

          URL.revokeObjectURL(url);
          expBtn.innerText = "IXF exported";

        } catch (e) {
          console.error("[V74] RelPerm IXF export failed", e);
          alert("RelPerm IXF export failed. Check console/logs.");
          expBtn.disabled = false;
          expBtn.innerText = "Export Modified RelPerm IXF";
        }
      };
    }

    console.log("[V74] Global RelPerm panel shown for", well, payload);
    return true;

  } catch (e) {
    console.error("[V74] showRelPermGlobalPanelV74 failed", e);
    return false;
  }
}

// Override manual test helper to use the visible global panel.
window.showRelPermGlobalPanelV74 = showRelPermGlobalPanelV74;
window.showRelPermPanelForWellV73 = showRelPermGlobalPanelV74;

console.log("[V74] Global RelPerm floating panel active. Test: await showRelPermGlobalPanelV74('HW-28')");



// ==========================================================
// RELPERM ACTION UX V75
// Anchored near recommendation / TRAN action area.
// Evaluate renders curve directly, export downloads IXF.
// ==========================================================

function renderRelPermCurveEvaluationV75(payload) {
  const panel = document.getElementById("visualPanel");
  if (!panel) return false;

  if (typeof Plotly === "undefined") {
    panel.innerHTML = `<div class="section-title">Plotly not loaded</div>`;
    return false;
  }

  const well = payload.well || "";
  const model = payload.model || "";
  const curve = payload.curve_name || "Krw_v_Sw";
  const original = payload.original_curve || [];
  const proposed = payload.proposed_curve || [];
  const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
  const uid = "relperm_eval_v75_" + Date.now();

  panel.innerHTML = `
    <div style="
      padding:12px 14px 14px 14px;
      border-radius:20px;
      background:
        radial-gradient(circle at 20% 0%, rgba(85,255,122,.12), transparent 34%),
        linear-gradient(180deg, rgba(4,14,32,.96), rgba(2,7,18,.98));
      border:1px solid rgba(95,255,165,.20);
      box-shadow:0 20px 48px rgba(0,0,0,.32), inset 0 0 36px rgba(85,255,122,.04);
    ">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px;">
        <div>
          <div class="section-title" style="margin:0 0 2px 0;">
            RelPerm Sensitivity Evaluation - ${escapeHtml(well)}
          </div>
          <div style="color:#9fb3d9;font-size:12px;line-height:1.45;">
            Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Conservative uplift: <b>${escapeHtml(factor)}</b>` : ""}
          </div>
        </div>

        <button id="relpermEvalExportV75" style="
          cursor:pointer;
          border:1px solid rgba(85,255,122,.42);
          background:rgba(20,105,55,.78);
          color:#d8ffe1;
          border-radius:12px;
          padding:9px 12px;
          font-weight:850;
          font-size:12px;
          white-space:nowrap;
        ">
          Export Modified RelPerm IXF
        </button>
      </div>

      <div style="
        color:#c7d7f2;
        font-size:12px;
        line-height:1.45;
        margin:8px 0 10px 0;
        padding:10px 12px;
        border-radius:14px;
        background:rgba(5,18,40,.64);
        border:1px solid rgba(120,190,255,.12);
      ">
        ${escapeHtml(payload.interpretation || "")}
        ${payload.risk_statement ? `<br><span style="color:#ffd18a">${escapeHtml(payload.risk_statement || "")}</span>` : ""}
      </div>

      <div id="${uid}" style="
        width:100%;
        height:640px;
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(80,165,255,.14);
        background:#020817;
      "></div>
    </div>
  `;

  if (!original.length || !proposed.length) {
    panel.innerHTML += `<div class="empty-state">No original/proposed RelPerm curve arrays were found.</div>`;
    return false;
  }

  const traces = [
    {
      type: "scattergl",
      mode: "lines+markers",
      name: "Original Krw",
      x: original.map(r => Number(r.saturation)),
      y: original.map(r => Number(r.value)),
      line: { color: "rgba(220,230,245,.68)", width: 2.8, dash: "dot" },
      marker: { size: 5, color: "rgba(220,230,245,.9)" },
      hovertemplate: "Original Krw<br>Sw: %{x:.5f}<br>Krw: %{y:.5f}<extra></extra>"
    },
    {
      type: "scattergl",
      mode: "lines+markers",
      name: "Proposed Krw",
      x: proposed.map(r => Number(r.saturation)),
      y: proposed.map(r => Number(r.value)),
      line: { color: "#55ff7a", width: 4.0 },
      marker: { size: 6, color: "#55ff7a" },
      hovertemplate: "Proposed Krw<br>Sw: %{x:.5f}<br>Krw: %{y:.5f}<extra></extra>"
    }
  ];

  Plotly.newPlot(uid, traces, {
    paper_bgcolor: "#020817",
    plot_bgcolor: "#020817",
    font: { color: "#d8e5ff", family: "Inter, Arial, sans-serif" },
    margin: { l: 72, r: 34, t: 24, b: 68 },
    xaxis: {
      title: { text: "Water saturation Sw", font: { size: 12, color: "#9fb3d9" } },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 }
    },
    yaxis: {
      title: { text: "Krw", font: { size: 12, color: "#9fb3d9" } },
      gridcolor: "rgba(120,190,255,.10)",
      zerolinecolor: "rgba(120,190,255,.13)",
      tickfont: { color: "#c7d7f2", size: 10 },
      rangemode: "tozero"
    },
    legend: {
      orientation: "h",
      x: 0,
      y: -0.15,
      bgcolor: "rgba(2,8,23,.68)",
      bordercolor: "rgba(120,190,255,.12)",
      borderwidth: 1,
      font: { size: 11, color: "#d8e5ff" }
    },
    hovermode: "closest"
  }, {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  const exportBtn = document.getElementById("relpermEvalExportV75");
  if (exportBtn) {
    exportBtn.onclick = () => exportRelPermIXFV75(well, exportBtn);
  }

  console.log("[V75] RelPerm curve evaluation rendered", {well, model, factor});
  return true;
}

async function exportRelPermIXFV75(well, button=null) {
  const btn = button;
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Generating IXF...";
  }

  try {
    const r = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
    const data = await r.json();

    if (!data.ok || !data.content) {
      alert(data.message || "RelPerm IXF export is not available for this well.");
      if (btn) {
        btn.disabled = false;
        btn.innerText = "Export Modified RelPerm IXF";
      }
      return false;
    }

    const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename || `RELPERM_${well}.ixf`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);

    if (btn) btn.innerText = "IXF exported";
    return true;

  } catch (e) {
    console.error("[V75] RelPerm IXF export failed", e);
    alert("RelPerm IXF export failed. Check console/logs.");
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Export Modified RelPerm IXF";
    }
    return false;
  }
}

function findBestActionAnchorV75() {
  // Prefer the same area where TRAN / multiplier buttons are rendered.
  const buttons = Array.from(document.querySelectorAll("button, a"))
    .filter(el => {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      return txt.includes("tran") || txt.includes("transmiss") || txt.includes("multiplier") || txt.includes("ixf");
    });

  for (const b of buttons) {
    let p = b.parentElement;
    for (let depth = 0; p && depth < 5; depth++, p = p.parentElement) {
      const txt = p.innerText || "";
      if (
        txt.includes("Recommended") ||
        txt.includes("Action") ||
        txt.includes("TRAN") ||
        txt.includes("Multiplier") ||
        txt.includes("Pattern-Aware")
      ) {
        return p;
      }
    }
  }

  // Fallback: use recommendation card / chat answer area.
  const cards = Array.from(document.querySelectorAll("div, section, article"))
    .filter(el => {
      const txt = el.innerText || "";
      return (
        txt.includes("Recommended") ||
        txt.includes("Pattern-Aware") ||
        txt.includes("Key Findings") ||
        txt.includes("Criticalities")
      );
    })
    .sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);

  return cards[0] || document.getElementById("chatAnswer") || document.getElementById("visualPanel") || document.body;
}

function buildRelPermActionInlinePanelV75(well, payload) {
  const model = payload.model || "";
  const curve = payload.curve_name || "Krw_v_Sw";
  const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
  const same = payload.impacted_wells_summary?.same_direction || [];
  const opp = payload.impacted_wells_summary?.opposite_direction || [];

  const box = document.createElement("div");
  box.className = "relperm-inline-action-v75";
  box.dataset.well = well;

  box.style.cssText = `
    margin-top: 10px;
    padding: 12px;
    border-radius: 14px;
    border: 1px solid rgba(85,255,122,.32);
    background: linear-gradient(180deg, rgba(8,36,34,.86), rgba(4,18,28,.94));
    box-shadow: inset 0 0 22px rgba(85,255,122,.05);
  `;

  box.innerHTML = `
    <div style="font-size:13px;font-weight:900;color:#d8ffe1;">
      RelPerm candidate available
    </div>
    <div style="font-size:12px;color:#9fb3d9;margin-top:3px;line-height:1.45;">
      Well: <b>${escapeHtml(well)}</b> · Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Uplift: <b>${escapeHtml(factor)}</b>` : ""}
      <br>
      Same-direction wells: <b>${escapeHtml(same.join(", ") || "None")}</b>
      ${opp.length ? `<br><span style="color:#ffd18a;">Risk: opposite-direction wells ${escapeHtml(opp.join(", "))}</span>` : ""}
    </div>

    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
      <button class="relperm-evaluate-v75" style="
        cursor:pointer;
        border:1px solid rgba(255,216,74,.42);
        background:rgba(130,95,10,.72);
        color:#fff2b3;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Evaluate RelPerm Curve
      </button>

      <button class="relperm-export-v75" style="
        cursor:pointer;
        border:1px solid rgba(85,255,122,.42);
        background:rgba(20,105,55,.74);
        color:#d8ffe1;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Export Modified RelPerm IXF
      </button>
    </div>
  `;

  box.querySelector(".relperm-evaluate-v75").onclick = () => {
    renderRelPermCurveEvaluationV75(payload);
  };

  box.querySelector(".relperm-export-v75").onclick = (ev) => {
    exportRelPermIXFV75(well, ev.currentTarget);
  };

  return box;
}

async function showRelPermInlineActionsV75(well) {
  if (!well) return false;

  const payload = await getRelPermCandidateV73(well);

  document.querySelectorAll(".relperm-inline-action-v75").forEach(x => x.remove());
  document.querySelectorAll(".relperm-global-panel-v74").forEach(x => x.remove());

  if (!payload || !payload.eligible) {
    console.log("[V75] RelPerm not eligible for", well, payload?.message || "");
    return false;
  }

  const anchor = findBestActionAnchorV75();
  const box = buildRelPermActionInlinePanelV75(well, payload);
  anchor.appendChild(box);

  console.log("[V75] RelPerm inline action panel added near recommendation/actions", {well, payload});
  return true;
}

// Replace floating/manual helpers with inline action behavior.
window.showRelPermInlineActionsV75 = showRelPermInlineActionsV75;
window.showRelPermGlobalPanelV74 = showRelPermInlineActionsV75;
window.showRelPermPanelForWellV73 = showRelPermInlineActionsV75;

// If Plotly click hook exists, make it use inline actions.
console.log("[V75] RelPerm action UX active. Test: await showRelPermInlineActionsV75('HW-28')");



// ==========================================================
// ROBUST WELL CLICK DETECTOR FOR RELPERM V76
// Reads well name from Plotly point text/customdata/hovertext/data arrays.
// ==========================================================

function normalizeWellNameV76(value) {
  if (value === null || value === undefined) return null;

  const s = String(value);
  const m = s.match(/\bHW[-_\s]?(\d+[A-Z]?)\b/i);

  if (m) return `HW-${String(m[1]).toUpperCase()}`;

  return null;
}

function findWellInAnyV76(obj, depth = 0) {
  if (depth > 5 || obj === null || obj === undefined) return null;

  if (typeof obj === "string" || typeof obj === "number") {
    return normalizeWellNameV76(obj);
  }

  if (Array.isArray(obj)) {
    for (const item of obj) {
      const w = findWellInAnyV76(item, depth + 1);
      if (w) return w;
    }
    return null;
  }

  if (typeof obj === "object") {
    // Prefer common Plotly fields first.
    for (const key of ["well", "name", "text", "hovertext", "label", "customdata"]) {
      if (key in obj) {
        const w = findWellInAnyV76(obj[key], depth + 1);
        if (w) return w;
      }
    }

    // Then search the rest.
    for (const key of Object.keys(obj)) {
      const w = findWellInAnyV76(obj[key], depth + 1);
      if (w) return w;
    }
  }

  return null;
}

function extractWellFromPlotlyClickV76(evt) {
  const p = evt?.points?.[0];

  if (!p) return null;

  // Direct fields
  let well =
    findWellInAnyV76(p.text) ||
    findWellInAnyV76(p.hovertext) ||
    findWellInAnyV76(p.customdata) ||
    findWellInAnyV76(p.data?.text) ||
    findWellInAnyV76(p.data?.hovertext) ||
    findWellInAnyV76(p.data?.customdata) ||
    findWellInAnyV76(p);

  return well;
}

function hookPlotlyRelPermClicksV76() {
  const plots = Array.from(document.querySelectorAll(".js-plotly-plot"));
  let hooked = 0;

  for (const plot of plots) {
    if (plot.dataset.relpermClickHookedV76 === "true") continue;

    plot.dataset.relpermClickHookedV76 = "true";
    hooked += 1;

    plot.on("plotly_click", function(evt) {
      try {
        const point = evt?.points?.[0];
        const well = extractWellFromPlotlyClickV76(evt);

        console.log("[V76] Plotly click payload:", {
          detected_well: well,
          point_text: point?.text,
          point_hovertext: point?.hovertext,
          point_customdata: point?.customdata,
          trace_name: point?.data?.name,
          curve_number: point?.curveNumber,
          point_number: point?.pointNumber
        });

        if (well) {
          window.lastSelectedWellV76 = well;

          if (typeof showRelPermInlineActionsV75 === "function") {
            showRelPermInlineActionsV75(well);
          } else if (typeof showRelPermGlobalPanelV74 === "function") {
            showRelPermGlobalPanelV74(well);
          }
        }

      } catch (e) {
        console.error("[V76] plotly_click handler failed", e);
      }
    });
  }

  if (hooked) {
    console.log("[V76] Hooked Plotly click detector on plots:", hooked);
  }
}

window.hookPlotlyRelPermClicksV76 = hookPlotlyRelPermClicksV76;

setTimeout(hookPlotlyRelPermClicksV76, 800);
setTimeout(hookPlotlyRelPermClicksV76, 1800);
setTimeout(hookPlotlyRelPermClicksV76, 3500);

document.addEventListener("click", function() {
  setTimeout(hookPlotlyRelPermClicksV76, 250);
}, true);

console.log("[V76] Robust RelPerm well click detector active");




// ==========================================================
// RELPERM WELL CARD INLINE ACTIONS V78
// Attaches RelPerm buttons directly inside the visible well card.
// No heavy observer; runs after dashboard clicks / manual call.
// ==========================================================

function extractWellFromTextV78(txt) {
  const m = String(txt || "").match(/\bHW[-_\s]?(\d+[A-Z]?)\b/i);
  return m ? `HW-${String(m[1]).toUpperCase()}` : null;
}

function findVisibleWellCardV78() {
  const nodes = Array.from(document.querySelectorAll("div, section, article"));

  const cards = nodes
    .filter(el => {
      const txt = el.innerText || "";
      return (
        /\bHW[-_\s]?\d+/i.test(txt) &&
        txt.includes("Overall HM") &&
        (
          txt.includes("Key Findings") ||
          txt.includes("Pattern-Aware Recommendation") ||
          txt.includes("Candidate model edit") ||
          txt.includes("Evaluate / Export IXF")
        )
      );
    })
    .sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);

  return cards[0] || null;
}

async function fetchRelPermCandidateV78(well) {
  try {
    const res = await fetch(`/api/relperm/sensitivity/${encodeURIComponent(well)}?ts=${Date.now()}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.warn("[V78] RelPerm candidate fetch failed", e);
    return null;
  }
}

function buildRelPermInlinePanelV78(well, payload) {
  const model = payload.model || "";
  const curve = payload.curve_name || "Krw_v_Sw";
  const factor = payload.factor ? `${Math.round(payload.factor * 1000) / 10}%` : "";
  const same = payload.impacted_wells_summary?.same_direction || [];
  const opp = payload.impacted_wells_summary?.opposite_direction || [];

  const box = document.createElement("div");
  box.className = "relperm-inline-panel-v78";
  box.dataset.well = well;

  box.style.cssText = `
    margin-top: 12px;
    padding: 12px;
    border-radius: 14px;
    border: 1px solid rgba(85,255,122,.34);
    background: linear-gradient(180deg, rgba(8,36,34,.88), rgba(4,18,28,.96));
    box-shadow: inset 0 0 22px rgba(85,255,122,.06);
  `;

  box.innerHTML = `
    <div style="font-size:13px;font-weight:900;color:#d8ffe1;margin-bottom:4px;">
      Candidate relperm edit
    </div>

    <div style="font-size:12px;color:#9fb3d9;line-height:1.45;margin-bottom:8px;">
      The agent found a mobility-based candidate for this well. 
      Model: <b>${escapeHtml(model)}</b> · Curve: <b>${escapeHtml(curve)}</b>${factor ? ` · Conservative uplift: <b>${escapeHtml(factor)}</b>` : ""}
      <br>
      Same-direction wells: <b>${escapeHtml(same.join(", ") || "None")}</b>
      ${opp.length ? `<br><span style="color:#ffd18a;">Risk: opposite-direction wells ${escapeHtml(opp.join(", "))}</span>` : ""}
    </div>

    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="relperm-evaluate-v78" style="
        cursor:pointer;
        border:1px solid rgba(255,216,74,.42);
        background:rgba(130,95,10,.74);
        color:#fff2b3;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Evaluate RelPerm Curve
      </button>

      <button class="relperm-export-v78" style="
        cursor:pointer;
        border:1px solid rgba(85,255,122,.42);
        background:rgba(20,105,55,.76);
        color:#d8ffe1;
        border-radius:12px;
        padding:8px 11px;
        font-weight:800;
        font-size:12px;
      ">
        Export Modified RelPerm IXF
      </button>
    </div>
  `;

  const evalBtn = box.querySelector(".relperm-evaluate-v78");
  const exportBtn = box.querySelector(".relperm-export-v78");

  evalBtn.onclick = function(ev) {
    ev.stopPropagation();

    if (typeof renderRelPermCurveEvaluationV75 === "function") {
      renderRelPermCurveEvaluationV75(payload);
      return;
    }

    const q = `evaluate Krw sensitivity for ${well}`;
    const input = document.getElementById("chatInput");
    if (input) input.value = q;

    if (typeof askChatV9 === "function") askChatV9(q);
    else if (typeof askChat === "function") askChat(q);
  };

  exportBtn.onclick = async function(ev) {
    ev.stopPropagation();

    if (typeof exportRelPermIXFV75 === "function") {
      await exportRelPermIXFV75(well, exportBtn);
      return;
    }

    exportBtn.disabled = true;
    exportBtn.innerText = "Generating IXF...";

    try {
      const r = await fetch(`/api/relperm/export-ixf/${encodeURIComponent(well)}?ts=${Date.now()}`);
      const data = await r.json();

      if (!data.ok || !data.content) {
        alert(data.message || "RelPerm IXF export is not available for this well.");
        exportBtn.disabled = false;
        exportBtn.innerText = "Export Modified RelPerm IXF";
        return;
      }

      const blob = new Blob([data.content], {type: "text/plain;charset=utf-8"});
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename || `RELPERM_${well}.ixf`;
      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(url);
      exportBtn.innerText = "IXF exported";

    } catch (e) {
      console.error("[V78] RelPerm IXF export failed", e);
      alert("RelPerm IXF export failed. Check console/logs.");
      exportBtn.disabled = false;
      exportBtn.innerText = "Export Modified RelPerm IXF";
    }
  };

  return box;
}

async function attachRelPermToVisibleWellCardV78() {
  const card = findVisibleWellCardV78();

  if (!card) {
    console.log("[V78] No visible well card found");
    return false;
  }

  const well = extractWellFromTextV78(card.innerText);

  if (!well) {
    console.log("[V78] Well card found, but no well name detected");
    return false;
  }

  // Remove old RelPerm panels in all cards.
  document.querySelectorAll(".relperm-inline-panel-v78").forEach(x => x.remove());
  document.querySelectorAll(".relperm-global-panel-v74").forEach(x => x.remove());

  const payload = await fetchRelPermCandidateV78(well);

  if (!payload || !payload.eligible) {
    console.log("[V78] RelPerm not eligible for", well, payload?.message || "");
    return false;
  }

  const panel = buildRelPermInlinePanelV78(well, payload);

  // Put it after the existing action/edit area if possible.
  const actionHeaders = Array.from(card.querySelectorAll("div, p, span, h1, h2, h3, h4"))
    .filter(el => {
      const t = el.innerText || "";
      return t.includes("Candidate model edit") || t.includes("Evaluate / Export IXF");
    });

  if (actionHeaders.length) {
    const anchor = actionHeaders[actionHeaders.length - 1];
    const parent = anchor.parentElement || card;
    parent.appendChild(panel);
  } else {
    card.appendChild(panel);
  }

  console.log("[V78] RelPerm inline panel attached to visible well card", {well, payload});
  return true;
}

window.attachRelPermToVisibleWellCardV78 = attachRelPermToVisibleWellCardV78;

// Lightweight: run only after user click, not on every DOM mutation.
if (!window.__relpermWellCardClickV78) {
  document.addEventListener("click", function() {
    setTimeout(() => {
      attachRelPermToVisibleWellCardV78();
    }, 350);
  }, true);

  window.__relpermWellCardClickV78 = true;
  console.log("[V78] RelPerm well-card inline action hook active. Manual test: await attachRelPermToVisibleWellCardV78()");
}
