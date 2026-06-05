(function(){
  const qs = (s, root=document) => root.querySelector(s);
  const qsa = (s, root=document) => Array.from(root.querySelectorAll(s));

  function classOf(score, label){
    if (score === null || score === undefined || score === "" || String(label || "").toLowerCase().includes("not evaluated")) return "na";
    const n = Number(score);
    if (!Number.isFinite(n)) return "na";
    if (n >= 80) return "good";
    if (n >= 60) return "fair";
    return "poor";
  }

  function fmt(score){
    if (score === null || score === undefined || score === "") return "N/A";
    const n = Number(score);
    if (!Number.isFinite(n)) return "N/A";
    return n.toFixed(1);
  }

  function byIds(ids){
    for (const id of ids){
      const el = document.getElementById(id);
      if (el) return el;
    }
    return null;
  }

  function closestCard(el){
    if (!el) return null;
    return el.closest(".card, .panel, .metric-card, .summary-card, section, article, div") || el;
  }

  function findMainContainer(){
    return qs("main") || document.body;
  }

  function findMapHost(){
    const ids = ["hmMap","mainMap","mapPlot","mapPanel","wellMap","spatialMap","map"];
    for (const id of ids){
      const el = document.getElementById(id);
      if (el) return closestCard(el);
    }

    const plots = qsa(".js-plotly-plot").map(el => {
      const r = el.getBoundingClientRect();
      return { el, area: Math.max(0, r.width * r.height) };
    }).sort((a,b) => b.area - a.area);

    if (plots.length){
      return closestCard(plots[0].el);
    }

    return null;
  }

  function findChatHost(){
    const ids = ["chatPanel","chatCard","assistantPanel","analysisPanel","chatAnswer"];
    for (const id of ids){
      const el = document.getElementById(id);
      if (el) return closestCard(el);
    }

    const textArea = qs("textarea");
    if (textArea) return closestCard(textArea);

    return null;
  }

  function findDetailHost(){
    const ids = ["visualPanel","wellInsightPanel","wellDetailPanel"];
    for (const id of ids){
      const el = document.getElementById(id);
      if (el) return el;
    }
    return null;
  }

  function markOldNoise(){
    const badLabels = [
      "inactive wells",
      "candidate corridors"
    ];

    qsa("section, article, div").forEach(node => {
      const txt = String(node.innerText || "").trim().toLowerCase();
      if (!txt) return;

      if (badLabels.some(x => txt === x || txt.startsWith(x + "\n"))){
        node.setAttribute("data-nv-hide","true");
      }

      if (txt.includes("success running") || txt.includes("agent running") || txt.includes("agent status")){
        if (txt.length < 400){
          node.setAttribute("data-nv-hide","true");
        }
      }
    });

    const old = document.getElementById("topKpiCardsV230");
    if (old) old.setAttribute("data-nv-hide","true");
  }

  function ensureShell(){
    if (document.getElementById("nvDashboardShell")){
      return {
        shell: document.getElementById("nvDashboardShell"),
        topBar: document.getElementById("nvTopBar"),
        mapMount: document.getElementById("nvMapMount"),
        rightBody: document.getElementById("nvRightBody"),
        chatMount: document.getElementById("nvChatMount")
      };
    }

    const host = findMainContainer();

    const shell = document.createElement("div");
    shell.id = "nvDashboardShell";
    shell.innerHTML = `
      <div id="nvTopBar"></div>

      <div id="nvMainGrid">
        <section id="nvMapCard" class="nv-card">
          <div class="nv-card-header">
            <div>
              <div class="nv-card-title">Spatial History Match Map</div>
              <div class="nv-card-subtitle">Main interactive map with active wells and HM color coding</div>
            </div>
            <div class="nv-pill">Click a well to inspect details</div>
          </div>
          <div class="nv-card-body">
            <div id="nvMapMount"></div>
          </div>
        </section>

        <aside id="nvRightPanel" class="nv-card">
          <div class="nv-card-header">
            <div>
              <div class="nv-card-title">Well Insight</div>
              <div class="nv-card-subtitle">Selected well diagnostics and notes</div>
            </div>
          </div>
          <div class="nv-card-body" id="nvRightBody">
            <div class="nv-empty">Click a well on the map to view its KPIs, criticalities and suggested actions.</div>
          </div>
        </aside>
      </div>

      <div id="nvBottomRow">
        <section class="nv-card">
          <div class="nv-card-header">
            <div>
              <div class="nv-card-title">Assistant Workspace</div>
              <div class="nv-card-subtitle">Use the chat and quick actions to explore the model</div>
            </div>
          </div>
          <div class="nv-card-body">
            <div id="nvChatMount"></div>
          </div>
        </section>
      </div>
    `;

    host.prepend(shell);

    return {
      shell,
      topBar: document.getElementById("nvTopBar"),
      mapMount: document.getElementById("nvMapMount"),
      rightBody: document.getElementById("nvRightBody"),
      chatMount: document.getElementById("nvChatMount")
    };
  }

  function moveExistingPanels(){
    const ui = ensureShell();

    const mapHost = findMapHost();
    if (mapHost && !ui.mapMount.contains(mapHost)){
      ui.mapMount.innerHTML = "";
      ui.mapMount.appendChild(mapHost);
    }

    const detail = findDetailHost();
    if (detail && !ui.rightBody.contains(detail)){
      ui.rightBody.innerHTML = "";
      ui.rightBody.appendChild(detail);
    }

    const chat = findChatHost();
    if (chat && !ui.chatMount.contains(chat)){
      ui.chatMount.innerHTML = "";
      ui.chatMount.appendChild(chat);
    }

    markOldNoise();
  }

  async function loadTopKpis(){
    const ui = ensureShell();

    try{
      const res = await fetch("/api/dashboard/kpi-summary?t=" + Date.now());
      const data = await res.json();

      const cards = data.cards || [];

      ui.topBar.innerHTML = cards.map(card => {
        const cls = classOf(card.score, card.class);
        return `
          <div class="nv-kpi-card">
            <div class="nv-kpi-label">${card.label || ""}</div>
            <div class="nv-kpi-value ${cls}">${fmt(card.score)}</div>
            <div class="nv-kpi-class">${card.class || "Not Evaluated"}</div>
            <div class="nv-kpi-sub">${card.subtext || ""}</div>
          </div>
        `;
      }).join("");
    }catch(err){
      console.error("Failed to load top KPIs:", err);
      ui.topBar.innerHTML = `<div class="nv-kpi-card"><div class="nv-kpi-label">Dashboard</div><div class="nv-kpi-class">Failed to load KPI summary</div></div>`;
    }
  }

  function renderInsight(data){
    const ui = ensureShell();

    if (!data || !data.found){
      ui.rightBody.innerHTML = `<div class="nv-empty">${(data && data.message) ? data.message : "No well insight available."}</div>`;
      return;
    }

    const cards = data.cards || [];
    const crit = data.criticalities || [];
    const activity = data.activity || {};

    ui.rightBody.innerHTML = `
      <div class="nv-insight">
        <div class="nv-insight-title">${data.well}</div>
        <div class="nv-insight-sub">
          Active producer: ${activity.active_producer === true ? "Yes" : activity.active_producer === false ? "No" : "N/A"}
          ${activity.exclude_from_hm ? " | Excluded from HM" : ""}
        </div>

        <div class="nv-insight-grid">
          ${cards.map(card => {
            const cls = classOf(card.score, card.class);
            return `
              <div class="nv-mini-kpi">
                <div class="nv-mini-kpi-label">${card.label}</div>
                <div class="nv-mini-kpi-value ${cls}">${fmt(card.score)}</div>
                <div class="nv-kpi-sub">${card.class || "Not Evaluated"}</div>
              </div>
            `;
          }).join("")}
        </div>

        <div class="nv-section-title">Criticalities</div>
        <ul class="nv-bullets">
          ${crit.length ? crit.map(x => `<li>${x}</li>`).join("") : "<li>No major criticality detected.</li>"}
        </ul>

        <div class="nv-section-title">Recommended Action</div>
        <p class="nv-text">${data.recommended_action || "Review variable profiles, property maps and local connectivity before applying model changes."}</p>

        ${data.interpretation ? `
          <div class="nv-section-title">Interpretation</div>
          <p class="nv-text">${data.interpretation}</p>
        ` : ""}

        <div class="nv-section-title">Quick Actions</div>
        <div class="nv-quick">
          <button onclick="askQuick('Show water profiles simulated vs observed for ${data.well}')">Water profile</button>
          <button onclick="askQuick('Show oil profiles simulated vs observed for ${data.well}')">Oil profile</button>
          <button onclick="askQuick('Show gas profiles simulated vs observed for ${data.well}')">Gas profile</button>
          <button onclick="askQuick('Show transmissibility map around ${data.well}')">Transmissibility</button>
          <button onclick="askQuick('Why is water not matching for ${data.well}?')">Explain water</button>
        </div>
      </div>
    `;
  }

  async function loadWellInsight(well){
    try{
      const res = await fetch("/api/dashboard/well-insight?well=" + encodeURIComponent(well) + "&t=" + Date.now());
      const data = await res.json();
      renderInsight(data);
    }catch(err){
      console.error("Failed to load well insight:", err);
      renderInsight({ found:false, message:"Failed to load well insight." });
    }
  }

  function resizePlotly(){
    if (!window.Plotly) return;
    qsa(".js-plotly-plot").forEach(plot => {
      try{ window.Plotly.Plots.resize(plot); } catch(e){}
    });
  }

  window.selectWell = async function(well){
    await loadWellInsight(well);
  };

  function init(){
    moveExistingPanels();
    loadTopKpis();
    resizePlotly();
    setTimeout(resizePlotly, 500);
    setTimeout(resizePlotly, 1200);
    window.addEventListener("resize", resizePlotly);
  }

  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(init, 120);
  });
})();
