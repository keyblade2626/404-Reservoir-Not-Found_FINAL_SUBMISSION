
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */
window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER = true;
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */


async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

async function postJson(url, payload) {
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

function fmt(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  if (typeof v === "number") return Number(v).toFixed(1);
  return v;
}

function renderCards(data) {
  const el = document.getElementById("cards");
  el.innerHTML = "";

  data.cards.forEach(c => {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <div class="label">${c.label}</div>
      <div class="score" style="color:${c.color}">${fmt(c.score)}</div>
      <div class="class" style="color:${c.color}">${c.class || ""}</div>
    `;
    el.appendChild(div);
  });
}

async function loadSummary() {
  const data = await getJson("/api/dashboard/summary");
  renderCards(data);
}

function scale(v, min, max, outMin, outMax) {
  if (max === min) return (outMin + outMax) / 2;
  return outMin + (v - min) * (outMax - outMin) / (max - min);
}

async function loadMap() {
  const variable = document.getElementById("variableSelect").value;
  const data = await getJson(`/api/dashboard/wells?variable=${variable}`);
  drawMap(data.wells, variable);
}

function drawMap(wells, variable) {
  const el = document.getElementById("map");

  if (!wells || wells.length === 0) {
    el.innerHTML = "<p style='padding:20px;color:#94a3b8'>No well data available.</p>";
    return;
  }

  const width = 1000;
  const height = 620;
  const pad = 50;

  const xs = wells.map(w => w.i);
  const ys = wells.map(w => w.j);

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  let svg = `<svg viewBox="0 0 ${width} ${height}">`;

  svg += `<text x="30" y="32" fill="#94a3b8" font-size="16">Variable: ${variable.toUpperCase()}</text>`;

  wells.forEach(w => {
    const x = scale(w.i, minX, maxX, pad, width - pad);
    const y = scale(w.j, minY, maxY, pad, height - pad);

    const radius = w.class === "Inactive" ? 8 : 11;

    svg += `
      <g onclick="selectWell('${w.well}')" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="${radius}" fill="${w.color}" stroke="#ffffff" stroke-width="1.5" opacity="0.95"></circle>
        <text x="${x + 13}" y="${y + 4}" class="well-label">${w.well}</text>
        <title>${w.well} | ${variable}: ${fmt(w.score)} | ${w.class}</title>
      </g>
    `;
  });

  svg += `</svg>`;
  el.innerHTML = svg;
}

function badgeClass(score) {
  let cls = "Inactive";
  let color = "#64748b";
  if (score !== null && score !== undefined) {
    if (score >= 80) { cls = "Good"; color = "#22c55e"; }
    else if (score >= 60) { cls = "Fair"; color = "#facc15"; }
    else { cls = "Poor"; color = "#ef4444"; }
  }
  return `<span class="badge" style="background:${color}">${cls}</span>`;
}

async function selectWell(well) {
  const data = await getJson(`/api/dashboard/well/${well}`);
  renderWellDetail(data);
}

function renderWellDetail(data) {
  const el = document.getElementById("detail");

  if (!data.found) {
    el.innerHTML = "Well not found.";
    return;
  }

  const scores = data.scores || {};
  const waterDiag = data.water_diagnosis || {};
  const corridor = data.corridor || null;

  el.innerHTML = `
    <h3>${data.well}</h3>
    <div class="score-row"><span>Overall</span><strong>${fmt(scores.overall)}</strong>${badgeClass(scores.overall)}</div>
    <div class="score-row"><span>Oil</span><strong>${fmt(scores.oil)}</strong>${badgeClass(scores.oil)}</div>
    <div class="score-row"><span>Water</span><strong>${fmt(scores.water)}</strong>${badgeClass(scores.water)}</div>
    <div class="score-row"><span>Gas</span><strong>${fmt(scores.gas)}</strong>${badgeClass(scores.gas)}</div>
    <div class="score-row"><span>BHP</span><strong>${fmt(scores.bhp)}</strong>${badgeClass(scores.bhp)}</div>

    <h4>Main Diagnosis</h4>
    <p><b>Water driver:</b> ${waterDiag.primary_driver || "N/A"}</p>
    <p><b>Action:</b> ${waterDiag.recommended_action || "N/A"}</p>

    <h4>Corridor</h4>
    <p>${corridor ? `${corridor.multiplier_direction || ""} TRAN | cells: ${corridor.candidate_cell_count || "N/A"}` : "No corridor candidate available."}</p>
  `;
}

function renderTable(items) {
  if (!items || items.length === 0) return "<p>No rows.</p>";

  let html = `<table class="table"><thead><tr>`;
  Object.keys(items[0]).forEach(k => html += `<th>${k}</th>`);
  html += `</tr></thead><tbody>`;

  items.forEach(row => {
    html += `<tr>`;
    Object.values(row).forEach(v => html += `<td>${fmt(v)}</td>`);
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  return html;
}

async function sendChat() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;

  const data = await postJson("/api/agent-chat-v501", {message: msg});

  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  answer.innerHTML = `<p>${data.answer}</p>`;

  if (data.type === "summary") {
    renderCards(data.data);
    visual.innerHTML = `<p>Summary cards updated.</p>`;
  }

  else if (data.type === "ranking") {
    answer.innerHTML += renderTable(data.data.items);
    visual.innerHTML = `<p>Ranking generated for ${data.data.variable} mismatch.</p>`;
  }

  else if (data.type === "well_detail") {
    renderWellDetail(data.data);
    visual.innerHTML = `<p>Well detail loaded for ${data.data.well}.</p>`;
  }

  else if (data.type === "area") {
    answer.innerHTML += `<h4>${data.data.area.toUpperCase()} area</h4>`;
    answer.innerHTML += renderTable([
      {metric: "well_count", value: data.data.well_count},
      {metric: "overall", value: data.data.summary.overall},
      {metric: "water", value: data.data.summary.water},
      {metric: "bhp", value: data.data.summary.bhp},
    ]);
    answer.innerHTML += `<h4>Worst water wells</h4>`;
    answer.innerHTML += renderTable(data.data.top_water_mismatches);
    visual.innerHTML = `<p>Area summary generated.</p>`;
  }

  else if (data.type === "corridors") {
    answer.innerHTML += renderTable(data.data.summary);
    if (data.data.map_url) {
      visual.innerHTML = `<img src="${data.data.map_url}" />`;
    } else {
      visual.innerHTML = `<p>No corridor map found.</p>`;
    }
  }

  else if (data.type === "profile_plot") {
    answer.innerHTML += `
      <p><b>Well:</b> ${data.data.well}</p>
      <p><b>Variable:</b> ${data.data.variable}</p>
      <p><b>Sim key:</b> ${data.data.sim_key || "N/A"}</p>
      <p><b>Hist key:</b> ${data.data.hist_key || "N/A"}</p>
    `;

    if (data.data.image_url) {
      visual.innerHTML = `<img src="${data.data.image_url}?t=${Date.now()}" />`;
    } else {
      visual.innerHTML = `<p>No plot image generated.</p>`;
    }
  }


  else if (data.type === "profile_series") {
    answer.innerHTML += `
      <p><b>Well:</b> ${data.data.well}</p>
      <p><b>Variable:</b> ${data.data.variable}</p>
    `;
    renderProfileSeries(data.data);
  }


  else {
    visual.innerHTML = `<p>Try a specific question about HM quality, WCT mismatch, transmissibility corridors, area south, or a well name.</p>`;
  }
}

async function runDiagnostics() {
  const answer = document.getElementById("chatAnswer");
  answer.innerHTML = "<p>Running diagnostics... this can take a bit depending on the case.</p>";

  const data = await postJson("/api/run-diagnostics", {});
  answer.innerHTML = `<p>Pipeline status: <b>${data.status}</b>. Runtime: ${data.seconds}s</p>`;

  await 
function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series.ok) {
    visual.innerHTML = `<p>${series.message || "Profile series not available."}</p>`;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    const traces = panel.traces.map(t => ({
      x: t.x,
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 60, r: 25, t: 50, b: 50 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      yaxis: {
        title: panel.y_title,
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    Plotly.newPlot(div.id, traces, layout, config);
  });
}



function renderSimpleSvgPlot(panel, targetId) {
  const el = document.getElementById(targetId);
  const width = 900;
  const height = 330;
  const padL = 60;
  const padR = 25;
  const padT = 35;
  const padB = 45;

  const allY = [];
  panel.traces.forEach(t => {
    (t.y || []).forEach(v => {
      if (v !== null && v !== undefined && isFinite(v)) allY.push(Number(v));
    });
  });

  if (allY.length === 0) {
    el.innerHTML = `<p style="color:#94a3b8;padding:20px">No numeric data available for ${panel.title}</p>`;
    return;
  }

  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const ySpan = Math.max(yMax - yMin, 1e-9);

  const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));

  function sx(i) {
    if (maxN <= 1) return padL;
    return padL + i * (width - padL - padR) / (maxN - 1);
  }

  function sy(v) {
    return height - padB - (Number(v) - yMin) * (height - padT - padB) / ySpan;
  }

  const colors = ["#38bdf8", "#f97316", "#22c55e", "#e879f9"];

  let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;display:block">`;
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="rgba(2,6,23,0.55)"/>`;
  svg += `<text x="${padL}" y="23" fill="#e5e7eb" font-size="16" font-weight="700">${panel.title}</text>`;

  // grid
  for (let k = 0; k <= 5; k++) {
    const y = padT + k * (height - padT - padB) / 5;
    svg += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(148,163,184,0.18)" />`;
  }

  panel.traces.forEach((t, idx) => {
    const y = t.y || [];
    let d = "";
    y.forEach((v, i) => {
      if (v === null || v === undefined || !isFinite(v)) return;
      const x = sx(i);
      const yy = sy(v);
      d += d === "" ? `M ${x} ${yy}` : ` L ${x} ${yy}`;
    });

    const dash = (t.dash || "").includes("dash") ? 'stroke-dasharray="8 6"' : "";
    const color = colors[idx % colors.length];

    svg += `<path d="${d}" fill="none" stroke="${color}" stroke-width="3" ${dash}/>`;
    svg += `<circle cx="${padL + idx*150}" cy="${height-18}" r="5" fill="${color}"/>`;
    svg += `<text x="${padL + 10 + idx*150}" y="${height-14}" fill="#cbd5e1" font-size="12">${t.name}</text>`;
  });

  svg += `<text x="${padL}" y="${height-32}" fill="#94a3b8" font-size="11">Fallback SVG chart - Plotly not loaded</text>`;
  svg += `</svg>`;

  el.innerHTML = svg;
}


function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series || !series.ok) {
    visual.innerHTML = `<p>${series && series.message ? series.message : "Profile series not available."}</p>`;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable)}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  if (!series.panels || series.panels.length === 0) {
    container.innerHTML = `<p style="color:#94a3b8">No panels available for this profile.</p>`;
    return;
  }

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    // If Plotly did not load, use the internal SVG fallback.
    if (typeof Plotly === "undefined") {
      renderSimpleSvgPlot(panel, div.id);
      return;
    }

    const traces = panel.traces.map(t => ({
      x: t.x,
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 60, r: 25, t: 50, b: 50 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      yaxis: {
        title: panel.y_title,
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    Plotly.newPlot(div.id, traces, layout, config);
  });
}



function hasNumericData(panel) {
  if (!panel || !panel.traces) return false;

  for (const t of panel.traces) {
    for (const v of (t.y || [])) {
      if (v !== null && v !== undefined && isFinite(Number(v))) {
        return true;
      }
    }
  }

  return false;
}


function renderSimpleSvgPlot(panel, targetId) {
  const el = document.getElementById(targetId);
  const width = 900;
  const height = 330;
  const padL = 65;
  const padR = 30;
  const padT = 42;
  const padB = 48;

  const allY = [];

  panel.traces.forEach(t => {
    (t.y || []).forEach(v => {
      if (v !== null && v !== undefined && isFinite(Number(v))) {
        allY.push(Number(v));
      }
    });
  });

  if (allY.length === 0) {
    el.innerHTML = `
      <div style="padding:24px;color:#94a3b8">
        <b>${panel.title}</b><br/>
        No numeric data available for this panel.
      </div>
    `;
    return;
  }

  let yMin = Math.min(...allY);
  let yMax = Math.max(...allY);

  if (Math.abs(yMax - yMin) < 1e-12) {
    yMax = yMax + 1;
    yMin = yMin - 1;
  }

  const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));

  function sx(i) {
    if (maxN <= 1) return padL;
    return padL + i * (width - padL - padR) / (maxN - 1);
  }

  function sy(v) {
    return height - padB - (Number(v) - yMin) * (height - padT - padB) / (yMax - yMin);
  }

  const colors = ["#38bdf8", "#f97316", "#22c55e", "#e879f9"];

  let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;display:block">`;

  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="rgba(2,6,23,0.55)"/>`;
  svg += `<text x="${padL}" y="26" fill="#e5e7eb" font-size="16" font-weight="700">${panel.title}</text>`;

  for (let k = 0; k <= 5; k++) {
    const y = padT + k * (height - padT - padB) / 5;
    svg += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(148,163,184,0.18)" />`;

    const val = yMax - k * (yMax - yMin) / 5;
    svg += `<text x="8" y="${y + 4}" fill="#94a3b8" font-size="11">${val.toFixed(2)}</text>`;
  }

  panel.traces.forEach((t, idx) => {
    const y = t.y || [];
    let d = "";

    y.forEach((v, i) => {
      if (v === null || v === undefined || !isFinite(Number(v))) return;

      const x = sx(i);
      const yy = sy(v);

      d += d === "" ? `M ${x} ${yy}` : ` L ${x} ${yy}`;
    });

    const dash = (t.dash || "").includes("dash") ? 'stroke-dasharray="9 7"' : "";
    const color = colors[idx % colors.length];

    svg += `<path d="${d}" fill="none" stroke="${color}" stroke-width="3" ${dash}/>`;
    svg += `<circle cx="${padL + idx*170}" cy="${height-20}" r="5" fill="${color}"/>`;
    svg += `<text x="${padL + 10 + idx*170}" y="${height-16}" fill="#cbd5e1" font-size="12">${t.name}</text>`;
  });

  svg += `</svg>`;
  el.innerHTML = svg;
}


function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  console.log("PROFILE SERIES RECEIVED:", series);

  if (!series || !series.ok) {
    visual.innerHTML = `
      <div style="color:#fca5a5">
        <b>Profile not available.</b><br/>
        ${series && series.message ? series.message : "No profile data returned by backend."}
      </div>
    `;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable)}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  if (!series.panels || series.panels.length === 0) {
    container.innerHTML = `<p style="color:#94a3b8">No panels available for this profile.</p>`;
    return;
  }

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    const numeric = hasNumericData(panel);

    if (!numeric) {
      div.innerHTML = `
        <div style="padding:24px;color:#94a3b8">
          <b>${panel.title}</b><br/>
          No numeric data available in this panel.
        </div>
      `;
      return;
    }

    // Use numeric x index to avoid date parsing issues.
    const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));
    const xIndex = Array.from({length: maxN}, (_, i) => i + 1);

    if (typeof Plotly === "undefined") {
      console.warn("Plotly not loaded. Using SVG fallback.");
      renderSimpleSvgPlot(panel, div.id);
      return;
    }

    const traces = panel.traces.map(t => ({
      x: (t.x && t.x.length > 0) ? t.x : xIndex.slice(0, (t.y || []).length),
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 65, r: 25, t: 50, b: 55 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)",
        title: "Time"
      },
      yaxis: {
        title: panel.y_title || "",
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    try {
      Plotly.newPlot(div.id, traces, layout, config);
    } catch (err) {
      console.error("Plotly rendering failed:", err);
      renderSimpleSvgPlot(panel, div.id);
    }
  });
}



function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series) {
    visual.innerHTML = `<p>No profile data returned.</p>`;
    return;
  }

  const fallback = series.fallback_plot || {};
  const imageUrl = fallback.image_url;

  let html = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable + " profile")}</h3>
      <p>Sim key: ${series.sim_key || fallback.sim_key || "N/A"} | Hist key: ${series.hist_key || fallback.hist_key || "N/A"}</p>
    </div>
  `;

  if (imageUrl) {
    html += `
      <div class="png-plot-card">
        <img src="${imageUrl}?t=${Date.now()}" class="profile-img" />
      </div>
    `;
  } else if (!series.ok) {
    html += `
      <div style="color:#fca5a5;padding:16px">
        <b>Profile not available.</b><br/>
        ${series.message || "No image or time-series data available."}
      </div>
    `;
  } else {
    html += `
      <div style="color:#94a3b8;padding:16px">
        Profile data is available, but no fallback image was generated.
      </div>
    `;
  }

  visual.innerHTML = html;
}


loadAll();
loadAgentFlow();
}

async function loadAll() {
  await loadSummary();
  await loadMap();
}


function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series.ok) {
    visual.innerHTML = `<p>${series.message || "Profile series not available."}</p>`;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    const traces = panel.traces.map(t => ({
      x: t.x,
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 60, r: 25, t: 50, b: 50 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      yaxis: {
        title: panel.y_title,
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    Plotly.newPlot(div.id, traces, layout, config);
  });
}



function renderSimpleSvgPlot(panel, targetId) {
  const el = document.getElementById(targetId);
  const width = 900;
  const height = 330;
  const padL = 60;
  const padR = 25;
  const padT = 35;
  const padB = 45;

  const allY = [];
  panel.traces.forEach(t => {
    (t.y || []).forEach(v => {
      if (v !== null && v !== undefined && isFinite(v)) allY.push(Number(v));
    });
  });

  if (allY.length === 0) {
    el.innerHTML = `<p style="color:#94a3b8;padding:20px">No numeric data available for ${panel.title}</p>`;
    return;
  }

  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const ySpan = Math.max(yMax - yMin, 1e-9);

  const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));

  function sx(i) {
    if (maxN <= 1) return padL;
    return padL + i * (width - padL - padR) / (maxN - 1);
  }

  function sy(v) {
    return height - padB - (Number(v) - yMin) * (height - padT - padB) / ySpan;
  }

  const colors = ["#38bdf8", "#f97316", "#22c55e", "#e879f9"];

  let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;display:block">`;
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="rgba(2,6,23,0.55)"/>`;
  svg += `<text x="${padL}" y="23" fill="#e5e7eb" font-size="16" font-weight="700">${panel.title}</text>`;

  // grid
  for (let k = 0; k <= 5; k++) {
    const y = padT + k * (height - padT - padB) / 5;
    svg += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(148,163,184,0.18)" />`;
  }

  panel.traces.forEach((t, idx) => {
    const y = t.y || [];
    let d = "";
    y.forEach((v, i) => {
      if (v === null || v === undefined || !isFinite(v)) return;
      const x = sx(i);
      const yy = sy(v);
      d += d === "" ? `M ${x} ${yy}` : ` L ${x} ${yy}`;
    });

    const dash = (t.dash || "").includes("dash") ? 'stroke-dasharray="8 6"' : "";
    const color = colors[idx % colors.length];

    svg += `<path d="${d}" fill="none" stroke="${color}" stroke-width="3" ${dash}/>`;
    svg += `<circle cx="${padL + idx*150}" cy="${height-18}" r="5" fill="${color}"/>`;
    svg += `<text x="${padL + 10 + idx*150}" y="${height-14}" fill="#cbd5e1" font-size="12">${t.name}</text>`;
  });

  svg += `<text x="${padL}" y="${height-32}" fill="#94a3b8" font-size="11">Fallback SVG chart - Plotly not loaded</text>`;
  svg += `</svg>`;

  el.innerHTML = svg;
}


