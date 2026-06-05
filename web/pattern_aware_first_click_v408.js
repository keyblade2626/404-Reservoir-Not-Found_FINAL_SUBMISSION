(function installFirstHmClickPatternApplyV408() {
  if (window.__firstHmClickPatternApplyV408Installed) return;
  window.__firstHmClickPatternApplyV408Installed = true;

  let running = false;

  function hasPatternAwareContentV408() {
    const content = document.getElementById("patternAwareContentV311");
    if (!content) return false;

    const card = content.querySelector(".smart-well-recommendation-v41");
    const textLen = (content.innerText || "").trim().length;
    const htmlLen = (content.innerHTML || "").trim().length;

    return !!card && textLen > 80 && htmlLen > 300;
  }

  async function applyAndMovePatternAwareV408(reason) {
    if (running) return false;
    running = true;

    try {
      if (hasPatternAwareContentV408()) {
        return true;
      }

      const well = typeof findSelectedWellV41 === "function" ? findSelectedWellV41() : null;

      console.log("[V408] Attempt Pattern-Aware apply+move:", reason, { well });

      if (typeof applySmartWellRecommendationV42 === "function") {
        await applySmartWellRecommendationV42();
      } else if (typeof applySmartWellRecommendationV41 === "function") {
        applySmartWellRecommendationV41();
      }

      await new Promise(resolve => setTimeout(resolve, 250));

      if (typeof movePatternAwareCardToSlotV313 === "function") {
        movePatternAwareCardToSlotV313();
      }

      if (!hasPatternAwareContentV408() && typeof movePatternAwareCardToSlotV311 === "function") {
        movePatternAwareCardToSlotV311();
      }

      console.log("[V408] Pattern-Aware apply+move result:", {
        reason,
        well,
        attached: hasPatternAwareContentV408()
      });

      return hasPatternAwareContentV408();
    } catch (e) {
      console.warn("[V408] Pattern-Aware apply+move failed:", reason, e);
      return false;
    } finally {
      running = false;
    }
  }

  function scheduleApplyAndMoveV408(reason) {
    [350, 800, 1400, 2400, 3800, 5600].forEach(function(delay) {
      setTimeout(function() {
        if (!hasPatternAwareContentV408()) {
          applyAndMovePatternAwareV408(reason + "-" + delay);
        }
      }, delay);
    });
  }

  document.addEventListener("click", function(ev) {
    const target = ev.target;
    if (!target || !target.closest) return;

    if (!target.closest("#mapCanvas")) return;

    scheduleApplyAndMoveV408("hm-map-click");
  }, true);

  // Also run once shortly after load in case a default well is already selected.
  setTimeout(function() {
    if (!hasPatternAwareContentV408()) {
      applyAndMovePatternAwareV408("initial-load");
    }
  }, 1800);

  window.forcePatternAwareApplyMoveV408 = function() {
    return applyAndMovePatternAwareV408("manual-console");
  };

  console.log("[V408] First HM click Pattern-Aware apply+move active.");
})();
