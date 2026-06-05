from pathlib import Path

ROOT = Path(".").resolve()
WEB = ROOT / "web"

START = "/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_START */"
END = "/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_END */"

patch = r'''
/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_START */
(function () {
  "use strict";

  if (window.__404RnfDisableV393FallbackHmMapInstalled) {
    return;
  }

  window.__404RnfDisableV393FallbackHmMapInstalled = true;

  var style = document.createElement("style");
  style.id = "disable-v393-hm-map-fallback-style";
  style.textContent = `
    svg.hm-map-svg,
    .hm-well-point-v393 {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
    }
  `;
  document.head.appendChild(style);

  function arr(x) {
    return Array.prototype.slice.call(x || []);
  }

  function removeOrphanMapRects() {
    arr(document.querySelectorAll("rect")).forEach(function (r) {
      var parent = r.parentElement;
      if (!parent) return;

      // Only remove orphan background rects outside SVG.
      if (String(parent.tagName || "").toLowerCase() === "svg") return;

      var w = Number(r.getAttribute("width"));
      var h = Number(r.getAttribute("height"));
      var fill = String(r.getAttribute("fill") || "");

      if (
        (w >= 300 || r.getAttribute("width") === "920" || r.getAttribute("width") === "100%") &&
        (h >= 200 || r.getAttribute("height") === "600" || r.getAttribute("height") === "100%") &&
        fill.indexOf("rgba") >= 0
      ) {
        r.remove();
      }
    });
  }

  function removeEmptyFallbackParents(svg) {
    if (!svg || !svg.parentElement) return;

    var p = svg.parentElement;

    // Remove SVG first.
    svg.remove();

    // If parent is just a fallback map wrapper, remove it too.
    var safety = 0;

    while (p && p !== document.body && safety < 4) {
      var next = p.parentElement;
      var idClass = String((p.id || "") + " " + (p.className || "")).toLowerCase();
      var text = String(p.textContent || "").trim();
      var graphics = p.querySelectorAll ? p.querySelectorAll("svg, canvas, img").length : 0;
      var hasUsefulControls = p.querySelectorAll ? p.querySelectorAll("button, select, input, textarea").length : 0;

      if (
        hasUsefulControls === 0 &&
        graphics === 0 &&
        (
          idClass.indexOf("map") >= 0 ||
          idClass.indexOf("hm") >= 0 ||
          idClass.indexOf("fixed") >= 0 ||
          idClass.indexOf("pattern") >= 0 ||
          text.length < 50
        )
      ) {
        p.remove();
        p = next;
        safety += 1;
      } else {
        break;
      }
    }
  }

  function removeV393FallbackMaps() {
    arr(document.querySelectorAll("svg.hm-map-svg")).forEach(function (svg) {
      removeEmptyFallbackParents(svg);
    });

    arr(document.querySelectorAll(".hm-well-point-v393")).forEach(function (el) {
      var svg = el.closest ? el.closest("svg.hm-map-svg") : null;
      if (svg) {
        removeEmptyFallbackParents(svg);
      } else {
        el.remove();
      }
    });

    removeOrphanMapRects();

    return document.querySelectorAll("svg.hm-map-svg").length;
  }

  function scheduleRemove() {
    window.clearTimeout(window.__404RnfDisableV393T1);
    window.clearTimeout(window.__404RnfDisableV393T2);
    window.clearTimeout(window.__404RnfDisableV393T3);
    window.clearTimeout(window.__404RnfDisableV393T4);

    window.__404RnfDisableV393T1 = window.setTimeout(removeV393FallbackMaps, 0);
    window.__404RnfDisableV393T2 = window.setTimeout(removeV393FallbackMaps, 80);
    window.__404RnfDisableV393T3 = window.setTimeout(removeV393FallbackMaps, 250);
    window.__404RnfDisableV393T4 = window.setTimeout(removeV393FallbackMaps, 800);
  }

  function containsFallbackMap(node) {
    if (!node || node.nodeType !== 1) return false;

    if (node.matches && node.matches("svg.hm-map-svg")) return true;
    if (node.querySelector && node.querySelector("svg.hm-map-svg")) return true;
    if (node.matches && node.matches(".hm-well-point-v393")) return true;
    if (node.querySelector && node.querySelector(".hm-well-point-v393")) return true;

    return false;
  }

  function install() {
    scheduleRemove();

    var sel = document.getElementById("hmVariable");

    if (sel && !sel.__404RnfDisableV393Bound) {
      sel.__404RnfDisableV393Bound = true;
      sel.addEventListener("change", function () {
        scheduleRemove();
      }, true);
    }

    document.addEventListener("click", function () {
      scheduleRemove();
    }, true);

    var observer = new MutationObserver(function (mutations) {
      var found = false;

      mutations.forEach(function (m) {
        arr(m.addedNodes).forEach(function (n) {
          if (containsFallbackMap(n)) found = true;
        });
      });

      if (found) {
        scheduleRemove();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    console.log("[404_RNF] V393 fallback HM map disabled completely");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }

  window.__404_RNF_removeV393FallbackHmMaps = function () {
    var count = removeV393FallbackMaps();
    console.log("[404_RNF] remaining svg.hm-map-svg =", count);
    return count;
  };

})();
/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_END */
'''

def strip_existing(text: str) -> str:
    if START not in text:
        return text

    before = text.split(START)[0]
    parts = text.split(END, 1)

    if len(parts) == 2:
        return before.rstrip() + "\n" + parts[1].lstrip()

    return before.rstrip() + "\n"

targets = []

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    if (
        "hmVariable" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt or
        "HM KPI well map fallback rendered" in txt
    ):
        targets.append(p)

if not targets:
    raise SystemExit("No frontend file found for V393 fallback map patch.")

patched = []

for p in targets:
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    txt = strip_existing(txt)

    if p.suffix.lower() == ".html" and "</body>" in txt.lower():
        lower = txt.lower()
        idx = lower.rfind("</body>")
        txt = txt[:idx] + "\n<script>\n" + patch + "\n</script>\n" + txt[idx:]
    else:
        txt = txt.rstrip() + "\n\n" + patch + "\n"

    p.write_text(txt, encoding="utf-8")
    patched.append(str(p))

print("[OK] Patched files:")
for x in patched:
    print(" -", x)