function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series || !series.ok) {
    visual.innerHTML = `<p>${series && series.message ? series.message : "Profile series not available."}</p>`;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable)}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  if (!series.panels || series.panels.length === 0) {
    container.innerHTML = `<p style="color:#94a3b8">No panels available for this profile.</p>`;
    return;
  }

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    // If Plotly did not load, use the internal SVG fallback.
    if (typeof Plotly === "undefined") {
      renderSimpleSvgPlot(panel, div.id);
      return;
    }

    const traces = panel.traces.map(t => ({
      x: t.x,
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 60, r: 25, t: 50, b: 50 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      yaxis: {
        title: panel.y_title,
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    Plotly.newPlot(div.id, traces, layout, config);
  });
}



function hasNumericData(panel) {
  if (!panel || !panel.traces) return false;

  for (const t of panel.traces) {
    for (const v of (t.y || [])) {
      if (v !== null && v !== undefined && isFinite(Number(v))) {
        return true;
      }
    }
  }

  return false;
}


function renderSimpleSvgPlot(panel, targetId) {
  const el = document.getElementById(targetId);
  const width = 900;
  const height = 330;
  const padL = 65;
  const padR = 30;
  const padT = 42;
  const padB = 48;

  const allY = [];

  panel.traces.forEach(t => {
    (t.y || []).forEach(v => {
      if (v !== null && v !== undefined && isFinite(Number(v))) {
        allY.push(Number(v));
      }
    });
  });

  if (allY.length === 0) {
    el.innerHTML = `
      <div style="padding:24px;color:#94a3b8">
        <b>${panel.title}</b><br/>
        No numeric data available for this panel.
      </div>
    `;
    return;
  }

  let yMin = Math.min(...allY);
  let yMax = Math.max(...allY);

  if (Math.abs(yMax - yMin) < 1e-12) {
    yMax = yMax + 1;
    yMin = yMin - 1;
  }

  const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));

  function sx(i) {
    if (maxN <= 1) return padL;
    return padL + i * (width - padL - padR) / (maxN - 1);
  }

  function sy(v) {
    return height - padB - (Number(v) - yMin) * (height - padT - padB) / (yMax - yMin);
  }

  const colors = ["#38bdf8", "#f97316", "#22c55e", "#e879f9"];

  let svg = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;height:100%;display:block">`;

  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="rgba(2,6,23,0.55)"/>`;
  svg += `<text x="${padL}" y="26" fill="#e5e7eb" font-size="16" font-weight="700">${panel.title}</text>`;

  for (let k = 0; k <= 5; k++) {
    const y = padT + k * (height - padT - padB) / 5;
    svg += `<line x1="${padL}" y1="${y}" x2="${width-padR}" y2="${y}" stroke="rgba(148,163,184,0.18)" />`;

    const val = yMax - k * (yMax - yMin) / 5;
    svg += `<text x="8" y="${y + 4}" fill="#94a3b8" font-size="11">${val.toFixed(2)}</text>`;
  }

  panel.traces.forEach((t, idx) => {
    const y = t.y || [];
    let d = "";

    y.forEach((v, i) => {
      if (v === null || v === undefined || !isFinite(Number(v))) return;

      const x = sx(i);
      const yy = sy(v);

      d += d === "" ? `M ${x} ${yy}` : ` L ${x} ${yy}`;
    });

    const dash = (t.dash || "").includes("dash") ? 'stroke-dasharray="9 7"' : "";
    const color = colors[idx % colors.length];

    svg += `<path d="${d}" fill="none" stroke="${color}" stroke-width="3" ${dash}/>`;
    svg += `<circle cx="${padL + idx*170}" cy="${height-20}" r="5" fill="${color}"/>`;
    svg += `<text x="${padL + 10 + idx*170}" y="${height-16}" fill="#cbd5e1" font-size="12">${t.name}</text>`;
  });

  svg += `</svg>`;
  el.innerHTML = svg;
}


function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  console.log("PROFILE SERIES RECEIVED:", series);

  if (!series || !series.ok) {
    visual.innerHTML = `
      <div style="color:#fca5a5">
        <b>Profile not available.</b><br/>
        ${series && series.message ? series.message : "No profile data returned by backend."}
      </div>
    `;
    return;
  }

  visual.innerHTML = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable)}</h3>
      <p>Sim key: ${series.sim_key || "N/A"} | Hist key: ${series.hist_key || "N/A"}</p>
    </div>
    <div id="profilePlots"></div>
  `;

  const container = document.getElementById("profilePlots");

  if (!series.panels || series.panels.length === 0) {
    container.innerHTML = `<p style="color:#94a3b8">No panels available for this profile.</p>`;
    return;
  }

  series.panels.forEach((panel, idx) => {
    const div = document.createElement("div");
    div.id = `plotly_profile_${idx}`;
    div.className = "plotly-box";
    container.appendChild(div);

    const numeric = hasNumericData(panel);

    if (!numeric) {
      div.innerHTML = `
        <div style="padding:24px;color:#94a3b8">
          <b>${panel.title}</b><br/>
          No numeric data available in this panel.
        </div>
      `;
      return;
    }

    // Use numeric x index to avoid date parsing issues.
    const maxN = Math.max(...panel.traces.map(t => (t.y || []).length));
    const xIndex = Array.from({length: maxN}, (_, i) => i + 1);

    if (typeof Plotly === "undefined") {
      console.warn("Plotly not loaded. Using SVG fallback.");
      renderSimpleSvgPlot(panel, div.id);
      return;
    }

    const traces = panel.traces.map(t => ({
      x: (t.x && t.x.length > 0) ? t.x : xIndex.slice(0, (t.y || []).length),
      y: t.y,
      type: "scatter",
      mode: "lines",
      name: t.name,
      line: {
        width: 3,
        dash: t.dash || "solid"
      }
    }));

    const layout = {
      title: {
        text: panel.title,
        font: { color: "#e5e7eb", size: 16 }
      },
      paper_bgcolor: "rgba(15, 23, 42, 0)",
      plot_bgcolor: "rgba(2, 6, 23, 0.45)",
      font: { color: "#e5e7eb" },
      margin: { l: 65, r: 25, t: 50, b: 55 },
      xaxis: {
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)",
        title: "Time"
      },
      yaxis: {
        title: panel.y_title || "",
        gridcolor: "rgba(148, 163, 184, 0.18)",
        zerolinecolor: "rgba(148, 163, 184, 0.18)"
      },
      legend: {
        orientation: "h",
        y: -0.25
      },
      hovermode: "x unified"
    };

    const config = {
      responsive: true,
      displaylogo: false
    };

    try {
      Plotly.newPlot(div.id, traces, layout, config);
    } catch (err) {
      console.error("Plotly rendering failed:", err);
      renderSimpleSvgPlot(panel, div.id);
    }
  });
}



function renderProfileSeries(series) {
  const visual = document.getElementById("visualPanel");

  if (!series) {
    visual.innerHTML = `<p>No profile data returned.</p>`;
    return;
  }

  const fallback = series.fallback_plot || {};
  const imageUrl = fallback.image_url;

  let html = `
    <div class="plot-header">
      <h3>${series.title || (series.well + " - " + series.variable + " profile")}</h3>
      <p>Sim key: ${series.sim_key || fallback.sim_key || "N/A"} | Hist key: ${series.hist_key || fallback.hist_key || "N/A"}</p>
    </div>
  `;

  if (imageUrl) {
    html += `
      <div class="png-plot-card">
        <img src="${imageUrl}?t=${Date.now()}" class="profile-img" />
      </div>
    `;
  } else if (!series.ok) {
    html += `
      <div style="color:#fca5a5;padding:16px">
        <b>Profile not available.</b><br/>
        ${series.message || "No image or time-series data available."}
      </div>
    `;
  } else {
    html += `
      <div style="color:#94a3b8;padding:16px">
        Profile data is available, but no fallback image was generated.
      </div>
    `;
  }

  visual.innerHTML = html;
}


loadAll();
loadAgentFlow();



// ==========================================================
// HM MAP V2 - active producers by default + optional injectors
// ==========================================================

let hmMapPayload = null;

function hmClassColor(hmClass) {
  const c = (hmClass || "").toLowerCase();

  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
}

function hmScoreLabel(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  const n = Number(value);
  if (!isFinite(n)) return "N/A";
  return n.toFixed(1);
}

async function loadHmMapPayload() {
  try {
    const resp = await fetch("/api/dashboard/hm-map");
    hmMapPayload = await resp.json();
    renderHmMap();
  } catch (err) {
    const panel = document.getElementById("map");
    if (panel) {
      panel.innerHTML = `<p style="padding:20px;color:#fca5a5">Failed to load HM map payload: ${err}</p>`;
    }
  }
}

// Override previous loadMap() implementation.
// This keeps compatibility with existing loadAll().
async function loadMap() {
  await loadHmMapPayload();
}

function renderHmMap() {
  const panel = document.getElementById("map");

  if (!panel) return;

  if (!hmMapPayload || !hmMapPayload.wells) {
    panel.innerHTML = `<p style="padding:20px;color:#94a3b8">HM map payload not available.</p>`;
    return;
  }

  const showInjectors = document.getElementById("toggleInjectors")?.checked || false;
  const showInactive = document.getElementById("toggleInactiveProducers")?.checked || false;
  const variable = document.getElementById("hmVariableSelect")?.value || "overall";

  let wells = hmMapPayload.wells.filter(w => {
    if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) return false;

    if (w.well_role === "producer") {
      if (!showInactive && !w.is_active_hm) return false;
      return true;
    }

    if (w.well_role === "injector") {
      return showInjectors;
    }

    return false;
  });

  if (wells.length === 0) {
    panel.innerHTML = `<p style="padding:20px;color:#94a3b8">No wells available for current filters.</p>`;
    return;
  }

  const iVals = wells.map(w => Number(w.i)).filter(v => isFinite(v));
  const jVals = wells.map(w => Number(w.j)).filter(v => isFinite(v));

  const minI = Math.min(...iVals);
  const maxI = Math.max(...iVals);
  const minJ = Math.min(...jVals);
  const maxJ = Math.max(...jVals);

  const W = 1000;
  const H = 640;
  const pad = 58;

  function sx(i) {
    if (maxI === minI) return W / 2;
    return pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  }

  function sy(j) {
    if (maxJ === minJ) return H / 2;
    // J grows downward, so keep it visually downward.
    return pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);
  }

  const label = {
    overall: "Overall HM",
    oil: "Oil HM",
    water: "Water HM",
    gas: "Gas HM",
    bhp: "BHP HM",
  }[variable] || "Overall HM";

  let svg = `
    <div class="hm-map-wrapper">
      <svg viewBox="0 0 ${W} ${H}" class="hm-map-svg">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3.5" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <text x="32" y="35" fill="#e5e7eb" font-size="18" font-weight="700">History Match Map</text>
        <text x="32" y="58" fill="#94a3b8" font-size="12">${label} | active producers by default | injectors optional</text>
        <text x="${W - 32}" y="35" fill="#5eead4" font-size="12" text-anchor="end">404 Reservoir Not Found</text>
  `;

  // grid
  for (let k = 0; k < 9; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    svg += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(148,163,184,0.12)" />`;
    svg += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(148,163,184,0.12)" />`;
  }

  wells.forEach(w => {
    const x = sx(w.i);
    const y = sy(w.j);

    const cls = w[`${variable}_class`] || w["overall_class"] || "Inactive";
    const score = w[`${variable}_score`] ?? w["overall_score"];
    const color = hmClassColor(cls);

    const opacity = w.is_active_hm ? 1.0 : 0.55;

    let shape = "";

    if (w.well_role === "injector") {
      shape = `
        <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                 fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#glow)" />
      `;
    } else {
      shape = `
        <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#glow)" />
      `;
    }

    svg += `
      <g onclick="selectWell('${w.well}')" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity="0.14" />
        ${shape}
        <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
        <title>${w.well}
Role: ${w.well_role}
Active HM: ${w.is_active_hm}
Evaluated: ${w.is_evaluated_hm}
${label}: ${hmScoreLabel(score)}
Class: ${cls}</title>
      </g>
    `;
  });

  svg += `
      </svg>

      <div class="hm-legend">
        <span><span class="hm-legend-dot" style="background:#22c55e"></span>Good</span>
        <span><span class="hm-legend-dot" style="background:#facc15"></span>Fair</span>
        <span><span class="hm-legend-dot" style="background:#ef4444"></span>Poor</span>
        <span><span class="hm-legend-dot" style="background:#94a3b8"></span>Inactive / not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
      </div>
    </div>
  `;

  panel.innerHTML = svg;
}

function bindHmControls() {
  document.getElementById("toggleInjectors")?.addEventListener("change", renderHmMap);
  document.getElementById("toggleInactiveProducers")?.addEventListener("change", renderHmMap);
  document.getElementById("hmVariableSelect")?.addEventListener("change", renderHmMap);
}

// Bind controls after the page is ready.
setTimeout(() => {
  bindHmControls();
  loadHmMapPayload();
}, 250);



// ==========================================================
// AGENT FLOW PANEL
// ==========================================================


async function loadAgentFlow() {
  const el = document.getElementById("agentFlow");
  if (!el) return;

  try {
    const resp = await fetch("/api/agents/logs?limit=200");
    const data = await resp.json();
    const logs = data.logs || [];

    if (logs.length === 0) {
      el.innerHTML = `<p style="color:#94a3b8">No agent logs available yet. Run diagnostics first.</p>`;
      return;
    }

    const agentOrder = [
      "Agent Orchestrator",
      "Data Ingestion Agent",
      "HM Scoring Agent",
      "Well Activity Classification Agent",
      "Profile Diagnostics Agent",
      "BHP Observed Data Filter Agent",
      "Injection HM Agent",
      "Streamline Alignment Agent",
      "Injector-Producer Context Agent",
      "Reservoir Diagnosis Agent",
      "Recommendation Agent",
      "Visualization Agent",
      "Chat Copilot Agent"
    ];

    const latestByAgent = {};

    logs.forEach(item => {
      if (!item.agent) return;
      latestByAgent[item.agent] = item;
    });

    const summaryRows = agentOrder
      .filter(agent => latestByAgent[agent])
      .map(agent => {
        const item = latestByAgent[agent];
        const status = (item.status || "info").toLowerCase();
        const statusClass = ["success", "failed", "running", "warning", "skipped"].includes(status) ? status : "info";

        const handoff = item.handoff_to ? ` → ${item.handoff_to}` : "";
        const outputs = (item.outputs || []).slice(0, 2).join(", ");

        return `
          <div class="agent-row compact">
            <div class="agent-name">${agent}</div>
            <div class="agent-status ${statusClass}">${status}</div>
            <div class="agent-message">
              <div>${item.event || "event"}${handoff}</div>
              <div class="agent-meta">${outputs ? "Outputs: " + outputs : item.message || ""}</div>
            </div>
          </div>
        `;
      }).join("");

    const importantLogs = logs
      .filter(item =>
        item.event === "agent_completed" ||
        item.event === "agent_failed" ||
        item.event === "input_validation_completed" ||
        item.event === "chat_agent_ready" ||
        item.event === "user_question_routed"
      )
      .slice(-8)
      .reverse();

    const recentRows = importantLogs.map(item => {
      const status = (item.status || "info").toLowerCase();
      const statusClass = ["success", "failed", "running", "warning", "skipped"].includes(status) ? status : "info";

      return `
        <div class="agent-mini-row">
          <span class="agent-status ${statusClass}">${status}</span>
          <span><b>${item.agent}</b> — ${item.message || item.event}</span>
        </div>
      `;
    }).join("");

    el.innerHTML = `
      <div class="agent-section-title">Agent Handoff Summary</div>
      <div class="agent-summary-grid">
        ${summaryRows}
      </div>

      <div class="agent-section-title" style="margin-top:16px">Latest Important Interactions</div>
      <div class="agent-mini-list">
        ${recentRows}
      </div>
    `;

  } catch (err) {
    el.innerHTML = `<p style="color:#fca5a5">Failed to load agent logs: ${err}</p>`;
  }
}




