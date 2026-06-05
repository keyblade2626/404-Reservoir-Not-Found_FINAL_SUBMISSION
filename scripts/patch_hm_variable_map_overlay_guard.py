from pathlib import Path

ROOT = Path(".").resolve()
WEB = ROOT / "web"

MARKER_START = "/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_START */"
MARKER_END = "/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_END */"

guard_js = r'''
/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_START */
(function () {
  "use strict";

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    return r.width > 40 && r.height > 40;
  }

  function looksLikeMapContainer(el) {
    if (!el || !el.querySelectorAll) return false;

    var idClass = ((el.id || "") + " " + (el.className || "")).toLowerCase();
    var hasMapName = idClass.indexOf("map") >= 0 || idClass.indexOf("well") >= 0 || idClass.indexOf("hm") >= 0;

    var graphics = qsa("img, canvas, svg", el).filter(isVisible);
    if (graphics.length === 0) return false;

    var r = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    if (!r || r.width < 120 || r.height < 120) return false;

    return hasMapName || graphics.length >= 2;
  }

  function findMapContainers() {
    var candidates = [];

    [
      "#hmMap",
      "#hm-map",
      "#hmMapContainer",
      "#mapContainer",
      "#map-container",
      "#wellMap",
      "#well-map",
      "#wellMapContainer",
      "#dashboardMap",
      "#fieldMap",
      ".hm-map",
      ".hm-map-container",
      ".map-container",
      ".well-map",
      ".well-map-container",
      ".map-panel",
      ".dashboard-map"
    ].forEach(function (sel) {
      qsa(sel).forEach(function (el) {
        if (candidates.indexOf(el) < 0) candidates.push(el);
      });
    });

    qsa("div, section, article").forEach(function (el) {
      if (looksLikeMapContainer(el) && candidates.indexOf(el) < 0) {
        candidates.push(el);
      }
    });

    return candidates;
  }

  function graphicSignature(el) {
    var tag = (el.tagName || "").toLowerCase();
    var src = el.getAttribute && (el.getAttribute("src") || "");
    var cls = el.className || "";
    var id = el.id || "";
    var style = el.getAttribute && (el.getAttribute("style") || "");
    return [tag, src, id, cls, style].join("|").slice(0, 500);
  }

  function cleanupDirectDuplicateGraphics(container) {
    if (!container || !container.children) return;

    var children = Array.prototype.slice.call(container.children);

    var graphics = children.filter(function (el) {
      var tag = (el.tagName || "").toLowerCase();
      if (["img", "canvas", "svg"].indexOf(tag) >= 0 && isVisible(el)) return true;

      var idClass = ((el.id || "") + " " + (el.className || "")).toLowerCase();
      if (idClass.indexOf("map") >= 0 && qsa("img, canvas, svg", el).length > 0 && isVisible(el)) return true;

      return false;
    });

    if (graphics.length <= 1) return;

    // Prefer the last rendered large map layer, because change handlers usually append the new layer.
    var largeGraphics = graphics.filter(function (el) {
      var r = el.getBoundingClientRect();
      return r.width > 160 && r.height > 120;
    });

    if (largeGraphics.length <= 1) return;

    var keep = largeGraphics[largeGraphics.length - 1];

    largeGraphics.forEach(function (el) {
      if (el !== keep) {
        el.setAttribute("data-404-rnf-removed-map-duplicate", "true");
        el.remove();
      }
    });
  }

  function cleanupNestedDuplicateImages(container) {
    if (!container) return;

    var imgs = qsa("img", container).filter(isVisible);
    if (imgs.length <= 1) return;

    var bySig = {};
    imgs.forEach(function (img) {
      var src = img.getAttribute("src") || "";
      if (!src) return;
      if (!bySig[src]) bySig[src] = [];
      bySig[src].push(img);
    });

    Object.keys(bySig).forEach(function (src) {
      var arr = bySig[src].filter(function (img) {
        var r = img.getBoundingClientRect();
        return r.width > 160 && r.height > 120;
      });

      if (arr.length <= 1) return;

      var keep = arr[arr.length - 1];
      arr.forEach(function (img) {
        if (img !== keep) {
          img.setAttribute("data-404-rnf-removed-duplicate-img", "true");
          img.remove();
        }
      });
    });
  }

  function normalizeMapContainers() {
    findMapContainers().forEach(function (container) {
      try {
        container.style.position = container.style.position || "relative";
        container.style.overflow = "hidden";
        container.style.isolation = "isolate";

        cleanupDirectDuplicateGraphics(container);
        cleanupNestedDuplicateImages(container);
      } catch (e) {
        console.warn("[404_RNF] map cleanup skipped:", e);
      }
    });
  }

  function installHmVariableGuard() {
    var select = document.getElementById("hmVariable");
    if (!select || select.__hmVariableOverlayGuardInstalled) return;

    select.__hmVariableOverlayGuardInstalled = true;

    // Run once at startup.
    window.setTimeout(normalizeMapContainers, 200);
    window.setTimeout(normalizeMapContainers, 800);

    select.addEventListener("change", function () {
      // Let the existing dashboard handler render first, then remove duplicated layers.
      window.setTimeout(normalizeMapContainers, 50);
      window.setTimeout(normalizeMapContainers, 250);
      window.setTimeout(normalizeMapContainers, 800);
    }, true);

    // MutationObserver catches async map/image insertions after selecting Oil/Water/Gas/BHP.
    var observer = new MutationObserver(function () {
      window.clearTimeout(window.__hmVariableMapCleanupTimer);
      window.__hmVariableMapCleanupTimer = window.setTimeout(normalizeMapContainers, 120);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    console.log("[404_RNF] hmVariable map overlay guard installed");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installHmVariableGuard);
  } else {
    installHmVariableGuard();
  }

  window.__404_RNF_normalizeHmMapLayers = normalizeMapContainers;
})();
/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_END */
'''

def strip_existing(text: str) -> str:
    if MARKER_START not in text:
        return text

    before = text.split(MARKER_START)[0]
    after = text.split(MARKER_END, 1)
    if len(after) == 2:
        return before.rstrip() + "\n" + after[1].lstrip()

    return before.rstrip() + "\n"

files = []
for pattern in ["*.html", "*.js"]:
    files.extend(WEB.glob(f"**/{pattern}"))

targets = []
for p in files:
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    if "hmVariable" in txt:
        targets.append(p)

if not targets:
    raise SystemExit("No web file containing hmVariable was found.")

patched = []

for p in targets:
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    txt = strip_existing(txt)

    if "</body>" in txt.lower():
        # Preserve actual casing by replacing with regex-like simple split.
        lower = txt.lower()
        idx = lower.rfind("</body>")
        txt = txt[:idx] + "\n<script>\n" + guard_js + "\n</script>\n" + txt[idx:]
    else:
        txt = txt.rstrip() + "\n\n" + guard_js + "\n"

    p.write_text(txt, encoding="utf-8")
    patched.append(str(p))

print("[OK] Patched files:")
for x in patched:
    print(" -", x)
