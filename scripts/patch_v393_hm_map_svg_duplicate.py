from pathlib import Path

ROOT = Path(".").resolve()
WEB = ROOT / "web"

MARKER_START = "/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_START */"
MARKER_END = "/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_END */"

patch_js = r'''
/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_START */
(function () {
  "use strict";

  function toArray(x) {
    return Array.prototype.slice.call(x || []);
  }

  function visible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    return r.width > 30 && r.height > 30;
  }

  function getHmVariable() {
    var sel = document.getElementById("hmVariable");
    return sel ? String(sel.value || "overall").toLowerCase() : "overall";
  }

  function mapVariableFromSvg(svg) {
    if (!svg) return "";
    var txt = (svg.textContent || "").toLowerCase();

    if (txt.indexOf("color by oil") >= 0) return "oil";
    if (txt.indexOf("color by water") >= 0) return "water";
    if (txt.indexOf("color by gas") >= 0) return "gas";
    if (txt.indexOf("color by bhp") >= 0) return "bhp";
    if (txt.indexOf("color by overall") >= 0) return "overall";

    return "";
  }

  function findLikelyHmMapRoots() {
    var roots = [];

    [
      "#hmMap",
      "#hm-map",
      "#hmMapContainer",
      "#hmKpiMap",
      "#hmKpiMapContainer",
      "#wellMap",
      "#wellMapContainer",
      "#patternAwareFixedSlot",
      "#fixedSlot",
      "#fixed-slot",
      ".hm-map",
      ".hm-map-container",
      ".hm-kpi-map",
      ".hm-kpi-map-container",
      ".pattern-aware-fixed-slot",
      ".fixed-slot",
      ".map-panel"
    ].forEach(function (sel) {
      toArray(document.querySelectorAll(sel)).forEach(function (el) {
        if (roots.indexOf(el) < 0) roots.push(el);
      });
    });

    toArray(document.querySelectorAll(".hm-map-svg")).forEach(function (svg) {
      var p = svg.parentElement;
      var safety = 0;

      while (p && p !== document.body && safety < 8) {
        var idClass = ((p.id || "") + " " + (p.className || "")).toLowerCase();
        var svgCount = p.querySelectorAll ? p.querySelectorAll(".hm-map-svg").length : 0;

        if (
          svgCount > 0 &&
          (
            idClass.indexOf("map") >= 0 ||
            idClass.indexOf("hm") >= 0 ||
            idClass.indexOf("fixed") >= 0 ||
            idClass.indexOf("pattern") >= 0 ||
            p.querySelectorAll(".hm-map-svg").length > 1
          )
        ) {
          if (roots.indexOf(p) < 0) roots.push(p);
          break;
        }

        p = p.parentElement;
        safety += 1;
      }

      if (svg.parentElement && roots.indexOf(svg.parentElement) < 0) {
        roots.push(svg.parentElement);
      }
    });

    return roots;
  }

  function removeOrphanMapRects(root) {
    if (!root || !root.children) return;

    toArray(root.children).forEach(function (child) {
      var tag = (child.tagName || "").toLowerCase();

      // The user saw a rect outside the SVG. That is invalid/duplicated map residue.
      if (tag === "rect") {
        child.remove();
      }
    });
  }

  function keepOnlyLatestMapSvg(root) {
    if (!root || !root.querySelectorAll) return;

    var svgs = toArray(root.querySelectorAll("svg.hm-map-svg")).filter(visible);

    if (svgs.length <= 1) {
      removeOrphanMapRects(root);
      return;
    }

    var currentVar = getHmVariable();

    // Prefer SVG matching selected variable. If multiple match, keep the last one.
    var matching = svgs.filter(function (svg) {
      var v = mapVariableFromSvg(svg);
      return v && v === currentVar;
    });

    var keep = null;

    if (matching.length > 0) {
      keep = matching[matching.length - 1];
    } else {
      keep = svgs[svgs.length - 1];
    }

    svgs.forEach(function (svg) {
      if (svg !== keep) {
        var parent = svg.parentElement;

        // If SVG is the only meaningful child inside a wrapper, remove wrapper;
        // otherwise remove only SVG.
        if (parent && parent !== root) {
          var wrapperText = (parent.textContent || "").trim();
          var wrapperSvgs = parent.querySelectorAll ? parent.querySelectorAll("svg.hm-map-svg").length : 0;
          var wrapperGraphics = parent.querySelectorAll ? parent.querySelectorAll("svg, canvas, img").length : 0;
          var idClass = ((parent.id || "") + " " + (parent.className || "")).toLowerCase();

          if (
            wrapperSvgs === 1 &&
            wrapperGraphics === 1 &&
            (
              idClass.indexOf("map") >= 0 ||
              idClass.indexOf("hm") >= 0 ||
              idClass.indexOf("fixed") >= 0 ||
              wrapperText.length < 2500
            )
          ) {
            parent.remove();
          } else {
            svg.remove();
          }
        } else {
          svg.remove();
        }
      }
    });

    removeOrphanMapRects(root);
  }

  function cleanupAllHmMaps() {
    var roots = findLikelyHmMapRoots();

    roots.forEach(function (root) {
      try {
        root.style.position = root.style.position || "relative";
        root.style.overflow = "hidden";
        root.style.isolation = "isolate";

        keepOnlyLatestMapSvg(root);
      } catch (e) {
        console.warn("[404_RNF] V393 map cleanup skipped", e);
      }
    });

    // Final global cleanup: if multiple visible hm-map-svg still exist in the whole document,
    // keep the one matching the selected variable or the last rendered one.
    var all = toArray(document.querySelectorAll("svg.hm-map-svg")).filter(visible);

    if (all.length > 1) {
      var currentVar = getHmVariable();
      var matching = all.filter(function (svg) {
        return mapVariableFromSvg(svg) === currentVar;
      });

      var keep = matching.length ? matching[matching.length - 1] : all[all.length - 1];

      all.forEach(function (svg) {
        if (svg !== keep) {
          svg.remove();
        }
      });
    }
  }

  function scheduleCleanup() {
    window.clearTimeout(window.__404RnfV393CleanupT1);
    window.clearTimeout(window.__404RnfV393CleanupT2);
    window.clearTimeout(window.__404RnfV393CleanupT3);

    window.__404RnfV393CleanupT1 = window.setTimeout(cleanupAllHmMaps, 0);
    window.__404RnfV393CleanupT2 = window.setTimeout(cleanupAllHmMaps, 80);
    window.__404RnfV393CleanupT3 = window.setTimeout(cleanupAllHmMaps, 300);
  }

  function install() {
    if (window.__404RnfV393HmMapFixInstalled) return;
    window.__404RnfV393HmMapFixInstalled = true;

    var sel = document.getElementById("hmVariable");

    if (sel) {
      sel.addEventListener("change", function () {
        scheduleCleanup();
      }, true);
    }

    // Also listen to clicks on KPI filter cards because you said injectors/inactive producers
    // forces the correct overlay behaviour.
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t) return;

      var text = "";
      try {
        text = String((t.innerText || t.textContent || "")).toLowerCase();
      } catch (e) {}

      var cls = String((t.className || "")).toLowerCase();

      if (
        cls.indexOf("kpi") >= 0 ||
        cls.indexOf("filter") >= 0 ||
        text.indexOf("injector") >= 0 ||
        text.indexOf("inactive") >= 0 ||
        text.indexOf("producer") >= 0
      ) {
        scheduleCleanup();
      }
    }, true);

    var observer = new MutationObserver(function (mutations) {
      var should = false;

      mutations.forEach(function (m) {
        toArray(m.addedNodes).forEach(function (n) {
          if (!n || !n.querySelectorAll) return;

          if (
            (n.matches && n.matches("svg.hm-map-svg")) ||
            n.querySelector("svg.hm-map-svg") ||
            n.querySelector(".hm-well-point-v393")
          ) {
            should = true;
          }
        });
      });

      if (should) scheduleCleanup();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    scheduleCleanup();
    console.log("[404_RNF] V393 hm-map-svg duplicate fix installed");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }

  window.__404_RNF_cleanupV393HmMaps = cleanupAllHmMaps;
})();
/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_END */
'''

def strip_existing(text: str) -> str:
    if MARKER_START not in text:
        return text

    before = text.split(MARKER_START)[0]
    rest = text.split(MARKER_END, 1)
    if len(rest) == 2:
        return before.rstrip() + "\n" + rest[1].lstrip()
    return before.rstrip() + "\n"

files = list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html"))

targets = []
for p in files:
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    if (
        "hmVariable" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt or
        "HM KPI well map fallback rendered" in txt or
        "Pattern-aware card moved to fixed slot" in txt
    ):
        targets.append(p)

if not targets:
    raise SystemExit("No frontend target file found for V393 HM map fix.")

patched = []

for p in targets:
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    txt = strip_existing(txt)

    if p.suffix.lower() == ".html" and "</body>" in txt.lower():
        lower = txt.lower()
        idx = lower.rfind("</body>")
        txt = txt[:idx] + "\n<script>\n" + patch_js + "\n</script>\n" + txt[idx:]
    else:
        txt = txt.rstrip() + "\n\n" + patch_js + "\n"

    p.write_text(txt, encoding="utf-8")
    patched.append(str(p))

print("[OK] Patched files:")
for p in patched:
    print(" -", p)