// ==========================================================
// HM MAP V4 - strict active producer / inactive producer logic
// ==========================================================

let hmMapPayloadV4 = null;

function hmClassColorV4(hmClass) {
  const c = (hmClass || "").toLowerCase();

  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  if (c === "not evaluated") return "#94a3b8";
  return "#94a3b8";
}

function hmScoreLabelV4(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  const n = Number(value);
  if (!isFinite(n)) return "N/A";
  return n.toFixed(1);
}

async function loadHmMapPayload() {
  const panel = document.getElementById("map");

  try {
    const resp = await fetch("/api/dashboard/hm-map?t=" + Date.now());
    hmMapPayloadV4 = await resp.json();
    renderHmMap();
  } catch (err) {
    if (panel) {
      panel.innerHTML = `<p style="padding:20px;color:#fca5a5">Failed to load HM map payload: ${err}</p>`;
    }
  }
}

async function loadMap() {
  await loadHmMapPayload();
}

function renderHmMap() {
  const panel = document.getElementById("map");
  if (!panel) return;

  if (!hmMapPayloadV4 || !hmMapPayloadV4.wells) {
    panel.innerHTML = `<p style="padding:20px;color:#94a3b8">HM map payload not available.</p>`;
    return;
  }

  const showInjectors = document.getElementById("toggleInjectors")?.checked || false;
  const showInactive = document.getElementById("toggleInactiveProducers")?.checked || false;
  const variable = document.getElementById("hmVariableSelect")?.value || "overall";

  let mapItems = [];

  hmMapPayloadV4.wells.forEach(w => {
    if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) return;

    // Default map = active producers only.
    if (w.producer_candidate && w.active_producer) {
      mapItems.push({
        ...w,
        display_role: "producer",
        display_active: true,
        score: w[`${variable}_score`],
        cls: w[`${variable}_class`] || "Inactive"
      });
    }

    // Optional inactive producers.
    if (showInactive && w.producer_candidate && !w.active_producer) {
      mapItems.push({
        ...w,
        display_role: "inactive_producer",
        display_active: false,
        score: null,
        cls: "Inactive"
      });
    }

    // Optional injectors.
    if (showInjectors && w.injector_candidate) {
      mapItems.push({
        ...w,
        display_role: "injector",
        display_active: !!w.active_injector,
        score: w.injection_score,
        cls: w.injection_class || "Not Evaluated"
      });
    }
  });

  // Remove duplicates with same well/display_role.
  const seen = new Set();
  mapItems = mapItems.filter(w => {
    const key = `${w.well}_${w.display_role}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (mapItems.length === 0) {
    panel.innerHTML = `<p style="padding:20px;color:#94a3b8">No wells available for current filters.</p>`;
    return;
  }

  const iVals = mapItems.map(w => Number(w.i)).filter(v => isFinite(v));
  const jVals = mapItems.map(w => Number(w.j)).filter(v => isFinite(v));

  const minI = Math.min(...iVals);
  const maxI = Math.max(...iVals);
  const minJ = Math.min(...jVals);
  const maxJ = Math.max(...jVals);

  const W = 1000;
  const H = 640;
  const pad = 58;

  function sx(i) {
    if (maxI === minI) return W / 2;
    return pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  }

  function sy(j) {
    if (maxJ === minJ) return H / 2;
    return pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);
  }

  const label = {
    overall: "Overall HM",
    oil: "Oil HM",
    water: "Water HM",
    gas: "Gas HM",
    bhp: "BHP HM",
  }[variable] || "Overall HM";

  let svg = `
    <div class="hm-map-wrapper">
      <svg viewBox="0 0 ${W} ${H}" class="hm-map-svg">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3.5" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <text x="32" y="35" fill="#e5e7eb" font-size="18" font-weight="700">History Match Map</text>
        <text x="32" y="58" fill="#94a3b8" font-size="12">
          ${label} | default: active producers only | inactive producers and injectors optional
        </text>
        <text x="${W - 32}" y="35" fill="#5eead4" font-size="12" text-anchor="end">404 Reservoir Not Found</text>
  `;

  for (let k = 0; k < 9; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    svg += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(148,163,184,0.12)" />`;
    svg += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(148,163,184,0.12)" />`;
  }

  mapItems.forEach(w => {
    const x = sx(w.i);
    const y = sy(w.j);

    const cls = w.cls || "Inactive";
    const color = hmClassColorV4(cls);
    const opacity = w.display_active ? 1.0 : 0.55;

    let shape = "";

    if (w.display_role === "injector") {
      shape = `
        <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                 fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#glow)" />
      `;
    } else if (w.display_role === "inactive_producer") {
      shape = `
        <circle cx="${x}" cy="${y}" r="8.5" fill="${color}" stroke="#e5e7eb" stroke-width="1.2" opacity="0.5" />
      `;
    } else {
      shape = `
        <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#glow)" />
      `;
    }

    svg += `
      <g onclick="selectWell('${w.well}')" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity="0.14" />
        ${shape}
        <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
        <title>${w.well}
Display role: ${w.display_role}
Active producer: ${w.active_producer}
Active injector: ${w.active_injector}
Excluded from HM: ${w.exclude_from_hm}
Reason: ${w.exclusion_reason || "N/A"}
${label}: ${hmScoreLabelV4(w.score)}
Class: ${cls}
Max observed oil rate: ${w.max_observed_oil_rate ?? "N/A"}
Max observed injection rate: ${w.max_observed_injection_rate ?? "N/A"}</title>
      </g>
    `;
  });

  svg += `
      </svg>

      <div class="hm-legend">
        <span><span class="hm-legend-dot" style="background:#22c55e"></span>Good</span>
        <span><span class="hm-legend-dot" style="background:#facc15"></span>Fair</span>
        <span><span class="hm-legend-dot" style="background:#ef4444"></span>Poor</span>
        <span><span class="hm-legend-dot" style="background:#94a3b8"></span>Inactive / not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
      </div>
    </div>
  `;

  panel.innerHTML = svg;
}

function bindHmControlsV4() {
  document.getElementById("toggleInjectors")?.addEventListener("change", renderHmMap);
  document.getElementById("toggleInactiveProducers")?.addEventListener("change", renderHmMap);
  document.getElementById("hmVariableSelect")?.addEventListener("change", renderHmMap);
}

setTimeout(() => {
  bindHmControlsV4();
  loadHmMapPayload();
}, 400);



// ==========================================================
// VISUAL COPILOT CHAT V1
// ==========================================================

function askQuick(text) {
  const input = document.getElementById("chatInput");
  input.value = text;
  sendChat();
}

function vfmt(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  if (typeof v === "number") return Number(v).toFixed(2);
  const n = Number(v);
  if (!isNaN(n) && isFinite(n)) return n.toFixed(2);
  return String(v);
}

function classColor(cls) {
  const c = (cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
}

function heatColor(value, min, max) {
  const v = Number(value);
  if (!isFinite(v)) return "#64748b";
  if (max === null || min === null || max === min) return "#38bdf8";
  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));
  const hue = 210 - 170 * t;
  return `hsl(${hue}, 85%, 58%)`;
}

function getMapCoordinates(items) {
  const coords = [];

  items.forEach(x => {
    if (x.i !== null && x.i !== undefined && x.j !== null && x.j !== undefined) {
      coords.push({i: Number(x.i), j: Number(x.j)});
    }
  });

  return coords.filter(x => isFinite(x.i) && isFinite(x.j));
}

function renderInteractiveMap(block) {
  const payload = block.payload || {};
  const mapKind = block.map_kind || payload.kind;
  const visual = document.getElementById("visualPanel");

  const wells = payload.wells || [];
  const cells = payload.cells || [];

  const coords = getMapCoordinates([...wells, ...cells]);

  if (coords.length === 0) {
    visual.innerHTML = `<p style="color:#94a3b8">No spatial data available for this map.</p>`;
    return;
  }

  const minI = Math.min(...coords.map(x => x.i));
  const maxI = Math.max(...coords.map(x => x.i));
  const minJ = Math.min(...coords.map(x => x.j));
  const maxJ = Math.max(...coords.map(x => x.j));

  const W = 1000;
  const H = 640;
  const pad = 58;

  function sx(i) {
    if (maxI === minI) return W / 2;
    return pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  }

  function sy(j) {
    if (maxJ === minJ) return H / 2;
    return pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);
  }

  const variable = payload.variable || "overall";
  const title = block.title || payload.title || "Interactive Map";

  const showInactive = true;
  const showInjectors = true;

  let svg = `
    <div class="visual-section-title">${title}</div>
    <div class="visual-map-card">
      <svg viewBox="0 0 ${W} ${H}" class="visual-map-svg">
        <defs>
          <filter id="visualGlow">
            <feGaussianBlur stdDeviation="3.5" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <text x="32" y="35" fill="#e5e7eb" font-size="18" font-weight="700">${title}</text>
        <text x="${W - 32}" y="35" fill="#5eead4" font-size="12" text-anchor="end">404 Reservoir Not Found</text>
  `;

  for (let k = 0; k < 9; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    svg += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(148,163,184,0.12)" />`;
    svg += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(148,163,184,0.12)" />`;
  }

  // Corridor cells / highlighted channel.
  if (mapKind === "transmissibility_corridors" && cells.length > 0) {
    const minV = payload.min_intensity ?? Math.min(...cells.map(c => Number(c.intensity || 1)));
    const maxV = payload.max_intensity ?? Math.max(...cells.map(c => Number(c.intensity || 1)));

    cells.forEach(c => {
      const x = sx(c.i);
      const y = sy(c.j);
      const color = heatColor(c.intensity || 1, minV, maxV);

      svg += `
        <rect x="${x - 5}" y="${y - 5}" width="10" height="10"
              rx="2" fill="${color}" opacity="0.72" stroke="rgba(255,255,255,0.25)" />
      `;
    });
  }

  // Property halos around wells.
  if (mapKind === "property_map") {
    wells.forEach(w => {
      if (w.property_value === null || w.property_value === undefined) return;

      const x = sx(w.i);
      const y = sy(w.j);
      const color = heatColor(w.property_value, payload.min_value, payload.max_value);

      svg += `
        <circle cx="${x}" cy="${y}" r="22" fill="${color}" opacity="0.24" />
        <circle cx="${x}" cy="${y}" r="14" fill="${color}" opacity="0.14" />
      `;
    });
  }

  wells.forEach(w => {
    if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) return;

    const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
    const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

    let displayRole = "producer";
    if (injectorCandidate && !producerCandidate) displayRole = "injector";

    let cls = w[`${variable}_class`] || w.overall_class || "Not Evaluated";
    let score = w[`${variable}_score`] ?? w.overall_score;

    if (mapKind === "property_map") {
      cls = w.overall_class || "Not Evaluated";
      score = w.property_value;
    }

    if (displayRole === "producer" && w.active_producer === false) {
      cls = "Inactive";
      score = null;
    }

    const color = mapKind === "property_map"
      ? heatColor(w.property_value, payload.min_value, payload.max_value)
      : classColor(cls);

    const x = sx(w.i);
    const y = sy(w.j);
    const opacity = (cls || "").toLowerCase() === "inactive" ? 0.55 : 1.0;

    if (displayRole === "injector") {
      svg += `
        <g onclick="selectWell('${w.well}')" style="cursor:pointer">
          <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                   fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#visualGlow)" />
          <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
          <title>${w.well}
Role: injector
Class/value: ${cls}
Score/value: ${vfmt(score)}</title>
        </g>
      `;
    } else {
      svg += `
        <g onclick="selectWell('${w.well}')" style="cursor:pointer">
          <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity="0.13" />
          <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#visualGlow)" />
          <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
          <title>${w.well}
Role: producer
Class/value: ${cls}
Score/value: ${vfmt(score)}
Property: ${vfmt(w.property_value)}</title>
        </g>
      `;
    }
  });

  svg += `
      </svg>
    </div>
    <div class="hm-legend">
      <span><span class="hm-legend-dot" style="background:#22c55e"></span>Good</span>
      <span><span class="hm-legend-dot" style="background:#facc15"></span>Fair</span>
      <span><span class="hm-legend-dot" style="background:#ef4444"></span>Poor</span>
      <span><span class="hm-legend-dot" style="background:#94a3b8"></span>Inactive / Not evaluated</span>
      <span>● Producer</span>
      <span>◆ Injector</span>
    </div>
  `;

  if (payload.message) {
    svg += `<p style="color:#94a3b8;margin-top:10px">${payload.message}</p>`;
  }

  visual.innerHTML = svg;
}

