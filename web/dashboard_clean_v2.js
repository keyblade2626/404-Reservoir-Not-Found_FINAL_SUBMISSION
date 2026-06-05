(function(){
  function norm(t){
    return String(t || "").replace(/\s+/g," ").trim().toLowerCase();
  }

  function clsFrom(score, klass){
    if (score === null || score === undefined || score === "" || !isFinite(Number(score))) return "na";
    const v = Number(score);
    if (v >= 80) return "good";
    if (v >= 60) return "fair";
    return "poor";
  }

  function fmt(score){
    if (score === null || score === undefined || score === "" || !isFinite(Number(score))) return "N/A";
    return Number(score).toFixed(1);
  }

  function allBlocks(){
    return Array.from(document.querySelectorAll("section, article, div"));
  }

  function findBlockByText(text){
    const target = norm(text);
    const candidates = allBlocks().filter(el => {
      const t = norm(el.innerText);
      return t.startsWith(target) || t.includes(target);
    });

    if (!candidates.length) return null;

    candidates.sort((a,b) => {
      const da = a.innerText.length;
      const db = b.innerText.length;
      return da - db;
    });

    return candidates[0];
  }

  function findButtonByText(text){
    const target = norm(text);
    return Array.from(document.querySelectorAll("button")).find(btn => norm(btn.innerText) === target);
  }

  function getMain(){
    return document.querySelector("main") || document.body;
  }

  function ensureRoot(){
    let root = document.getElementById("cleanDashRoot");
    if (root) return root;

    root = document.createElement("div");
    root.id = "cleanDashRoot";
    root.innerHTML = `
      <div id="cleanTopHeader">
        <div id="cleanTitleBlock">
          <h1>404 Reservoir Not Found</h1>
          <p>Reservoir HM Copilot</p>
        </div>
        <div id="cleanHeaderActions"></div>
      </div>

      <div id="cleanKpiRow"></div>

      <div id="cleanMainGrid">
        <section class="clean-card" id="cleanMapCard">
          <div class="clean-card-header">
            <div>
              <div class="clean-card-title">Spatial History Match Map</div>
              <div class="clean-card-sub">Main view for HM quality. Filters and map are now in one single place.</div>
            </div>
            <div class="clean-chip">Main focus area</div>
          </div>
          <div class="clean-card-body" id="cleanMapBody">
            <div id="cleanMapControls"></div>
            <div id="cleanMapMount"></div>
          </div>
        </section>

        <section class="clean-card" id="cleanInsightCard">
          <div class="clean-card-header">
            <div>
              <div class="clean-card-title">Well Insight</div>
              <div class="clean-card-sub">Selected well KPIs, criticalities and suggested actions</div>
            </div>
          </div>
          <div class="clean-card-body" id="cleanInsightBody">
            <div class="clean-empty">Click a well on the map to inspect the detail.</div>
          </div>
        </section>
      </div>

      <div id="cleanBottomGrid">
        <section class="clean-card" id="cleanAskCard">
          <div class="clean-card-header">
            <div>
              <div class="clean-card-title">Ask Reservoir AI</div>
              <div class="clean-card-sub">Use quick actions or ask a specific technical question</div>
            </div>
          </div>
          <div class="clean-card-body" id="cleanAskMount">
            <div class="clean-empty">Chat panel will appear here.</div>
          </div>
        </section>

        <section class="clean-card" id="cleanVisualCard">
          <div class="clean-card-header">
            <div>
              <div class="clean-card-title">Visual / Evidence</div>
              <div class="clean-card-sub">Profiles, maps and evidence generated on demand</div>
            </div>
          </div>
          <div class="clean-card-body" id="cleanVisualMount">
            <div class="clean-empty">Visual evidence will appear here when requested.</div>
          </div>
        </section>
      </div>
    `;
    getMain().prepend(root);
    return root;
  }

  function hideIfFound(text){
    const block = findBlockByText(text);
    if (block) block.setAttribute("data-cleanup-hide","true");
  }

  function moveButtons(){
    const actions = document.getElementById("cleanHeaderActions");
    if (!actions) return;

    ["Run Diagnostics","Refresh Dashboard"].forEach(label => {
      const btn = findButtonByText(label);
      if (btn && !actions.contains(btn)){
        actions.appendChild(btn);
      }
    });
  }

  function renderTopKpis(cards){
    const row = document.getElementById("cleanKpiRow");
    if (!row) return;

    row.innerHTML = (cards || []).map(card => {
      const cls = clsFrom(card.score, card.class);
      return `
        <div class="clean-kpi">
          <div class="clean-kpi-label">${card.label || ""}</div>
          <div class="clean-kpi-value ${cls}">${fmt(card.score)}</div>
          <div class="clean-kpi-class">${card.class || "N/A"}</div>
          <div class="clean-kpi-sub">${card.subtext || ""}</div>
        </div>
      `;
    }).join("");
  }

  async function loadKpis(){
    try{
      const r = await fetch("/api/dashboard/kpi-summary?t=" + Date.now());
      const data = await r.json();
      renderTopKpis(data.cards || []);
    }catch(err){
      console.error("KPI load failed:", err);
    }
  }

  function moveMainMap(){
    const mapSlot = document.getElementById("cleanMapMount");
    const ctlSlot = document.getElementById("cleanMapControls");
    if (!mapSlot || !ctlSlot) return;

    const spatial = findBlockByText("Spatial History Match Map");
    if (spatial && !mapSlot.contains(spatial)){
      mapSlot.appendChild(spatial);
    }

    const reservoirMap = findBlockByText("Reservoir Map");
    if (reservoirMap){
      const controls = Array.from(reservoirMap.querySelectorAll("input, select, label"));
      if (controls.length){
        const wrap = document.createElement("div");
        controls.forEach(el => wrap.appendChild(el));
        ctlSlot.appendChild(wrap);
      }

      const selects = reservoirMap.querySelectorAll("select");
      selects.forEach(sel => ctlSlot.appendChild(sel));

      const inputs = reservoirMap.querySelectorAll("input");
      inputs.forEach(inp => ctlSlot.appendChild(inp.closest("label") || inp));

      reservoirMap.setAttribute("data-cleanup-hide","true");
    }

    if (!ctlSlot.children.length){
      const fallback = document.createElement("div");
      fallback.className = "clean-empty";
      fallback.textContent = "Map controls not found. The main map is still available below.";
      ctlSlot.appendChild(fallback);
    }
  }

  function moveWellInsight(){
    const insightBody = document.getElementById("cleanInsightBody");
    if (!insightBody) return;

    const insight = findBlockByText("Well Insight");
    if (insight && !insightBody.contains(insight)){
      insightBody.innerHTML = "";
      insightBody.appendChild(insight);
    }
  }

  function moveBottomPanels(){
    const askMount = document.getElementById("cleanAskMount");
    const visualMount = document.getElementById("cleanVisualMount");

    const ask = findBlockByText("Ask Reservoir AI");
    if (ask && askMount && !askMount.contains(ask)){
      askMount.innerHTML = "";
      askMount.appendChild(ask);
    }

    const visual = findBlockByText("Visual / Evidence");
    if (visual && visualMount && !visualMount.contains(visual)){
      visualMount.innerHTML = "";
      visualMount.appendChild(visual);
    }
  }

  function hideOldJunk(){
    hideIfFound("Assistant Workspace");
    hideIfFound("Selected Well / Area");
    hideIfFound("Reservoir Map");

    // prova a nascondere i vecchi KPI box doppi
    const labels = ["overall hm","oil hm","water hm","gas hm","bhp hm"];
    allBlocks().forEach(el => {
      const txt = norm(el.innerText);
      if (!txt) return;

      const isKpiLike = labels.some(x => txt.startsWith(x)) && (txt.includes("good") || txt.includes("fair") || txt.includes("poor"));
      if (isKpiLike){
        const parentText = norm((el.parentElement && el.parentElement.innerText) || "");
        if (parentText.includes("evaluated wells") || parentText.includes("overall hm")){
          el.setAttribute("data-cleanup-hide","true");
        }
      }
    });
  }

  function resizePlots(){
    if (!window.Plotly) return;
    document.querySelectorAll(".js-plotly-plot").forEach(p => {
      try{ window.Plotly.Plots.resize(p); } catch(e){}
    });
  }

  async function loadWellInsight(well){
    try{
      const r = await fetch("/api/dashboard/well-insight?well=" + encodeURIComponent(well) + "&t=" + Date.now());
      const data = await r.json();

      const body = document.getElementById("cleanInsightBody");
      if (!body) return;

      if (!data || !data.found){
        body.innerHTML = `<div class="clean-empty">No well detail available for ${well}.</div>`;
        return;
      }

      const cards = data.cards || [];
      const crit = data.criticalities || [];

      body.innerHTML = `
        <div class="clean-note-title">${data.well}</div>

        <div class="clean-mini-grid">
          ${cards.map(card => {
            const cls = clsFrom(card.score, card.class);
            return `
              <div class="clean-mini">
                <div class="clean-mini-label">${card.label}</div>
                <div class="clean-mini-value ${cls}">${fmt(card.score)}</div>
                <div class="clean-kpi-sub">${card.class || "N/A"}</div>
              </div>
            `;
          }).join("")}
        </div>

        <div class="clean-section">
          <h4>Criticalities</h4>
          <ul>
            ${crit.length ? crit.map(x => `<li>${x}</li>`).join("") : "<li>No major criticality detected.</li>"}
          </ul>
        </div>

        <div class="clean-section">
          <h4>Recommended Action</h4>
          <p>${data.recommended_action || "Review profiles, local transmissibility, pressure support and connected flow behaviour."}</p>
        </div>

        ${data.interpretation ? `
        <div class="clean-section">
          <h4>Interpretation</h4>
          <p>${data.interpretation}</p>
        </div>` : ""}
      `;
    }catch(err){
      console.error("Well insight load failed:", err);
    }
  }

  window.selectWell = async function(well){
    await loadWellInsight(well);
  };

  function init(){
    ensureRoot();
    moveButtons();
    loadKpis();
    moveMainMap();
    moveWellInsight();
    moveBottomPanels();
    hideOldJunk();
    resizePlots();
    setTimeout(resizePlots, 500);
    setTimeout(resizePlots, 1200);
    window.addEventListener("resize", resizePlots);
  }

  document.addEventListener("DOMContentLoaded", function(){
    setTimeout(init, 120);
  });
})();