function renderMetricCards(block) {
  const items = block.items || [];
  return `
    <div class="visual-section-title">${block.title || "Metrics"}</div>
    <div class="visual-card-grid">
      ${items.map(c => `
        <div class="visual-card">
          <div class="visual-card-label">${c.label || c.variable || "Metric"}</div>
          <div class="visual-card-value" style="color:${c.color || classColor(c.class)}">${vfmt(c.score ?? c.value)}</div>
          <div class="visual-card-label">${c.class || ""}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderCompactTable(block) {
  const rows = block.rows || [];
  if (rows.length === 0) return `<p style="color:#94a3b8">No rows available.</p>`;

  const preferred = ["well", "score", "class", "issue", "metric", "value", "oil", "water", "gas", "bhp"];
  let keys = Object.keys(rows[0]);
  keys = preferred.filter(k => keys.includes(k)).concat(keys.filter(k => !preferred.includes(k))).slice(0, 6);

  return `
    <div class="visual-section-title">${block.title || "Table"}</div>
    <div class="compact-table-wrap">
      <table class="compact-table">
        <thead><tr>${keys.map(k => `<th>${k}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr>${keys.map(k => `<td>${vfmt(r[k])}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderWellCards(block) {
  const d = block.data || {};
  const scores = d.scores || {};

  return `
    <div class="visual-section-title">${block.title || d.well || "Well detail"}</div>
    <div class="visual-card-grid">
      ${["overall", "oil", "water", "gas", "bhp"].map(k => `
        <div class="visual-card">
          <div class="visual-card-label">${k.toUpperCase()}</div>
          <div class="visual-card-value">${vfmt(scores[k])}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderSuggestions(block) {
  const items = block.items || [];
  return `
    <div class="visual-section-title">Suggested actions</div>
    <div class="quick-actions">
      ${items.map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${x}</button>`).join("")}
    </div>
  `;
}

function renderVisualResponse(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  const blocks = data.ui_blocks || [];
  let answerHtml = `<p>${data.answer || ""}</p>`;

  visual.innerHTML = `<p style="color:#94a3b8">Select a visual action or ask a reservoir question.</p>`;

  let visualRendered = false;

  blocks.forEach(block => {
    if (block.type === "metric_cards") {
      answerHtml += renderMetricCards(block);
    }

    else if (block.type === "compact_table") {
      answerHtml += renderCompactTable(block);
    }

    else if (block.type === "compact_notes") {
      answerHtml += `
        <ul class="visual-note-list">
          ${(block.items || []).map(x => `<li>${x}</li>`).join("")}
        </ul>
      `;
    }

    else if (block.type === "well_cards") {
      answerHtml += renderWellCards(block);
    }

    else if (block.type === "suggestions") {
      answerHtml += renderSuggestions(block);
    }

    else if (block.type === "profile_series") {
      renderProfileSeries(block.data);
      visualRendered = true;
    }

    else if (block.type === "interactive_map") {
      renderInteractiveMap(block);
      visualRendered = true;
    }
  });

  answer.innerHTML = answerHtml;
}

async function sendChat() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;

  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const data = await postJson("/api/agent-chat-v501", {message: msg});

    if (data.type === "visual_response") {
      renderVisualResponse(data);
      await loadAgentFlow();
      return;
    }

    // fallback to previous handlers if an old response appears
    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;

    if (data.type === "profile_series") {
      renderProfileSeries(data.data);
    } else if (data.type === "corridors" && data.data && data.data.map_url) {
      visual.innerHTML = `<img src="${data.data.map_url}" />`;
    } else {
      visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;
    }

    await loadAgentFlow();

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed: ${err}</p>`;
    visual.innerHTML = `<p style="color:#fca5a5">No visual output generated.</p>`;
  }
}



// ==========================================================
// VISUAL MAP RENDERER V2 - robust scale, colorbar, corridor sampling
// ==========================================================

function safeMinMax(values) {
  let minV = null;
  let maxV = null;

  for (const raw of values) {
    const v = Number(raw);
    if (!isFinite(v)) continue;

    if (minV === null || v < minV) minV = v;
    if (maxV === null || v > maxV) maxV = v;
  }

  return { min: minV, max: maxV };
}

function sampleArrayDeterministic(arr, maxItems) {
  if (!arr || arr.length <= maxItems) return arr || [];

  const out = [];
  const step = arr.length / maxItems;

  for (let i = 0; i < maxItems; i++) {
    out.push(arr[Math.floor(i * step)]);
  }

  return out;
}

function heatColorV2(value, min, max) {
  const v = Number(value);

  if (!isFinite(v)) return "#64748b";
  if (min === null || max === null || min === undefined || max === undefined || max === min) return "#38bdf8";

  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));

  // Blue -> cyan -> yellow -> red
  if (t < 0.33) {
    return `rgb(${Math.round(40 + 40*t/0.33)}, ${Math.round(120 + 90*t/0.33)}, 255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${Math.round(80 + 175*u)}, ${Math.round(210 + 25*u)}, ${Math.round(255 - 210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255, ${Math.round(235 - 145*u)}, ${Math.round(45 - 10*u)})`;
}

function renderColorBarV2(label, min, max) {
  if (min === null || max === null || min === undefined || max === undefined) {
    return `
      <div class="visual-colorbar-wrap">
        <div class="visual-colorbar-title">${label}</div>
        <div class="visual-colorbar-empty">No numeric scale available</div>
      </div>
    `;
  }

  return `
    <div class="visual-colorbar-wrap">
      <div class="visual-colorbar-title">${label}</div>
      <div class="visual-colorbar"></div>
      <div class="visual-colorbar-labels">
        <span>${vfmt(min)}</span>
        <span>low → high</span>
        <span>${vfmt(max)}</span>
      </div>
    </div>
  `;
}

function renderInteractiveMap(block) {
  const payload = block.payload || {};
  const mapKind = block.map_kind || payload.kind;
  const visual = document.getElementById("visualPanel");

  const wells = payload.wells || [];
  const rawCells = payload.cells || [];

  // Avoid browser overload when corridors contain many cells.
  const MAX_CELLS_TO_DRAW = 6500;
  const cells = sampleArrayDeterministic(rawCells, MAX_CELLS_TO_DRAW);

  const coords = [];

  wells.forEach(w => {
    const i = Number(w.i);
    const j = Number(w.j);
    if (isFinite(i) && isFinite(j)) coords.push({ i, j });
  });

  cells.forEach(c => {
    const i = Number(c.i);
    const j = Number(c.j);
    if (isFinite(i) && isFinite(j)) coords.push({ i, j });
  });

  if (coords.length === 0) {
    visual.innerHTML = `<p style="color:#94a3b8">No spatial data available for this map.</p>`;
    return;
  }

  const mmI = safeMinMax(coords.map(x => x.i));
  const mmJ = safeMinMax(coords.map(x => x.j));

  const minI = mmI.min;
  const maxI = mmI.max;
  const minJ = mmJ.min;
  const maxJ = mmJ.max;

  const W = 1000;
  const H = 640;
  const pad = 58;

  function sx(i) {
    if (maxI === minI) return W / 2;
    return pad + (Number(i) - minI) * (W - 2 * pad) / (maxI - minI);
  }

  function sy(j) {
    if (maxJ === minJ) return H / 2;
    return pad + (Number(j) - minJ) * (H - 2 * pad) / (maxJ - minJ);
  }

  const variable = payload.variable || "overall";
  const title = block.title || payload.title || "Interactive Map";

  let scaleLabel = "";
  let scaleMin = null;
  let scaleMax = null;

  if (mapKind === "property_map") {
    scaleLabel = payload.property_label || payload.property_name || "Property";
    scaleMin = payload.min_value;
    scaleMax = payload.max_value;
  }

  if (mapKind === "transmissibility_corridors") {
    scaleLabel = "Corridor intensity";
    const mm = safeMinMax(cells.map(c => c.intensity || 1));
    scaleMin = payload.min_intensity ?? mm.min;
    scaleMax = payload.max_intensity ?? mm.max;
  }

  let svg = `
    <div class="visual-section-title">${title}</div>
    <div class="visual-map-card">
      <svg viewBox="0 0 ${W} ${H}" class="visual-map-svg">
        <defs>
          <filter id="visualGlow">
            <feGaussianBlur stdDeviation="3.5" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <text x="32" y="35" fill="#e5e7eb" font-size="18" font-weight="700">${title}</text>
        <text x="${W - 32}" y="35" fill="#5eead4" font-size="12" text-anchor="end">404 Reservoir Not Found</text>
  `;

  for (let k = 0; k < 9; k++) {
    const x = pad + k * (W - 2 * pad) / 8;
    const y = pad + k * (H - 2 * pad) / 8;
    svg += `<line x1="${x}" y1="${pad}" x2="${x}" y2="${H-pad}" stroke="rgba(148,163,184,0.12)" />`;
    svg += `<line x1="${pad}" y1="${y}" x2="${W-pad}" y2="${y}" stroke="rgba(148,163,184,0.12)" />`;
  }

  // Corridor cells / highlighted channel.
  if (mapKind === "transmissibility_corridors") {
    if (cells.length === 0) {
      svg += `
        <text x="${W/2}" y="${H/2}" fill="#94a3b8" font-size="15" text-anchor="middle">
          No corridor cells available. Check candidate_transmissibility_corridor_cells.csv.
        </text>
      `;
    } else {
      cells.forEach(c => {
        const x = sx(c.i);
        const y = sy(c.j);
        const intensity = Number(c.intensity || 1);
        const color = heatColorV2(intensity, scaleMin, scaleMax);

        svg += `
          <rect x="${x - 5}" y="${y - 5}" width="10" height="10"
                rx="2" fill="${color}" opacity="0.78" stroke="rgba(255,255,255,0.24)" />
        `;
      });
    }
  }

  // Property halos around wells.
  if (mapKind === "property_map") {
    wells.forEach(w => {
      if (w.property_value === null || w.property_value === undefined) return;

      const x = sx(w.i);
      const y = sy(w.j);
      const color = heatColorV2(w.property_value, scaleMin, scaleMax);

      svg += `
        <circle cx="${x}" cy="${y}" r="25" fill="${color}" opacity="0.30" />
        <circle cx="${x}" cy="${y}" r="14" fill="${color}" opacity="0.18" />
      `;
    });
  }

  // Wells.
  wells.forEach(w => {
    if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) return;

    const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
    const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

    let displayRole = "producer";
    if (injectorCandidate && !producerCandidate) displayRole = "injector";

    let cls = w[`${variable}_class`] || w.overall_class || "Not Evaluated";
    let score = w[`${variable}_score`] ?? w.overall_score;

    if (mapKind === "property_map") {
      cls = w.overall_class || "Not Evaluated";
      score = w.property_value;
    }

    if (displayRole === "producer" && w.active_producer === false) {
      cls = "Inactive";
      score = null;
    }

    const color = mapKind === "property_map"
      ? heatColorV2(w.property_value, scaleMin, scaleMax)
      : classColor(cls);

    const x = sx(w.i);
    const y = sy(w.j);
    const opacity = (cls || "").toLowerCase() === "inactive" ? 0.55 : 1.0;

    if (displayRole === "injector") {
      svg += `
        <g onclick="selectWell('${w.well}')" style="cursor:pointer">
          <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                   fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#visualGlow)" />
          <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
          <title>${w.well}
Role: injector
Class/value: ${cls}
Score/value: ${vfmt(score)}</title>
        </g>
      `;
    } else {
      svg += `
        <g onclick="selectWell('${w.well}')" style="cursor:pointer">
          <circle cx="${x}" cy="${y}" r="18" fill="${color}" opacity="0.13" />
          <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${opacity}" filter="url(#visualGlow)" />
          <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
          <title>${w.well}
Role: producer
Class/value: ${cls}
Score/value: ${vfmt(score)}
Property: ${vfmt(w.property_value)}</title>
        </g>
      `;
    }
  });

  svg += `
      </svg>
    </div>
  `;

  let footer = "";

  if (mapKind === "property_map" || mapKind === "transmissibility_corridors") {
    footer += renderColorBarV2(scaleLabel, scaleMin, scaleMax);
  }

  footer += `
    <div class="hm-legend">
      <span><span class="hm-legend-dot" style="background:#22c55e"></span>Good</span>
      <span><span class="hm-legend-dot" style="background:#facc15"></span>Fair</span>
      <span><span class="hm-legend-dot" style="background:#ef4444"></span>Poor</span>
      <span><span class="hm-legend-dot" style="background:#94a3b8"></span>Inactive / Not evaluated</span>
      <span>● Producer</span>
      <span>◆ Injector</span>
    </div>
  `;

  if (mapKind === "transmissibility_corridors") {
    footer += `
      <p style="color:#94a3b8;margin-top:8px;font-size:12px">
        Showing ${cells.length} of ${rawCells.length} corridor cells. 
        Cells are sampled for browser performance when the corridor is very dense.
      </p>
    `;
  }

  if (payload.message) {
    footer += `<p style="color:#94a3b8;margin-top:10px">${payload.message}</p>`;
  }

  visual.innerHTML = svg + footer;
}



// ==========================================================
// VISUAL COPILOT SAFE RENDER V3 - visible errors, no blank panel
// ==========================================================

function showVisualError(title, err, extra) {
  const visual = document.getElementById("visualPanel");
  const msg = err && err.stack ? err.stack : String(err || "Unknown error");

  visual.innerHTML = `
    <div style="padding:16px;border:1px solid rgba(239,68,68,0.35);border-radius:14px;background:rgba(127,29,29,0.18);color:#fecaca">
      <b>${title}</b>
      <pre style="white-space:pre-wrap;margin-top:10px;color:#fecaca;font-size:12px">${msg}</pre>
      ${extra ? `<pre style="white-space:pre-wrap;margin-top:10px;color:#fca5a5;font-size:12px">${extra}</pre>` : ""}
    </div>
  `;
}

function safeHeatColor(value, min, max) {
  const v = Number(value);
  if (!isFinite(v)) return "rgba(100,116,139,0)";

  if (min === null || max === null || min === undefined || max === undefined || max === min) {
    return "rgb(56,189,248)";
  }

  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));

  if (t < 0.33) {
    const u = t / 0.33;
    return `rgb(${Math.round(30 + 40*u)}, ${Math.round(100 + 100*u)}, 255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${Math.round(70 + 185*u)}, ${Math.round(200 + 35*u)}, ${Math.round(255 - 210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255, ${Math.round(235 - 145*u)}, ${Math.round(45 - 10*u)})`;
}

function safeClassColor(cls) {
  const c = (cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
}

function safeFmt(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (isFinite(n)) return n.toFixed(3);
  return String(v);
}

function renderCellPropertyMap(block) {
  const visual = document.getElementById("visualPanel");

  try {
    const payload = block.payload || {};

    console.log("CELL PROPERTY PAYLOAD:", payload);

    if (!payload.ok) {
      visual.innerHTML = `
        <div class="visual-section-title">${block.title || "Cell property map"}</div>
        <p style="color:#fca5a5">${payload.message || "Cell property layer not available."}</p>
        <pre style="color:#94a3b8;white-space:pre-wrap;font-size:12px">${JSON.stringify(payload, null, 2).slice(0, 3000)}</pre>
      `;
      return;
    }

    const mapId = "safeCellMap_" + Date.now();
    const tooltipId = "safeCellTooltip_" + Date.now();

    visual.innerHTML = `
      <div class="cell-map-title">${block.title || payload.label || payload.property}</div>
      <div class="cell-map-subtitle">
        ${payload.message || ""}<br/>
        Grid: ${payload.nx} × ${payload.ny} × ${payload.nz} | Cells: ${payload.cell_count}
      </div>

      <div class="cell-map-shell" id="${mapId}_shell">
        <canvas class="cell-map-canvas" id="${mapId}_canvas"></canvas>
        <div class="cell-map-overlay" id="${mapId}_overlay"></div>
      </div>

      <div class="visual-colorbar-wrap">
        <div class="visual-colorbar-title">${payload.label || payload.property}${payload.unit ? " (" + payload.unit + ")" : ""}</div>
        <div class="visual-colorbar"></div>
        <div class="visual-colorbar-labels">
          <span>${safeFmt(payload.p2 ?? payload.min)}</span>
          <span>low → high</span>
          <span>${safeFmt(payload.p98 ?? payload.max)}</span>
        </div>
      </div>

      <div class="hm-legend">
        <span><span class="hm-legend-dot" style="background:#22c55e"></span>Good</span>
        <span><span class="hm-legend-dot" style="background:#facc15"></span>Fair</span>
        <span><span class="hm-legend-dot" style="background:#ef4444"></span>Poor</span>
        <span><span class="hm-legend-dot" style="background:#94a3b8"></span>Inactive / Not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
        ${block.corridor_payload ? '<span style="color:#fde68a">■ Candidate corridor</span>' : ''}
      </div>

      <div class="cell-tooltip" id="${tooltipId}"></div>
    `;

    // Render after DOM layout is available.
    setTimeout(() => {
      try {
        const canvas = document.getElementById(`${mapId}_canvas`);
        const overlay = document.getElementById(`${mapId}_overlay`);
        const shell = document.getElementById(`${mapId}_shell`);
        const tooltip = document.getElementById(tooltipId);

        if (!canvas || !overlay || !shell) {
          throw new Error("Canvas/overlay/shell not found after inserting HTML.");
        }

        const rect = shell.getBoundingClientRect();

        if (rect.width < 10 || rect.height < 10) {
          throw new Error(`Cell map shell has invalid size: width=${rect.width}, height=${rect.height}`);
        }

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(rect.width * dpr);
        canvas.height = Math.floor(rect.height * dpr);

        const ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const W = rect.width;
        const H = rect.height;
        const pad = 42;

        const nx = Number(payload.nx);
        const ny = Number(payload.ny);

        if (!nx || !ny) {
          throw new Error(`Invalid grid dimensions nx=${payload.nx}, ny=${payload.ny}`);
        }

        const plotW = W - 2 * pad;
        const plotH = H - 2 * pad;

        const minV = payload.p2 ?? payload.min;
        const maxV = payload.p98 ?? payload.max;

        ctx.fillStyle = "#08111f";
        ctx.fillRect(0, 0, W, H);

        ctx.strokeStyle = "rgba(148,163,184,0.10)";
        ctx.lineWidth = 1;

        for (let k = 0; k <= 8; k++) {
          const x = pad + k * plotW / 8;
          const y = pad + k * plotH / 8;

          ctx.beginPath();
          ctx.moveTo(x, pad);
          ctx.lineTo(x, H - pad);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(pad, y);
          ctx.lineTo(W - pad, y);
          ctx.stroke();
        }

        const cellW = Math.max(1, plotW / nx);
        const cellH = Math.max(1, plotH / ny);

        const valueMap = new Map();

        for (const c of payload.cells || []) {
          const i = Number(c.i);
          const j = Number(c.j);
          const v = Number(c.value);

          if (!isFinite(i) || !isFinite(j) || !isFinite(v)) continue;

          const x = pad + (i - 1) * plotW / nx;
          const y = pad + (j - 1) * plotH / ny;

          ctx.fillStyle = safeHeatColor(v, minV, maxV);
          ctx.globalAlpha = 0.88;
          ctx.fillRect(x, y, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);

          valueMap.set(`${i}_${j}`, v);
        }

        ctx.globalAlpha = 1.0;

        // Optional corridor overlay.
        const corridorPayload = block.corridor_payload || null;
        const corridorCells = corridorPayload && corridorPayload.cells ? corridorPayload.cells : [];

        if (corridorCells.length > 0) {
          const maxDraw = 6500;
          const sampled = corridorCells.length > maxDraw
            ? corridorCells.filter((_, idx) => idx % Math.ceil(corridorCells.length / maxDraw) === 0)
            : corridorCells;

          ctx.globalAlpha = 0.85;

          for (const c of sampled) {
            const i = Number(c.i);
            const j = Number(c.j);

            if (!isFinite(i) || !isFinite(j)) continue;

            const x = pad + (i - 1) * plotW / nx;
            const y = pad + (j - 1) * plotH / ny;

            ctx.fillStyle = "rgba(255,220,80,0.88)";
            ctx.fillRect(x, y, Math.max(3, cellW * 1.4), Math.max(3, cellH * 1.4));
          }

          ctx.globalAlpha = 1.0;
        }

        // SVG overlay wells.
        let svg = `
          <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
            <defs>
              <filter id="safeWellGlow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
        `;

        function sx(i) {
          return pad + (Number(i) - 1) * plotW / nx;
        }

        function sy(j) {
          return pad + (Number(j) - 1) * plotH / ny;
        }

        for (const w of payload.wells || []) {
          if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

          const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
          const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

          let role = "producer";
          if (injectorCandidate && !producerCandidate) role = "injector";

          const inactive = producerCandidate && w.active_producer === false;
          const cls = inactive ? "Inactive" : (w.overall_class || "Not Evaluated");
          const color = safeClassColor(cls);

          const x = sx(w.i);
          const y = sy(w.j);

          if (role === "injector") {
            svg += `
              <g onclick="selectWell('${w.well}')" style="cursor:pointer">
                <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                         fill="${color}" stroke="#e5e7eb" stroke-width="1.4" filter="url(#safeWellGlow)" />
                <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                <title>${w.well} | Injector | ${cls}</title>
              </g>
            `;
          } else {
            svg += `
              <g onclick="selectWell('${w.well}')" style="cursor:pointer">
                <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${inactive ? 0.55 : 1}" filter="url(#safeWellGlow)" />
                <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                <title>${w.well} | Producer | ${cls}</title>
              </g>
            `;
          }
        }

        svg += `</svg>`;
        overlay.innerHTML = svg;

        shell.addEventListener("mousemove", (ev) => {
          const r = shell.getBoundingClientRect();
          const x = ev.clientX - r.left;
          const y = ev.clientY - r.top;

          const i = Math.floor((x - pad) / plotW * nx) + 1;
          const j = Math.floor((y - pad) / plotH * ny) + 1;

          if (i < 1 || j < 1 || i > nx || j > ny) {
            tooltip.style.display = "none";
            return;
          }

          const val = valueMap.get(`${i}_${j}`);

          tooltip.style.display = "block";
          tooltip.style.left = `${ev.clientX + 14}px`;
          tooltip.style.top = `${ev.clientY + 14}px`;
          tooltip.innerHTML = `
            <b>${payload.label || payload.property}</b><br/>
            I=${i}, J=${j}<br/>
            Value: ${safeFmt(val)} ${payload.unit || ""}
          `;
        });

        shell.addEventListener("mouseleave", () => {
          tooltip.style.display = "none";
        });

      } catch (err) {
        showVisualError("Cell map rendering failed", err, JSON.stringify({
          property: payload.property,
          nx: payload.nx,
          ny: payload.ny,
          cells: payload.cell_count,
          ok: payload.ok
        }, null, 2));
      }
    }, 50);

  } catch (err) {
    showVisualError("Cell map setup failed", err, JSON.stringify(block || {}, null, 2).slice(0, 3000));
  }
}

async function sendChat() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;

  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const resp = await fetch("/api/agent-chat-v501", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg})
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${txt}`);
    }

    const data = await resp.json();
    console.log("CHAT RESPONSE:", data);

    if (data.type === "visual_response") {
      renderVisualResponse(data);
      if (typeof loadAgentFlow === "function") {
        await loadAgentFlow();
      }
      return;
    }

    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;
    visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed.</p>`;
    showVisualError("Chat request failed", err);
  }
}



// ==========================================================
// FINAL VISUAL OVERRIDE V200 - forced window functions
// ==========================================================
window.__visualPatchVersion = "V200_CELL_HEATMAP_FINAL";
console.log("Loaded visual patch:", window.__visualPatchVersion);

window.v200Fmt = function(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(3);
  return String(v);
};

window.v200ClassColor = function(cls) {
  const c = String(cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
};

window.v200HeatColor = function(value, min, max) {
  const v = Number(value);
  if (!Number.isFinite(v)) return "rgba(100,116,139,0)";

  if (min === null || max === null || min === undefined || max === undefined || max === min) {
    return "rgb(56,189,248)";
  }

  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));

  if (t < 0.33) {
    const u = t / 0.33;
    return `rgb(${Math.round(30 + 40*u)}, ${Math.round(100 + 100*u)}, 255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${Math.round(70 + 185*u)}, ${Math.round(200 + 35*u)}, ${Math.round(255 - 210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255, ${Math.round(235 - 145*u)}, ${Math.round(45 - 10*u)})`;
};

window.v200ShowError = function(title, err, extra) {
  const visual = document.getElementById("visualPanel");
  if (!visual) {
    alert(title + ": " + err);
    return;
  }

  const msg = err && err.stack ? err.stack : String(err || "Unknown error");

  visual.innerHTML = `
    <div style="padding:16px;border:1px solid rgba(239,68,68,0.45);border-radius:14px;background:rgba(127,29,29,0.22);color:#fecaca">
      <b>${title}</b>
      <pre style="white-space:pre-wrap;margin-top:10px;color:#fecaca;font-size:12px">${msg}</pre>
      ${extra ? `<pre style="white-space:pre-wrap;margin-top:10px;color:#fca5a5;font-size:12px">${extra}</pre>` : ""}
    </div>
  `;
};

window.renderCellPropertyMap = function(block) {
  const visual = document.getElementById("visualPanel");

  try {
    if (!visual) {
      throw new Error("visualPanel element not found in DOM.");
    }

    const payload = block.payload || {};
    console.log("V200 renderCellPropertyMap payload:", payload);

    if (!payload.ok) {
      visual.innerHTML = `
        <div style="color:#e5e7eb;font-weight:800;margin-bottom:10px">${block.title || "Cell property map"}</div>
        <p style="color:#fca5a5">${payload.message || "Cell property layer not available."}</p>
        <pre style="white-space:pre-wrap;color:#94a3b8;font-size:12px">${JSON.stringify(payload, null, 2).slice(0, 2500)}</pre>
      `;
      return;
    }

    const mapId = "v200_cellmap_" + Date.now();
    const tooltipId = "v200_tooltip_" + Date.now();

    visual.innerHTML = `
      <div style="color:#e5e7eb;font-size:16px;font-weight:800;margin:8px 0">
        ${block.title || payload.label || payload.property}
      </div>
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">
        ${payload.message || ""}<br/>
        Grid: ${payload.nx} × ${payload.ny} × ${payload.nz} | Cells: ${payload.cell_count}
      </div>

      <div id="${mapId}_shell" style="position:relative;width:100%;height:640px;border-radius:18px;overflow:hidden;border:1px solid rgba(148,163,184,0.18);background:#08111f">
        <canvas id="${mapId}_canvas" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
        <div id="${mapId}_overlay" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto"></div>
      </div>

      <div style="margin-top:12px;padding:10px 12px;border:1px solid rgba(148,163,184,0.18);border-radius:14px;background:rgba(2,6,23,0.38)">
        <div style="color:#e5e7eb;font-size:13px;font-weight:800;margin-bottom:8px">
          ${payload.label || payload.property}${payload.unit ? " (" + payload.unit + ")" : ""}
        </div>
        <div style="height:14px;border-radius:999px;border:1px solid rgba(226,232,240,0.35);background:linear-gradient(90deg, rgb(30,100,255), rgb(70,200,255), rgb(255,235,45), rgb(255,90,35))"></div>
        <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:12px;margin-top:5px">
          <span>${window.v200Fmt(payload.p2 ?? payload.min)}</span>
          <span>low → high</span>
          <span>${window.v200Fmt(payload.p98 ?? payload.max)}</span>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:#cbd5e1;font-size:13px">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e;margin-right:6px"></span>Good</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#facc15;margin-right:6px"></span>Fair</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:6px"></span>Poor</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#94a3b8;margin-right:6px"></span>Inactive / Not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
        ${block.corridor_payload ? '<span style="color:#fde68a">■ Candidate corridor</span>' : ''}
      </div>

      <div id="${tooltipId}" style="position:fixed;display:none;z-index:9999;pointer-events:none;background:rgba(2,6,23,0.96);color:#e5e7eb;border:1px solid rgba(148,163,184,0.35);border-radius:10px;padding:8px 10px;font-size:12px;box-shadow:0 14px 35px rgba(0,0,0,0.35)"></div>
    `;

    requestAnimationFrame(() => {
      try {
        const shell = document.getElementById(`${mapId}_shell`);
        const canvas = document.getElementById(`${mapId}_canvas`);
        const overlay = document.getElementById(`${mapId}_overlay`);
        const tooltip = document.getElementById(tooltipId);

        if (!shell || !canvas || !overlay) {
          throw new Error("Map shell/canvas/overlay not found.");
        }

        const rect = shell.getBoundingClientRect();
        const W = rect.width || 900;
        const H = rect.height || 640;
        const pad = 42;

        const nx = Number(payload.nx);
        const ny = Number(payload.ny);

        if (!nx || !ny) {
          throw new Error(`Invalid grid dimensions nx=${payload.nx}, ny=${payload.ny}`);
        }

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(W * dpr);
        canvas.height = Math.floor(H * dpr);

        const ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const plotW = W - 2 * pad;
        const plotH = H - 2 * pad;

        const minV = payload.p2 ?? payload.min;
        const maxV = payload.p98 ?? payload.max;

        ctx.fillStyle = "#08111f";
        ctx.fillRect(0, 0, W, H);

        ctx.strokeStyle = "rgba(148,163,184,0.10)";
        ctx.lineWidth = 1;

        for (let k = 0; k <= 8; k++) {
          const x = pad + k * plotW / 8;
          const y = pad + k * plotH / 8;

          ctx.beginPath();
          ctx.moveTo(x, pad);
          ctx.lineTo(x, H - pad);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(pad, y);
          ctx.lineTo(W - pad, y);
          ctx.stroke();
        }

        const cellW = Math.max(1, plotW / nx);
        const cellH = Math.max(1, plotH / ny);

        const valueMap = new Map();

        for (const c of payload.cells || []) {
          const i = Number(c.i);
          const j = Number(c.j);
          const v = Number(c.value);

          if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;

          const x = pad + (i - 1) * plotW / nx;
          const y = pad + (j - 1) * plotH / ny;

          ctx.fillStyle = window.v200HeatColor(v, minV, maxV);
          ctx.globalAlpha = 0.88;
          ctx.fillRect(x, y, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);

          valueMap.set(`${i}_${j}`, v);
        }

        ctx.globalAlpha = 1.0;

        // Corridor overlay if present.
        const corridorPayload = block.corridor_payload || null;
        const corridorCells = corridorPayload && corridorPayload.cells ? corridorPayload.cells : [];

        if (corridorCells.length > 0) {
          const maxDraw = 6500;
          const step = Math.max(1, Math.ceil(corridorCells.length / maxDraw));

          ctx.globalAlpha = 0.85;
          ctx.fillStyle = "rgba(255,220,80,0.90)";

          for (let idx = 0; idx < corridorCells.length; idx += step) {
            const c = corridorCells[idx];
            const i = Number(c.i);
            const j = Number(c.j);

            if (!Number.isFinite(i) || !Number.isFinite(j)) continue;

            const x = pad + (i - 1) * plotW / nx;
            const y = pad + (j - 1) * plotH / ny;

            ctx.fillRect(x, y, Math.max(3, cellW * 1.4), Math.max(3, cellH * 1.4));
          }

          ctx.globalAlpha = 1.0;
        }

        function sx(i) {
          return pad + (Number(i) - 1) * plotW / nx;
        }

        function sy(j) {
          return pad + (Number(j) - 1) * plotH / ny;
        }

        let svg = `
          <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
            <defs>
              <filter id="v200WellGlow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
        `;

        for (const w of payload.wells || []) {
          if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

          const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
          const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

          let role = "producer";
          if (injectorCandidate && !producerCandidate) role = "injector";

          const inactive = producerCandidate && w.active_producer === false;
          const cls = inactive ? "Inactive" : (w.overall_class || "Not Evaluated");
          const color = window.v200ClassColor(cls);

          const x = sx(w.i);
          const y = sy(w.j);

          if (role === "injector") {
            svg += `
              <g onclick="selectWell('${w.well}')" style="cursor:pointer">
                <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                         fill="${color}" stroke="#e5e7eb" stroke-width="1.4" filter="url(#v200WellGlow)" />
                <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                <title>${w.well} | Injector | ${cls}</title>
              </g>
            `;
          } else {
            svg += `
              <g onclick="selectWell('${w.well}')" style="cursor:pointer">
                <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${inactive ? 0.55 : 1}" filter="url(#v200WellGlow)" />
                <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                <title>${w.well} | Producer | ${cls}</title>
              </g>
            `;
          }
        }

        svg += `</svg>`;
        overlay.innerHTML = svg;

        shell.addEventListener("mousemove", (ev) => {
          const r = shell.getBoundingClientRect();
          const x = ev.clientX - r.left;
          const y = ev.clientY - r.top;

          const i = Math.floor((x - pad) / plotW * nx) + 1;
          const j = Math.floor((y - pad) / plotH * ny) + 1;

          if (i < 1 || j < 1 || i > nx || j > ny) {
            tooltip.style.display = "none";
            return;
          }

          const val = valueMap.get(`${i}_${j}`);

          tooltip.style.display = "block";
          tooltip.style.left = `${ev.clientX + 14}px`;
          tooltip.style.top = `${ev.clientY + 14}px`;
          tooltip.innerHTML = `
            <b>${payload.label || payload.property}</b><br/>
            I=${i}, J=${j}<br/>
            Value: ${window.v200Fmt(val)} ${payload.unit || ""}
          `;
        });

        shell.addEventListener("mouseleave", () => {
          tooltip.style.display = "none";
        });

        console.log("V200 cell map rendered successfully:", payload.property);

      } catch (err) {
        window.v200ShowError("Cell map rendering failed", err, JSON.stringify({
          property: payload.property,
          nx: payload.nx,
          ny: payload.ny,
          nz: payload.nz,
          cells: payload.cell_count,
          ok: payload.ok
        }, null, 2));
      }
    });

  } catch (err) {
    window.v200ShowError("Cell map setup failed", err);
  }
};

window.renderVisualResponse = function(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!answer || !visual) {
    alert("chatAnswer or visualPanel not found in DOM");
    return;
  }

  console.log("V200 renderVisualResponse:", data);

  const blocks = data.ui_blocks || [];
  let answerHtml = `<p>${data.answer || ""}</p>`;

  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual output...</p>`;

  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      window.renderCellPropertyMap(block);
    }

    else if (block.type === "profile_series" && typeof window.renderProfileSeries === "function") {
      window.renderProfileSeries(block.data);
    }

    else if (block.type === "interactive_map" && typeof window.renderInteractiveMap === "function") {
      window.renderInteractiveMap(block);
    }

    else if (block.type === "compact_notes") {
      answerHtml += `
        <ul style="color:#cbd5e1">
          ${(block.items || []).map(x => `<li>${x}</li>`).join("")}
        </ul>
      `;
    }

    else if (block.type === "suggestions") {
      answerHtml += `
        <div class="quick-actions">
          ${(block.items || []).map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${x}</button>`).join("")}
        </div>
      `;
    }

    else if (block.type === "compact_table") {
      answerHtml += `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(block.rows || [], null, 2)}</pre>`;
    }
  }

  answer.innerHTML = answerHtml;
};

window.sendChat = async function() {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!input || !answer || !visual) {
    alert("Missing chatInput/chatAnswer/visualPanel elements.");
    return;
  }

  const msg = input.value.trim();
  if (!msg) return;

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const resp = await fetch("/api/agent-chat-v501", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg})
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${txt}`);
    }

    const data = await resp.json();
    console.log("V200 CHAT RESPONSE:", data);

    if (data.type === "visual_response") {
      window.renderVisualResponse(data);
      return;
    }

    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;
    visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed.</p>`;
    window.v200ShowError("Chat request failed", err);
  }
};

window.askQuick = function(text) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found");
    return;
  }
  input.value = text;
  window.sendChat();
};

console.log("V200 visual override ready. Test with: window.__visualPatchVersion");



// ==========================================================
// FINAL VISUAL OVERRIDE V210 - zoom/pan + clickable wells
// ==========================================================
window.__visualPatchVersion = "V210_ZOOM_PAN_CLICK_WELLS";
console.log("Loaded visual patch:", window.__visualPatchVersion);

window.v210Fmt = function(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(3);
  return String(v);
};

window.v210ClassColor = function(cls) {
  const c = String(cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
};

window.v210HeatColor = function(value, min, max) {
  const v = Number(value);
  if (!Number.isFinite(v)) return "rgba(100,116,139,0)";

  if (min === null || max === null || min === undefined || max === undefined || max === min) {
    return "rgb(56,189,248)";
  }

  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));

  if (t < 0.33) {
    const u = t / 0.33;
    return `rgb(${Math.round(30 + 40*u)}, ${Math.round(100 + 100*u)}, 255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${Math.round(70 + 185*u)}, ${Math.round(200 + 35*u)}, ${Math.round(255 - 210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255, ${Math.round(235 - 145*u)}, ${Math.round(45 - 10*u)})`;
};

window.v210ShowError = function(title, err, extra) {
  const visual = document.getElementById("visualPanel");
  const msg = err && err.stack ? err.stack : String(err || "Unknown error");

  if (!visual) {
    alert(title + ": " + msg);
    return;
  }

  visual.innerHTML = `
    <div style="padding:16px;border:1px solid rgba(239,68,68,0.45);border-radius:14px;background:rgba(127,29,29,0.22);color:#fecaca">
      <b>${title}</b>
      <pre style="white-space:pre-wrap;margin-top:10px;color:#fecaca;font-size:12px">${msg}</pre>
      ${extra ? `<pre style="white-space:pre-wrap;margin-top:10px;color:#fca5a5;font-size:12px">${extra}</pre>` : ""}
    </div>
  `;
};

window.selectWell = function(well) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found.");
    return;
  }

  input.value = `Show ${well}`;
  window.sendChat();
};

window.renderWellCardsV210 = function(block) {
  const d = block.data || {};
  const scores = d.scores || d.hm_scores || {};

  const rows = [
    ["Overall", scores.overall ?? d.overall_hm_score],
    ["Oil", scores.oil ?? d.oil_hm_score],
    ["Water", scores.water ?? d.water_hm_score],
    ["Gas", scores.gas ?? d.gas_hm_score],
    ["BHP", scores.bhp ?? d.bhp_hm_score],
  ];

  return `
    <div style="color:#e5e7eb;font-weight:800;margin:10px 0 8px">${block.title || d.well || "Well detail"}</div>
    <div class="visual-card-grid">
      ${rows.map(([label, value]) => `
        <div class="visual-card">
          <div class="visual-card-label">${label}</div>
          <div class="visual-card-value">${window.v210Fmt(value)}</div>
        </div>
      `).join("")}
    </div>
    ${d.recommended_action ? `<p style="color:#cbd5e1"><b>Recommended action:</b> ${d.recommended_action}</p>` : ""}
    ${d.interpretation ? `<p style="color:#cbd5e1"><b>Interpretation:</b> ${d.interpretation}</p>` : ""}
  `;
};

window.renderCellPropertyMap = function(block) {
  const visual = document.getElementById("visualPanel");

  try {
    if (!visual) throw new Error("visualPanel element not found.");

    const payload = block.payload || {};
    console.log("V210 renderCellPropertyMap payload:", payload);

    if (!payload.ok) {
      visual.innerHTML = `
        <div style="color:#e5e7eb;font-weight:800;margin-bottom:10px">${block.title || "Cell property map"}</div>
        <p style="color:#fca5a5">${payload.message || "Cell property layer not available."}</p>
        <pre style="white-space:pre-wrap;color:#94a3b8;font-size:12px">${JSON.stringify(payload, null, 2).slice(0, 2500)}</pre>
      `;
      return;
    }

    const mapId = "v210_cellmap_" + Date.now();
    const tooltipId = "v210_tooltip_" + Date.now();

    visual.innerHTML = `
      <div style="color:#e5e7eb;font-size:16px;font-weight:800;margin:8px 0">
        ${block.title || payload.label || payload.property}
      </div>
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">
        ${payload.message || ""}<br/>
        Grid: ${payload.nx} × ${payload.ny} × ${payload.nz} | Cells: ${payload.cell_count}
      </div>

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px">
        <button id="${mapId}_reset" style="padding:7px 10px;border-radius:999px;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.35);color:#bae6fd;font-size:12px">
          Reset zoom
        </button>
        <span style="color:#94a3b8;font-size:12px;align-self:center">
          Mouse wheel = zoom | drag = pan | hover = cell value | click well = detail
        </span>
      </div>

      <div id="${mapId}_shell" style="position:relative;width:100%;height:640px;border-radius:18px;overflow:hidden;border:1px solid rgba(148,163,184,0.18);background:#08111f;cursor:grab">
        <canvas id="${mapId}_canvas" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
        <div id="${mapId}_overlay" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto"></div>
      </div>

      <div style="margin-top:12px;padding:10px 12px;border:1px solid rgba(148,163,184,0.18);border-radius:14px;background:rgba(2,6,23,0.38)">
        <div style="color:#e5e7eb;font-size:13px;font-weight:800;margin-bottom:8px">
          ${payload.label || payload.property}${payload.unit ? " (" + payload.unit + ")" : ""}
        </div>
        <div style="height:14px;border-radius:999px;border:1px solid rgba(226,232,240,0.35);background:linear-gradient(90deg, rgb(30,100,255), rgb(70,200,255), rgb(255,235,45), rgb(255,90,35))"></div>
        <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:12px;margin-top:5px">
          <span>${window.v210Fmt(payload.p2 ?? payload.min)}</span>
          <span>low → high</span>
          <span>${window.v210Fmt(payload.p98 ?? payload.max)}</span>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:#cbd5e1;font-size:13px">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e;margin-right:6px"></span>Good</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#facc15;margin-right:6px"></span>Fair</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:6px"></span>Poor</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#94a3b8;margin-right:6px"></span>Inactive / Not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
        ${block.corridor_payload ? '<span style="color:#fde68a">■ Candidate corridor</span>' : ''}
      </div>

      <div id="${tooltipId}" style="position:fixed;display:none;z-index:9999;pointer-events:none;background:rgba(2,6,23,0.96);color:#e5e7eb;border:1px solid rgba(148,163,184,0.35);border-radius:10px;padding:8px 10px;font-size:12px;box-shadow:0 14px 35px rgba(0,0,0,0.35)"></div>
    `;

    requestAnimationFrame(() => {
      try {
        const shell = document.getElementById(`${mapId}_shell`);
        const canvas = document.getElementById(`${mapId}_canvas`);
        const overlay = document.getElementById(`${mapId}_overlay`);
        const tooltip = document.getElementById(tooltipId);
        const resetButton = document.getElementById(`${mapId}_reset`);

        if (!shell || !canvas || !overlay) throw new Error("Map shell/canvas/overlay not found.");

        const rect = shell.getBoundingClientRect();
        const W = rect.width || 900;
        const H = rect.height || 640;
        const pad = 42;

        const nx = Number(payload.nx);
        const ny = Number(payload.ny);

        if (!nx || !ny) throw new Error(`Invalid grid dimensions nx=${payload.nx}, ny=${payload.ny}`);

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(W * dpr);
        canvas.height = Math.floor(H * dpr);

        const ctx = canvas.getContext("2d");
        const plotW = W - 2 * pad;
        const plotH = H - 2 * pad;

        const minV = payload.p2 ?? payload.min;
        const maxV = payload.p98 ?? payload.max;

        const valueMap = new Map();

        for (const c of payload.cells || []) {
          const i = Number(c.i);
          const j = Number(c.j);
          const v = Number(c.value);
          if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;
          valueMap.set(`${i}_${j}`, v);
        }

        const state = {
          scale: 1,
          tx: 0,
          ty: 0,
          dragging: false,
          lastX: 0,
          lastY: 0,
          moved: false,
        };

        function baseX(i) {
          return pad + (Number(i) - 1) * plotW / nx;
        }

        function baseY(j) {
          return pad + (Number(j) - 1) * plotH / ny;
        }

        function screenXFromBase(x) {
          return state.tx + state.scale * x;
        }

        function screenYFromBase(y) {
          return state.ty + state.scale * y;
        }

        function baseFromScreenX(x) {
          return (x - state.tx) / state.scale;
        }

        function baseFromScreenY(y) {
          return (y - state.ty) / state.scale;
        }

        function drawCanvas() {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.clearRect(0, 0, W, H);

          ctx.fillStyle = "#08111f";
          ctx.fillRect(0, 0, W, H);

          ctx.save();
          ctx.translate(state.tx, state.ty);
          ctx.scale(state.scale, state.scale);

          ctx.strokeStyle = "rgba(148,163,184,0.10)";
          ctx.lineWidth = 1 / state.scale;

          for (let k = 0; k <= 8; k++) {
            const x = pad + k * plotW / 8;
            const y = pad + k * plotH / 8;

            ctx.beginPath();
            ctx.moveTo(x, pad);
            ctx.lineTo(x, H - pad);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(pad, y);
            ctx.lineTo(W - pad, y);
            ctx.stroke();
          }

          const cellW = Math.max(1, plotW / nx);
          const cellH = Math.max(1, plotH / ny);

          for (const c of payload.cells || []) {
            const i = Number(c.i);
            const j = Number(c.j);
            const v = Number(c.value);

            if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;

            const x = baseX(i);
            const y = baseY(j);

            ctx.fillStyle = window.v210HeatColor(v, minV, maxV);
            ctx.globalAlpha = 0.88;
            ctx.fillRect(x, y, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);
          }

          ctx.globalAlpha = 1.0;

          const corridorPayload = block.corridor_payload || null;
          const corridorCells = corridorPayload && corridorPayload.cells ? corridorPayload.cells : [];

          if (corridorCells.length > 0) {
            const maxDraw = 6500;
            const step = Math.max(1, Math.ceil(corridorCells.length / maxDraw));

            ctx.globalAlpha = 0.88;
            ctx.fillStyle = "rgba(255,220,80,0.92)";

            for (let idx = 0; idx < corridorCells.length; idx += step) {
              const c = corridorCells[idx];
              const i = Number(c.i);
              const j = Number(c.j);

              if (!Number.isFinite(i) || !Number.isFinite(j)) continue;

              const x = baseX(i);
              const y = baseY(j);

              ctx.fillRect(x, y, Math.max(3 / state.scale, cellW * 1.5), Math.max(3 / state.scale, cellH * 1.5));
            }

            ctx.globalAlpha = 1.0;
          }

          ctx.restore();
        }

        function drawOverlay() {
          let svg = `
            <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
              <defs>
                <filter id="v210WellGlow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>
          `;

          for (const w of payload.wells || []) {
            if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

            const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
            const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

            let role = "producer";
            if (injectorCandidate && !producerCandidate) role = "injector";

            const inactive = producerCandidate && w.active_producer === false;
            const cls = inactive ? "Inactive" : (w.overall_class || "Not Evaluated");
            const color = window.v210ClassColor(cls);

            const x = screenXFromBase(baseX(w.i));
            const y = screenYFromBase(baseY(w.j));

            if (x < -80 || y < -80 || x > W + 80 || y > H + 80) continue;

            if (role === "injector") {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                           fill="${color}" stroke="#e5e7eb" stroke-width="1.4" filter="url(#v210WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Injector | ${cls}</title>
                </g>
              `;
            } else {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${inactive ? 0.55 : 1}" filter="url(#v210WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Producer | ${cls}</title>
                </g>
              `;
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

        resetButton.addEventListener("click", () => {
          state.scale = 1;
          state.tx = 0;
          state.ty = 0;
          redraw();
        });

        shell.addEventListener("wheel", (ev) => {
          ev.preventDefault();

          const r = shell.getBoundingClientRect();
          const mx = ev.clientX - r.left;
          const my = ev.clientY - r.top;

          const oldScale = state.scale;
          const factor = ev.deltaY < 0 ? 1.18 : 1 / 1.18;
          const newScale = Math.max(0.55, Math.min(8.0, oldScale * factor));

          state.tx = mx - (newScale / oldScale) * (mx - state.tx);
          state.ty = my - (newScale / oldScale) * (my - state.ty);
          state.scale = newScale;

          redraw();
        }, { passive: false });

        shell.addEventListener("mousedown", (ev) => {
          state.dragging = true;
          state.moved = false;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;
          shell.style.cursor = "grabbing";
        });

        window.addEventListener("mousemove", (ev) => {
          if (!state.dragging) return;

          const dx = ev.clientX - state.lastX;
          const dy = ev.clientY - state.lastY;

          if (Math.abs(dx) + Math.abs(dy) > 2) state.moved = true;

          state.tx += dx;
          state.ty += dy;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;

          redraw();
        });

        window.addEventListener("mouseup", () => {
          state.dragging = false;
          shell.style.cursor = "grab";
        });

        shell.addEventListener("mousemove", (ev) => {
          const r = shell.getBoundingClientRect();
          const sx = ev.clientX - r.left;
          const sy = ev.clientY - r.top;

          const bx = baseFromScreenX(sx);
          const by = baseFromScreenY(sy);

          const i = Math.floor((bx - pad) / plotW * nx) + 1;
          const j = Math.floor((by - pad) / plotH * ny) + 1;

          if (i < 1 || j < 1 || i > nx || j > ny) {
            tooltip.style.display = "none";
            return;
          }

          const val = valueMap.get(`${i}_${j}`);

          tooltip.style.display = "block";
          tooltip.style.left = `${ev.clientX + 14}px`;
          tooltip.style.top = `${ev.clientY + 14}px`;
          tooltip.innerHTML = `
            <b>${payload.label || payload.property}</b><br/>
            I=${i}, J=${j}<br/>
            Value: ${window.v210Fmt(val)} ${payload.unit || ""}
          `;
        });

        shell.addEventListener("mouseleave", () => {
          tooltip.style.display = "none";
        });

        console.log("V210 cell map rendered successfully:", payload.property);

      } catch (err) {
        window.v210ShowError("Cell map rendering failed", err, JSON.stringify({
          property: payload.property,
          nx: payload.nx,
          ny: payload.ny,
          nz: payload.nz,
          cells: payload.cell_count,
          ok: payload.ok
        }, null, 2));
      }
    });

  } catch (err) {
    window.v210ShowError("Cell map setup failed", err);
  }
};

window.renderVisualResponse = function(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!answer || !visual) {
    alert("chatAnswer or visualPanel not found in DOM");
    return;
  }

  console.log("V210 renderVisualResponse:", data);

  const blocks = data.ui_blocks || [];
  let answerHtml = `<p>${data.answer || ""}</p>`;

  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual output...</p>`;

  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      window.renderCellPropertyMap(block);
    }

    else if (block.type === "well_cards") {
      answerHtml += window.renderWellCardsV210(block);
    }

    else if (block.type === "profile_series" && typeof window.renderProfileSeries === "function") {
      window.renderProfileSeries(block.data);
    }

    else if (block.type === "interactive_map" && typeof window.renderInteractiveMap === "function") {
      window.renderInteractiveMap(block);
    }

    else if (block.type === "compact_notes") {
      answerHtml += `
        <ul style="color:#cbd5e1">
          ${(block.items || []).map(x => `<li>${x}</li>`).join("")}
        </ul>
      `;
    }

    else if (block.type === "suggestions") {
      answerHtml += `
        <div class="quick-actions">
          ${(block.items || []).map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${x}</button>`).join("")}
        </div>
      `;
    }

    else if (block.type === "compact_table") {
      answerHtml += `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(block.rows || [], null, 2)}</pre>`;
    }
  }

  answer.innerHTML = answerHtml;
};

window.sendChat = async function() {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!input || !answer || !visual) {
    alert("Missing chatInput/chatAnswer/visualPanel elements.");
    return;
  }

  const msg = input.value.trim();
  if (!msg) return;

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const resp = await fetch("/api/agent-chat-v501", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg})
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${txt}`);
    }

    const data = await resp.json();
    console.log("V210 CHAT RESPONSE:", data);

    if (data.type === "visual_response") {
      window.renderVisualResponse(data);
      return;
    }

    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;
    visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed.</p>`;
    window.v210ShowError("Chat request failed", err);
  }
};

window.askQuick = function(text) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found");
    return;
  }
  input.value = text;
  window.sendChat();
};

console.log("V210 zoom/pan/click override ready. Test with: window.__visualPatchVersion");



// ==========================================================
// FINAL VISUAL OVERRIDE V220 - streamline overlay on cell maps
// ==========================================================
window.__visualPatchVersion = "V220_STREAMLINE_OVERLAY";
console.log("Loaded visual patch:", window.__visualPatchVersion);

window.v220Fmt = window.v210Fmt || window.v200Fmt || function(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(3);
  return String(v);
};

window.v220ClassColor = window.v210ClassColor || window.v200ClassColor || function(cls) {
  const c = String(cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
};

window.v220HeatColor = window.v210HeatColor || window.v200HeatColor;

window.v220ShowError = window.v210ShowError || window.v200ShowError || function(title, err) {
  alert(title + ": " + err);
};

window.renderCellPropertyMap = function(block) {
  const visual = document.getElementById("visualPanel");

  try {
    if (!visual) throw new Error("visualPanel element not found.");

    const payload = block.payload || {};
    const streamlinePayload = block.streamline_payload || null;
    const corridorPayload = block.corridor_payload || null;

    console.log("V220 renderCellPropertyMap payload:", payload);
    console.log("V220 streamline payload:", streamlinePayload);

    if (!payload.ok) {
      visual.innerHTML = `
        <div style="color:#e5e7eb;font-weight:800;margin-bottom:10px">${block.title || "Cell property map"}</div>
        <p style="color:#fca5a5">${payload.message || "Cell property layer not available."}</p>
        <pre style="white-space:pre-wrap;color:#94a3b8;font-size:12px">${JSON.stringify(payload, null, 2).slice(0, 2500)}</pre>
      `;
      return;
    }

    const mapId = "v220_cellmap_" + Date.now();
    const tooltipId = "v220_tooltip_" + Date.now();

    const streamlineCount = streamlinePayload && streamlinePayload.lines ? streamlinePayload.lines.length : 0;

    visual.innerHTML = `
      <div style="color:#e5e7eb;font-size:16px;font-weight:800;margin:8px 0">
        ${block.title || payload.label || payload.property}
      </div>
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">
        ${payload.message || ""}<br/>
        Grid: ${payload.nx} × ${payload.ny} × ${payload.nz} | Cells: ${payload.cell_count}
        ${streamlinePayload ? ` | Streamlines/links: ${streamlineCount}` : ""}
      </div>

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px">
        <button id="${mapId}_reset" style="padding:7px 10px;border-radius:999px;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.35);color:#bae6fd;font-size:12px">
          Reset zoom
        </button>
        <span style="color:#94a3b8;font-size:12px;align-self:center">
          Mouse wheel = zoom | drag = pan | hover = cell value | click well = detail
        </span>
      </div>

      <div id="${mapId}_shell" style="position:relative;width:100%;height:640px;border-radius:18px;overflow:hidden;border:1px solid rgba(148,163,184,0.18);background:#08111f;cursor:grab">
        <canvas id="${mapId}_canvas" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
        <div id="${mapId}_overlay" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto"></div>
      </div>

      <div style="margin-top:12px;padding:10px 12px;border:1px solid rgba(148,163,184,0.18);border-radius:14px;background:rgba(2,6,23,0.38)">
        <div style="color:#e5e7eb;font-size:13px;font-weight:800;margin-bottom:8px">
          ${payload.label || payload.property}${payload.unit ? " (" + payload.unit + ")" : ""}
        </div>
        <div style="height:14px;border-radius:999px;border:1px solid rgba(226,232,240,0.35);background:linear-gradient(90deg, rgb(30,100,255), rgb(70,200,255), rgb(255,235,45), rgb(255,90,35))"></div>
        <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:12px;margin-top:5px">
          <span>${window.v220Fmt(payload.p2 ?? payload.min)}</span>
          <span>low → high</span>
          <span>${window.v220Fmt(payload.p98 ?? payload.max)}</span>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:#cbd5e1;font-size:13px">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e;margin-right:6px"></span>Good</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#facc15;margin-right:6px"></span>Fair</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:6px"></span>Poor</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#94a3b8;margin-right:6px"></span>Inactive / Not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
        ${corridorPayload ? '<span style="color:#fde68a">■ Candidate corridor</span>' : ''}
        ${streamlinePayload ? '<span style="color:#67e8f9">— Streamline / connectivity</span>' : ''}
      </div>

      ${streamlinePayload && !streamlinePayload.ok ? `<p style="color:#fca5a5;margin-top:8px">${streamlinePayload.message || "No streamlines found."}</p>` : ""}

      <div id="${tooltipId}" style="position:fixed;display:none;z-index:9999;pointer-events:none;background:rgba(2,6,23,0.96);color:#e5e7eb;border:1px solid rgba(148,163,184,0.35);border-radius:10px;padding:8px 10px;font-size:12px;box-shadow:0 14px 35px rgba(0,0,0,0.35)"></div>
    `;

    requestAnimationFrame(() => {
      try {
        const shell = document.getElementById(`${mapId}_shell`);
        const canvas = document.getElementById(`${mapId}_canvas`);
        const overlay = document.getElementById(`${mapId}_overlay`);
        const tooltip = document.getElementById(tooltipId);
        const resetButton = document.getElementById(`${mapId}_reset`);

        if (!shell || !canvas || !overlay) throw new Error("Map shell/canvas/overlay not found.");

        const rect = shell.getBoundingClientRect();
        const W = rect.width || 900;
        const H = rect.height || 640;
        const pad = 42;

        const nx = Number(payload.nx);
        const ny = Number(payload.ny);

        if (!nx || !ny) throw new Error(`Invalid grid dimensions nx=${payload.nx}, ny=${payload.ny}`);

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(W * dpr);
        canvas.height = Math.floor(H * dpr);

        const ctx = canvas.getContext("2d");
        const plotW = W - 2 * pad;
        const plotH = H - 2 * pad;

        const minV = payload.p2 ?? payload.min;
        const maxV = payload.p98 ?? payload.max;

        const valueMap = new Map();

        for (const c of payload.cells || []) {
          const i = Number(c.i);
          const j = Number(c.j);
          const v = Number(c.value);
          if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;
          valueMap.set(`${i}_${j}`, v);
        }

        const state = {
          scale: 1,
          tx: 0,
          ty: 0,
          dragging: false,
          lastX: 0,
          lastY: 0,
        };

        function baseX(i) {
          return pad + (Number(i) - 1) * plotW / nx;
        }

        function baseY(j) {
          return pad + (Number(j) - 1) * plotH / ny;
        }

        function screenXFromBase(x) {
          return state.tx + state.scale * x;
        }

        function screenYFromBase(y) {
          return state.ty + state.scale * y;
        }

        function baseFromScreenX(x) {
          return (x - state.tx) / state.scale;
        }

        function baseFromScreenY(y) {
          return (y - state.ty) / state.scale;
        }

        function drawCanvas() {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.clearRect(0, 0, W, H);

          ctx.fillStyle = "#08111f";
          ctx.fillRect(0, 0, W, H);

          ctx.save();
          ctx.translate(state.tx, state.ty);
          ctx.scale(state.scale, state.scale);

          ctx.strokeStyle = "rgba(148,163,184,0.10)";
          ctx.lineWidth = 1 / state.scale;

          for (let k = 0; k <= 8; k++) {
            const x = pad + k * plotW / 8;
            const y = pad + k * plotH / 8;

            ctx.beginPath();
            ctx.moveTo(x, pad);
            ctx.lineTo(x, H - pad);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(pad, y);
            ctx.lineTo(W - pad, y);
            ctx.stroke();
          }

          const cellW = Math.max(1, plotW / nx);
          const cellH = Math.max(1, plotH / ny);

          for (const c of payload.cells || []) {
            const i = Number(c.i);
            const j = Number(c.j);
            const v = Number(c.value);

            if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;

            const x = baseX(i);
            const y = baseY(j);

            ctx.fillStyle = window.v220HeatColor(v, minV, maxV);
            ctx.globalAlpha = 0.88;
            ctx.fillRect(x, y, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);
          }

          ctx.globalAlpha = 1.0;

          if (corridorPayload && corridorPayload.cells && corridorPayload.cells.length > 0) {
            const cells = corridorPayload.cells;
            const maxDraw = 6500;
            const step = Math.max(1, Math.ceil(cells.length / maxDraw));

            ctx.globalAlpha = 0.88;
            ctx.fillStyle = "rgba(255,220,80,0.92)";

            for (let idx = 0; idx < cells.length; idx += step) {
              const c = cells[idx];
              const i = Number(c.i);
              const j = Number(c.j);

              if (!Number.isFinite(i) || !Number.isFinite(j)) continue;

              const x = baseX(i);
              const y = baseY(j);

              ctx.fillRect(x, y, Math.max(3 / state.scale, cellW * 1.5), Math.max(3 / state.scale, cellH * 1.5));
            }

            ctx.globalAlpha = 1.0;
          }

          ctx.restore();
        }

        function linePath(points) {
          if (!points || points.length < 2) return "";

          return points.map((p, idx) => {
            const x = screenXFromBase(baseX(p.i));
            const y = screenYFromBase(baseY(p.j));
            return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
          }).join(" ");
        }

        function drawOverlay() {
          let svg = `
            <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
              <defs>
                <filter id="v220WellGlow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
                <marker id="arrowCyan" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L7,3 z" fill="#67e8f9" opacity="0.85" />
                </marker>
              </defs>
          `;

          // Streamline/connectivity lines first, behind wells.
          const lines = streamlinePayload && streamlinePayload.lines ? streamlinePayload.lines : [];

          const maxLines = 450;
          const step = Math.max(1, Math.ceil(lines.length / maxLines));

          for (let idx = 0; idx < lines.length; idx += step) {
            const line = lines[idx];
            const d = linePath(line.points || []);
            if (!d) continue;

            const strength = Number(line.strength || 1);
            const width = Math.max(1.2, Math.min(5.0, 1.2 + Math.log10(1 + strength)));

            svg += `
              <path d="${d}" fill="none" stroke="#67e8f9" stroke-width="${width}" opacity="0.50"
                    stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrowCyan)">
                <title>${line.injector || "source"} → ${line.producer || "producer"} | strength=${window.v220Fmt(strength)}</title>
              </path>
            `;
          }

          // Wells.
          for (const w of payload.wells || []) {
            if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

            const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
            const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

            let role = "producer";
            if (injectorCandidate && !producerCandidate) role = "injector";

            const inactive = producerCandidate && w.active_producer === false;
            const cls = inactive ? "Inactive" : (w.overall_class || "Not Evaluated");
            const color = window.v220ClassColor(cls);

            const x = screenXFromBase(baseX(w.i));
            const y = screenYFromBase(baseY(w.j));

            if (x < -100 || y < -100 || x > W + 100 || y > H + 100) continue;

            if (role === "injector") {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                           fill="${color}" stroke="#e5e7eb" stroke-width="1.4" filter="url(#v220WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Injector | ${cls}</title>
                </g>
              `;
            } else {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${inactive ? 0.55 : 1}" filter="url(#v220WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Producer | ${cls}</title>
                </g>
              `;
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

        resetButton.addEventListener("click", () => {
          state.scale = 1;
          state.tx = 0;
          state.ty = 0;
          redraw();
        });

        shell.addEventListener("wheel", (ev) => {
          ev.preventDefault();

          const r = shell.getBoundingClientRect();
          const mx = ev.clientX - r.left;
          const my = ev.clientY - r.top;

          const oldScale = state.scale;
          const factor = ev.deltaY < 0 ? 1.18 : 1 / 1.18;
          const newScale = Math.max(0.55, Math.min(8.0, oldScale * factor));

          state.tx = mx - (newScale / oldScale) * (mx - state.tx);
          state.ty = my - (newScale / oldScale) * (my - state.ty);
          state.scale = newScale;

          redraw();
        }, { passive: false });

        shell.addEventListener("mousedown", (ev) => {
          state.dragging = true;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;
          shell.style.cursor = "grabbing";
        });

        window.addEventListener("mousemove", (ev) => {
          if (!state.dragging) return;

          const dx = ev.clientX - state.lastX;
          const dy = ev.clientY - state.lastY;

          state.tx += dx;
          state.ty += dy;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;

          redraw();
        });

        window.addEventListener("mouseup", () => {
          state.dragging = false;
          shell.style.cursor = "grab";
        });

        shell.addEventListener("mousemove", (ev) => {
          const r = shell.getBoundingClientRect();
          const sx = ev.clientX - r.left;
          const sy = ev.clientY - r.top;

          const bx = baseFromScreenX(sx);
          const by = baseFromScreenY(sy);

          const i = Math.floor((bx - pad) / plotW * nx) + 1;
          const j = Math.floor((by - pad) / plotH * ny) + 1;

          if (i < 1 || j < 1 || i > nx || j > ny) {
            tooltip.style.display = "none";
            return;
          }

          const val = valueMap.get(`${i}_${j}`);

          tooltip.style.display = "block";
          tooltip.style.left = `${ev.clientX + 14}px`;
          tooltip.style.top = `${ev.clientY + 14}px`;
          tooltip.innerHTML = `
            <b>${payload.label || payload.property}</b><br/>
            I=${i}, J=${j}<br/>
            Value: ${window.v220Fmt(val)} ${payload.unit || ""}
          `;
        });

        shell.addEventListener("mouseleave", () => {
          tooltip.style.display = "none";
        });

        console.log("V220 cell map rendered successfully:", payload.property);

      } catch (err) {
        window.v220ShowError("Cell map rendering failed", err, JSON.stringify({
          property: payload.property,
          nx: payload.nx,
          ny: payload.ny,
          nz: payload.nz,
          cells: payload.cell_count,
          ok: payload.ok
        }, null, 2));
      }
    });

  } catch (err) {
    window.v220ShowError("Cell map setup failed", err);
  }
};

window.renderVisualResponse = function(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!answer || !visual) {
    alert("chatAnswer or visualPanel not found in DOM");
    return;
  }

  console.log("V220 renderVisualResponse:", data);

  const blocks = data.ui_blocks || [];
  let answerHtml = `<p>${data.answer || ""}</p>`;

  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual output...</p>`;

  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      window.renderCellPropertyMap(block);
    }

    else if (block.type === "well_cards" && window.renderWellCardsV210) {
      answerHtml += window.renderWellCardsV210(block);
    }

    else if (block.type === "profile_series" && typeof window.renderProfileSeries === "function") {
      window.renderProfileSeries(block.data);
    }

    else if (block.type === "interactive_map" && typeof window.renderInteractiveMap === "function") {
      window.renderInteractiveMap(block);
    }

    else if (block.type === "compact_notes") {
      answerHtml += `
        <ul style="color:#cbd5e1">
          ${(block.items || []).map(x => `<li>${x}</li>`).join("")}
        </ul>
      `;
    }

    else if (block.type === "suggestions") {
      answerHtml += `
        <div class="quick-actions">
          ${(block.items || []).map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${x}</button>`).join("")}
        </div>
      `;
    }

    else if (block.type === "compact_table") {
      answerHtml += `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(block.rows || [], null, 2)}</pre>`;
    }
  }

  answer.innerHTML = answerHtml;
};

window.sendChat = async function() {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!input || !answer || !visual) {
    alert("Missing chatInput/chatAnswer/visualPanel elements.");
    return;
  }

  const msg = input.value.trim();
  if (!msg) return;

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const resp = await fetch("/api/agent-chat-v501", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg})
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${txt}`);
    }

    const data = await resp.json();
    console.log("V220 CHAT RESPONSE:", data);

    if (data.type === "visual_response") {
      window.renderVisualResponse(data);
      return;
    }

    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;
    visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed.</p>`;
    window.v220ShowError("Chat request failed", err);
  }
};

window.askQuick = function(text) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found");
    return;
  }
  input.value = text;
  window.sendChat();
};

console.log("V220 streamline overlay override ready. Test with: window.__visualPatchVersion");



// ==========================================================
// FINAL VISUAL OVERRIDE V210 - zoom/pan + clickable wells
// ==========================================================
window.__visualPatchVersion = "V210_ZOOM_PAN_CLICK_WELLS";
console.log("Loaded visual patch:", window.__visualPatchVersion);

window.v210Fmt = function(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(3);
  return String(v);
};

window.v210ClassColor = function(cls) {
  const c = String(cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
};

window.v210HeatColor = function(value, min, max) {
  const v = Number(value);
  if (!Number.isFinite(v)) return "rgba(100,116,139,0)";

  if (min === null || max === null || min === undefined || max === undefined || max === min) {
    return "rgb(56,189,248)";
  }

  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));

  if (t < 0.33) {
    const u = t / 0.33;
    return `rgb(${Math.round(30 + 40*u)}, ${Math.round(100 + 100*u)}, 255)`;
  }

  if (t < 0.66) {
    const u = (t - 0.33) / 0.33;
    return `rgb(${Math.round(70 + 185*u)}, ${Math.round(200 + 35*u)}, ${Math.round(255 - 210*u)})`;
  }

  const u = (t - 0.66) / 0.34;
  return `rgb(255, ${Math.round(235 - 145*u)}, ${Math.round(45 - 10*u)})`;
};

window.v210ShowError = function(title, err, extra) {
  const visual = document.getElementById("visualPanel");
  const msg = err && err.stack ? err.stack : String(err || "Unknown error");

  if (!visual) {
    alert(title + ": " + msg);
    return;
  }

  visual.innerHTML = `
    <div style="padding:16px;border:1px solid rgba(239,68,68,0.45);border-radius:14px;background:rgba(127,29,29,0.22);color:#fecaca">
      <b>${title}</b>
      <pre style="white-space:pre-wrap;margin-top:10px;color:#fecaca;font-size:12px">${msg}</pre>
      ${extra ? `<pre style="white-space:pre-wrap;margin-top:10px;color:#fca5a5;font-size:12px">${extra}</pre>` : ""}
    </div>
  `;
};

window.selectWell = function(well) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found.");
    return;
  }

  input.value = `Show ${well}`;
  window.sendChat();
};

window.renderWellCardsV210 = function(block) {
  const d = block.data || {};
  const scores = d.scores || d.hm_scores || {};

  const rows = [
    ["Overall", scores.overall ?? d.overall_hm_score],
    ["Oil", scores.oil ?? d.oil_hm_score],
    ["Water", scores.water ?? d.water_hm_score],
    ["Gas", scores.gas ?? d.gas_hm_score],
    ["BHP", scores.bhp ?? d.bhp_hm_score],
  ];

  return `
    <div style="color:#e5e7eb;font-weight:800;margin:10px 0 8px">${block.title || d.well || "Well detail"}</div>
    <div class="visual-card-grid">
      ${rows.map(([label, value]) => `
        <div class="visual-card">
          <div class="visual-card-label">${label}</div>
          <div class="visual-card-value">${window.v210Fmt(value)}</div>
        </div>
      `).join("")}
    </div>
    ${d.recommended_action ? `<p style="color:#cbd5e1"><b>Recommended action:</b> ${d.recommended_action}</p>` : ""}
    ${d.interpretation ? `<p style="color:#cbd5e1"><b>Interpretation:</b> ${d.interpretation}</p>` : ""}
  `;
};

window.renderCellPropertyMap = function(block) {
  const visual = document.getElementById("visualPanel");

  try {
    if (!visual) throw new Error("visualPanel element not found.");

    const payload = block.payload || {};
    console.log("V210 renderCellPropertyMap payload:", payload);

    if (!payload.ok) {
      visual.innerHTML = `
        <div style="color:#e5e7eb;font-weight:800;margin-bottom:10px">${block.title || "Cell property map"}</div>
        <p style="color:#fca5a5">${payload.message || "Cell property layer not available."}</p>
        <pre style="white-space:pre-wrap;color:#94a3b8;font-size:12px">${JSON.stringify(payload, null, 2).slice(0, 2500)}</pre>
      `;
      return;
    }

    const mapId = "v210_cellmap_" + Date.now();
    const tooltipId = "v210_tooltip_" + Date.now();

    visual.innerHTML = `
      <div style="color:#e5e7eb;font-size:16px;font-weight:800;margin:8px 0">
        ${block.title || payload.label || payload.property}
      </div>
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">
        ${payload.message || ""}<br/>
        Grid: ${payload.nx} × ${payload.ny} × ${payload.nz} | Cells: ${payload.cell_count}
      </div>

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px">
        <button id="${mapId}_reset" style="padding:7px 10px;border-radius:999px;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.35);color:#bae6fd;font-size:12px">
          Reset zoom
        </button>
        <span style="color:#94a3b8;font-size:12px;align-self:center">
          Mouse wheel = zoom | drag = pan | hover = cell value | click well = detail
        </span>
      </div>

      <div id="${mapId}_shell" style="position:relative;width:100%;height:640px;border-radius:18px;overflow:hidden;border:1px solid rgba(148,163,184,0.18);background:#08111f;cursor:grab">
        <canvas id="${mapId}_canvas" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
        <div id="${mapId}_overlay" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto"></div>
      </div>

      <div style="margin-top:12px;padding:10px 12px;border:1px solid rgba(148,163,184,0.18);border-radius:14px;background:rgba(2,6,23,0.38)">
        <div style="color:#e5e7eb;font-size:13px;font-weight:800;margin-bottom:8px">
          ${payload.label || payload.property}${payload.unit ? " (" + payload.unit + ")" : ""}
        </div>
        <div style="height:14px;border-radius:999px;border:1px solid rgba(226,232,240,0.35);background:linear-gradient(90deg, rgb(30,100,255), rgb(70,200,255), rgb(255,235,45), rgb(255,90,35))"></div>
        <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:12px;margin-top:5px">
          <span>${window.v210Fmt(payload.p2 ?? payload.min)}</span>
          <span>low → high</span>
          <span>${window.v210Fmt(payload.p98 ?? payload.max)}</span>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:#cbd5e1;font-size:13px">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#22c55e;margin-right:6px"></span>Good</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#facc15;margin-right:6px"></span>Fair</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ef4444;margin-right:6px"></span>Poor</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#94a3b8;margin-right:6px"></span>Inactive / Not evaluated</span>
        <span>● Producer</span>
        <span>◆ Injector</span>
        ${block.corridor_payload ? '<span style="color:#fde68a">■ Candidate corridor</span>' : ''}
      </div>

      <div id="${tooltipId}" style="position:fixed;display:none;z-index:9999;pointer-events:none;background:rgba(2,6,23,0.96);color:#e5e7eb;border:1px solid rgba(148,163,184,0.35);border-radius:10px;padding:8px 10px;font-size:12px;box-shadow:0 14px 35px rgba(0,0,0,0.35)"></div>
    `;

    requestAnimationFrame(() => {
      try {
        const shell = document.getElementById(`${mapId}_shell`);
        const canvas = document.getElementById(`${mapId}_canvas`);
        const overlay = document.getElementById(`${mapId}_overlay`);
        const tooltip = document.getElementById(tooltipId);
        const resetButton = document.getElementById(`${mapId}_reset`);

        if (!shell || !canvas || !overlay) throw new Error("Map shell/canvas/overlay not found.");

        const rect = shell.getBoundingClientRect();
        const W = rect.width || 900;
        const H = rect.height || 640;
        const pad = 42;

        const nx = Number(payload.nx);
        const ny = Number(payload.ny);

        if (!nx || !ny) throw new Error(`Invalid grid dimensions nx=${payload.nx}, ny=${payload.ny}`);

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(W * dpr);
        canvas.height = Math.floor(H * dpr);

        const ctx = canvas.getContext("2d");
        const plotW = W - 2 * pad;
        const plotH = H - 2 * pad;

        const minV = payload.p2 ?? payload.min;
        const maxV = payload.p98 ?? payload.max;

        const valueMap = new Map();

        for (const c of payload.cells || []) {
          const i = Number(c.i);
          const j = Number(c.j);
          const v = Number(c.value);
          if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;
          valueMap.set(`${i}_${j}`, v);
        }

        const state = {
          scale: 1,
          tx: 0,
          ty: 0,
          dragging: false,
          lastX: 0,
          lastY: 0,
          moved: false,
        };

        function baseX(i) {
          return pad + (Number(i) - 1) * plotW / nx;
        }

        function baseY(j) {
          return pad + (Number(j) - 1) * plotH / ny;
        }

        function screenXFromBase(x) {
          return state.tx + state.scale * x;
        }

        function screenYFromBase(y) {
          return state.ty + state.scale * y;
        }

        function baseFromScreenX(x) {
          return (x - state.tx) / state.scale;
        }

        function baseFromScreenY(y) {
          return (y - state.ty) / state.scale;
        }

        function drawCanvas() {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          ctx.clearRect(0, 0, W, H);

          ctx.fillStyle = "#08111f";
          ctx.fillRect(0, 0, W, H);

          ctx.save();
          ctx.translate(state.tx, state.ty);
          ctx.scale(state.scale, state.scale);

          ctx.strokeStyle = "rgba(148,163,184,0.10)";
          ctx.lineWidth = 1 / state.scale;

          for (let k = 0; k <= 8; k++) {
            const x = pad + k * plotW / 8;
            const y = pad + k * plotH / 8;

            ctx.beginPath();
            ctx.moveTo(x, pad);
            ctx.lineTo(x, H - pad);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(pad, y);
            ctx.lineTo(W - pad, y);
            ctx.stroke();
          }

          const cellW = Math.max(1, plotW / nx);
          const cellH = Math.max(1, plotH / ny);

          for (const c of payload.cells || []) {
            const i = Number(c.i);
            const j = Number(c.j);
            const v = Number(c.value);

            if (!Number.isFinite(i) || !Number.isFinite(j) || !Number.isFinite(v)) continue;

            const x = baseX(i);
            const y = baseY(j);

            ctx.fillStyle = window.v210HeatColor(v, minV, maxV);
            ctx.globalAlpha = 0.88;
            ctx.fillRect(x, y, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);
          }

          ctx.globalAlpha = 1.0;

          const corridorPayload = block.corridor_payload || null;
          const corridorCells = corridorPayload && corridorPayload.cells ? corridorPayload.cells : [];

          if (corridorCells.length > 0) {
            const maxDraw = 6500;
            const step = Math.max(1, Math.ceil(corridorCells.length / maxDraw));

            ctx.globalAlpha = 0.88;
            ctx.fillStyle = "rgba(255,220,80,0.92)";

            for (let idx = 0; idx < corridorCells.length; idx += step) {
              const c = corridorCells[idx];
              const i = Number(c.i);
              const j = Number(c.j);

              if (!Number.isFinite(i) || !Number.isFinite(j)) continue;

              const x = baseX(i);
              const y = baseY(j);

              ctx.fillRect(x, y, Math.max(3 / state.scale, cellW * 1.5), Math.max(3 / state.scale, cellH * 1.5));
            }

            ctx.globalAlpha = 1.0;
          }

          ctx.restore();
        }

        function drawOverlay() {
          let svg = `
            <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="width:100%;height:100%">
              <defs>
                <filter id="v210WellGlow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>
          `;

          for (const w of payload.wells || []) {
            if (w.i === null || w.i === undefined || w.j === null || w.j === undefined) continue;

            const producerCandidate = !!w.producer_candidate || w.well_role === "producer" || w.well_role === "producer_injector";
            const injectorCandidate = !!w.injector_candidate || w.well_role === "injector" || w.well_role === "producer_injector";

            let role = "producer";
            if (injectorCandidate && !producerCandidate) role = "injector";

            const inactive = producerCandidate && w.active_producer === false;
            const cls = inactive ? "Inactive" : (w.overall_class || "Not Evaluated");
            const color = window.v210ClassColor(cls);

            const x = screenXFromBase(baseX(w.i));
            const y = screenYFromBase(baseY(w.j));

            if (x < -80 || y < -80 || x > W + 80 || y > H + 80) continue;

            if (role === "injector") {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <polygon points="${x},${y-11} ${x+11},${y} ${x},${y+11} ${x-11},${y}"
                           fill="${color}" stroke="#e5e7eb" stroke-width="1.4" filter="url(#v210WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Injector | ${cls}</title>
                </g>
              `;
            } else {
              svg += `
                <g onclick="window.selectWell('${w.well}')" style="cursor:pointer">
                  <circle cx="${x}" cy="${y}" r="9" fill="${color}" stroke="#e5e7eb" stroke-width="1.4" opacity="${inactive ? 0.55 : 1}" filter="url(#v210WellGlow)" />
                  <text x="${x + 13}" y="${y - 10}" fill="#e5e7eb" font-size="11">${w.well}</text>
                  <title>${w.well} | Producer | ${cls}</title>
                </g>
              `;
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

        resetButton.addEventListener("click", () => {
          state.scale = 1;
          state.tx = 0;
          state.ty = 0;
          redraw();
        });

        shell.addEventListener("wheel", (ev) => {
          ev.preventDefault();

          const r = shell.getBoundingClientRect();
          const mx = ev.clientX - r.left;
          const my = ev.clientY - r.top;

          const oldScale = state.scale;
          const factor = ev.deltaY < 0 ? 1.18 : 1 / 1.18;
          const newScale = Math.max(0.55, Math.min(8.0, oldScale * factor));

          state.tx = mx - (newScale / oldScale) * (mx - state.tx);
          state.ty = my - (newScale / oldScale) * (my - state.ty);
          state.scale = newScale;

          redraw();
        }, { passive: false });

        shell.addEventListener("mousedown", (ev) => {
          state.dragging = true;
          state.moved = false;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;
          shell.style.cursor = "grabbing";
        });

        window.addEventListener("mousemove", (ev) => {
          if (!state.dragging) return;

          const dx = ev.clientX - state.lastX;
          const dy = ev.clientY - state.lastY;

          if (Math.abs(dx) + Math.abs(dy) > 2) state.moved = true;

          state.tx += dx;
          state.ty += dy;
          state.lastX = ev.clientX;
          state.lastY = ev.clientY;

          redraw();
        });

        window.addEventListener("mouseup", () => {
          state.dragging = false;
          shell.style.cursor = "grab";
        });

        shell.addEventListener("mousemove", (ev) => {
          const r = shell.getBoundingClientRect();
          const sx = ev.clientX - r.left;
          const sy = ev.clientY - r.top;

          const bx = baseFromScreenX(sx);
          const by = baseFromScreenY(sy);

          const i = Math.floor((bx - pad) / plotW * nx) + 1;
          const j = Math.floor((by - pad) / plotH * ny) + 1;

          if (i < 1 || j < 1 || i > nx || j > ny) {
            tooltip.style.display = "none";
            return;
          }

          const val = valueMap.get(`${i}_${j}`);

          tooltip.style.display = "block";
          tooltip.style.left = `${ev.clientX + 14}px`;
          tooltip.style.top = `${ev.clientY + 14}px`;
          tooltip.innerHTML = `
            <b>${payload.label || payload.property}</b><br/>
            I=${i}, J=${j}<br/>
            Value: ${window.v210Fmt(val)} ${payload.unit || ""}
          `;
        });

        shell.addEventListener("mouseleave", () => {
          tooltip.style.display = "none";
        });

        console.log("V210 cell map rendered successfully:", payload.property);

      } catch (err) {
        window.v210ShowError("Cell map rendering failed", err, JSON.stringify({
          property: payload.property,
          nx: payload.nx,
          ny: payload.ny,
          nz: payload.nz,
          cells: payload.cell_count,
          ok: payload.ok
        }, null, 2));
      }
    });

  } catch (err) {
    window.v210ShowError("Cell map setup failed", err);
  }
};

window.renderVisualResponse = function(data) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!answer || !visual) {
    alert("chatAnswer or visualPanel not found in DOM");
    return;
  }

  console.log("V210 renderVisualResponse:", data);

  const blocks = data.ui_blocks || [];
  let answerHtml = `<p>${data.answer || ""}</p>`;

  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual output...</p>`;

  for (const block of blocks) {
    if (block.type === "cell_property_map") {
      window.renderCellPropertyMap(block);
    }

    else if (block.type === "well_cards") {
      answerHtml += window.renderWellCardsV210(block);
    }

    else if (block.type === "profile_series" && typeof window.renderProfileSeries === "function") {
      window.renderProfileSeries(block.data);
    }

    else if (block.type === "interactive_map" && typeof window.renderInteractiveMap === "function") {
      window.renderInteractiveMap(block);
    }

    else if (block.type === "compact_notes") {
      answerHtml += `
        <ul style="color:#cbd5e1">
          ${(block.items || []).map(x => `<li>${x}</li>`).join("")}
        </ul>
      `;
    }

    else if (block.type === "suggestions") {
      answerHtml += `
        <div class="quick-actions">
          ${(block.items || []).map(x => `<button onclick="askQuick('${String(x).replaceAll("'", "\\'")}')">${x}</button>`).join("")}
        </div>
      `;
    }

    else if (block.type === "compact_table") {
      answerHtml += `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(block.rows || [], null, 2)}</pre>`;
    }
  }

  answer.innerHTML = answerHtml;
};

window.sendChat = async function() {
  const input = document.getElementById("chatInput");
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (!input || !answer || !visual) {
    alert("Missing chatInput/chatAnswer/visualPanel elements.");
    return;
  }

  const msg = input.value.trim();
  if (!msg) return;

  answer.innerHTML = `<p>Thinking...</p>`;
  visual.innerHTML = `<p style="color:#94a3b8">Preparing visual evidence...</p>`;

  try {
    const resp = await fetch("/api/agent-chat-v501", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg})
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${txt}`);
    }

    const data = await resp.json();
    console.log("V210 CHAT RESPONSE:", data);

    if (data.type === "visual_response") {
      window.renderVisualResponse(data);
      return;
    }

    answer.innerHTML = `<p>${data.answer || "No answer."}</p>`;
    visual.innerHTML = `<pre style="white-space:pre-wrap;color:#94a3b8">${JSON.stringify(data.data || {}, null, 2)}</pre>`;

  } catch (err) {
    answer.innerHTML = `<p style="color:#fca5a5">Chat request failed.</p>`;
    window.v210ShowError("Chat request failed", err);
  }
};

window.askQuick = function(text) {
  const input = document.getElementById("chatInput");
  if (!input) {
    alert("chatInput not found");
    return;
  }
  input.value = text;
  window.sendChat();
};

console.log("V210 zoom/pan/click override ready. Test with: window.__visualPatchVersion");



// ==========================================================
// DASHBOARD GRAPHICS V230 - 5 KPI cards + right well insight
// ==========================================================
window.__dashboardGraphicsPatch = "V230_5_KPI_AND_WELL_INSIGHT";
console.log("Loaded dashboard graphics patch:", window.__dashboardGraphicsPatch);

window.v230Fmt = function(v) {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(1);
  return String(v);
};

window.v230ClassColor = function(cls) {
  const c = String(cls || "").toLowerCase();
  if (c === "good") return "#22c55e";
  if (c === "fair") return "#facc15";
  if (c === "poor") return "#ef4444";
  return "#94a3b8";
};

window.ensureTopKpiContainerV230 = function() {
  let container = document.getElementById("topKpiCardsV230");

  if (container) return container;

  const main = document.querySelector("main") || document.body;

  container = document.createElement("section");
  container.id = "topKpiCardsV230";
  container.className = "top-kpi-v230";

  main.insertBefore(container, main.firstChild);

  return container;
};

window.hideOldInactiveAndCorridorCardsV230 = function() {
  const badTexts = [
    "inactive wells",
    "candidate corridors",
    "inactive",
    "corridors"
  ];

  const possibleCards = Array.from(document.querySelectorAll(".card, .metric-card, .summary-card, .kpi-card, .visual-card, section div"));

  for (const el of possibleCards) {
    const txt = String(el.innerText || "").trim().toLowerCase();

    if (!txt) continue;

    if (badTexts.some(x => txt === x || txt.startsWith(x + "\n") || txt.includes("candidate corridors"))) {
      el.style.display = "none";
    }
  }

  // Any visible KPI grid with 5 cards should occupy full width.
  const grids = Array.from(document.querySelectorAll(".cards, .summary-grid, .kpi-grid, .metric-grid, .visual-card-grid"));

  for (const g of grids) {
    const visibleChildren = Array.from(g.children).filter(c => c.offsetParent !== null);

    if (visibleChildren.length === 5) {
      g.style.gridTemplateColumns = "repeat(5, minmax(0, 1fr))";
      g.style.width = "100%";
    }
  }
};

window.renderTopKpisV230 = function(payload) {
  const container = window.ensureTopKpiContainerV230();
  const cards = payload.cards || [];

  container.innerHTML = `
    <div class="top-kpi-title-v230">History Match Quality</div>
    <div class="top-kpi-grid-v230">
      ${cards.map(card => {
        const color = window.v230ClassColor(card.class);
        return `
          <div class="top-kpi-card-v230">
            <div class="top-kpi-label-v230">${card.label}</div>
            <div class="top-kpi-score-v230" style="color:${color}">${window.v230Fmt(card.score)}</div>
            <div class="top-kpi-class-v230">${card.class || "Not Evaluated"}</div>
            <div class="top-kpi-sub-v230">${card.subtext || ""}</div>
          </div>
        `;
      }).join("")}
    </div>
  `;

  window.hideOldInactiveAndCorridorCardsV230();
};

window.loadTopKpisV230 = async function() {
  try {
    const resp = await fetch("/api/dashboard/kpi-summary?t=" + Date.now());

    if (!resp.ok) {
      throw new Error("HTTP " + resp.status + " while loading KPI summary.");
    }

    const payload = await resp.json();
    window.renderTopKpisV230(payload);
  } catch (err) {
    console.error("Failed to load V230 KPI summary:", err);
  }
};

window.renderWellInsightV230 = function(payload) {
  const visual = document.getElementById("visualPanel");

  if (!visual) {
    alert("visualPanel not found.");
    return;
  }

  if (!payload.found) {
    visual.innerHTML = `
      <div class="well-insight-v230">
        <h3>${payload.well || "Well"}</h3>
        <p style="color:#fca5a5">${payload.message || "Well not found."}</p>
      </div>
    `;
    return;
  }

  const cards = payload.cards || [];
  const activity = payload.activity || {};

  visual.innerHTML = `
    <div class="well-insight-v230">
      <div class="well-insight-header-v230">
        <div>
          <div class="well-insight-title-v230">${payload.well}</div>
          <div class="well-insight-subtitle-v230">
            Active producer: ${activity.active_producer === true ? "Yes" : activity.active_producer === false ? "No" : "N/A"}
            ${activity.exclude_from_hm ? " | Excluded from HM" : ""}
          </div>
        </div>
        <button class="well-insight-btn-v230" onclick="askQuick('Show water profiles simulated vs observed for ${payload.well}')">
          Show water profile
        </button>
      </div>

      <div class="well-insight-kpi-grid-v230">
        ${cards.map(card => {
          const color = window.v230ClassColor(card.class);
          return `
            <div class="well-insight-kpi-v230">
              <div class="well-insight-kpi-label-v230">${card.label}</div>
              <div class="well-insight-kpi-score-v230" style="color:${color}">${window.v230Fmt(card.score)}</div>
              <div class="well-insight-kpi-class-v230">${card.class || "Not Evaluated"}</div>
              <div class="well-insight-kpi-status-v230">${card.status || ""}</div>
            </div>
          `;
        }).join("")}
      </div>

      <div class="well-insight-section-title-v230">Criticalities</div>
      <ul class="well-insight-list-v230">
        ${(payload.criticalities || []).map(x => `<li>${x}</li>`).join("")}
      </ul>

      <div class="well-insight-section-title-v230">Recommended Action</div>
      <p class="well-insight-text-v230">${payload.recommended_action || "Review profile, property map and connectivity context."}</p>

      ${payload.interpretation ? `
        <div class="well-insight-section-title-v230">Interpretation</div>
        <p class="well-insight-text-v230">${payload.interpretation}</p>
      ` : ""}

      <div class="well-insight-section-title-v230">Quick Actions</div>
      <div class="quick-actions">
        <button onclick="askQuick('Show water profiles simulated vs observed for ${payload.well}')">Water Profile</button>
        <button onclick="askQuick('Show pressure map')">Pressure Map</button>
        <button onclick="askQuick('Show transmissibility map')">TRAN_H Map</button>
        <button onclick="askQuick('Where should I increase transmissibility for ${payload.well}')">TRAN Corridor</button>
        <button onclick="askQuick('Why is water not matching for ${payload.well}')">Explain Water</button>
      </div>
    </div>
  `;
};

window.selectWell = async function(well) {
  const answer = document.getElementById("chatAnswer");
  const visual = document.getElementById("visualPanel");

  if (answer) {
    answer.innerHTML = `<p>Selected well <b>${well}</b>. Loading diagnostic insight...</p>`;
  }

  if (visual) {
    visual.innerHTML = `<p style="color:#94a3b8">Loading well insight for ${well}...</p>`;
  }

  try {
    const resp = await fetch("/api/dashboard/well-insight?well=" + encodeURIComponent(well) + "&t=" + Date.now());

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error("HTTP " + resp.status + ": " + txt);
    }

    const payload = await resp.json();

    if (answer) {
      answer.innerHTML = `<p>Well <b>${well}</b> selected. The right panel shows the HM KPIs, criticalities and recommended action.</p>`;
    }

    window.renderWellInsightV230(payload);

  } catch (err) {
    console.error("Failed to load well insight:", err);

    if (visual) {
      visual.innerHTML = `
        <div style="color:#fca5a5;padding:12px;border:1px solid rgba(239,68,68,.35);border-radius:12px">
          Failed to load well insight for ${well}: ${err}
        </div>
      `;
    }
  }
};

setTimeout(() => {
  window.loadTopKpisV230();
  window.hideOldInactiveAndCorridorCardsV230();
}, 600);

setTimeout(() => {
  window.hideOldInactiveAndCorridorCardsV230();
}, 1800);





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
