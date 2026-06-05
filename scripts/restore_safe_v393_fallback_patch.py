from pathlib import Path
import re

ROOT = Path(".").resolve()
WEB = ROOT / "web"

OLD_BLOCKS = [
    ("/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_START */", "/* 404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_END */"),
    ("/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_START */", "/* 404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_END */"),
    ("/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_START */", "/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_END */"),
    ("/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_START */", "/* 404_RNF_DISABLE_V393_FALLBACK_HM_MAP_END */"),
    ("/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_START */", "/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_END */"),
]

SAFE_START = "/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_START */"
SAFE_END = "/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_END */"

safe_patch = r'''
/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_START */
(function () {
  "use strict";

  if (window.__404RnfSafeHideV393FallbackOnlyInstalled) {
    return;
  }

  window.__404RnfSafeHideV393FallbackOnlyInstalled = true;

  function arr(x) {
    return Array.prototype.slice.call(x || []);
  }

  function removeOnlyFallbackSvg() {
    // Important:
    // Do NOT remove parent containers, cards, slots, panels or map roots.
    // renderMap() needs those containers to exist.
    arr(document.querySelectorAll("svg.hm-map-svg")).forEach(function (svg) {
      svg.remove();
    });

    arr(document.querySelectorAll(".hm-well-point-v393")).forEach(function (el) {
      var svg = el.closest ? el.closest("svg.hm-map-svg") : null;
      if (svg) {
        svg.remove();
      } else {
        el.remove();
      }
    });

    // Remove only orphan background rects that are outside SVG.
    // Never remove rects inside SVG charts/maps.
    arr(document.querySelectorAll("rect")).forEach(function (r) {
      var parent = r.parentElement;
      if (!parent) return;

      if (String(parent.tagName || "").toLowerCase() === "svg") {
        return;
      }

      var wRaw = r.getAttribute("width");
      var hRaw = r.getAttribute("height");
      var fill = String(r.getAttribute("fill") || "");
      var w = Number(wRaw);
      var h = Number(hRaw);

      if (
        (wRaw === "920" || wRaw === "100%" || w >= 300) &&
        (hRaw === "600" || hRaw === "100%" || h >= 200) &&
        fill.indexOf("rgba") >= 0
      ) {
        r.remove();
      }
    });

    return document.querySelectorAll("svg.hm-map-svg").length;
  }

  function scheduleCleanup() {
    window.clearTimeout(window.__404RnfSafeV393T1);
    window.clearTimeout(window.__404RnfSafeV393T2);
    window.clearTimeout(window.__404RnfSafeV393T3);

    window.__404RnfSafeV393T1 = window.setTimeout(removeOnlyFallbackSvg, 0);
    window.__404RnfSafeV393T2 = window.setTimeout(removeOnlyFallbackSvg, 120);
    window.__404RnfSafeV393T3 = window.setTimeout(removeOnlyFallbackSvg, 500);
  }

  function containsFallback(node) {
    if (!node || node.nodeType !== 1) return false;

    if (node.matches && node.matches("svg.hm-map-svg")) return true;
    if (node.querySelector && node.querySelector("svg.hm-map-svg")) return true;
    if (node.matches && node.matches(".hm-well-point-v393")) return true;
    if (node.querySelector && node.querySelector(".hm-well-point-v393")) return true;

    return false;
  }

  function install() {
    // Hide immediately via CSS as additional safety.
    var style = document.createElement("style");
    style.id = "404-rnf-safe-hide-v393-fallback-style";
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

    var sel = document.getElementById("hmVariable");

    if (sel && !sel.__404RnfSafeV393Bound) {
      sel.__404RnfSafeV393Bound = true;
      sel.addEventListener("change", function () {
        scheduleCleanup();
      }, true);
    }

    document.addEventListener("click", function () {
      scheduleCleanup();
    }, true);

    var observer = new MutationObserver(function (mutations) {
      var found = false;

      mutations.forEach(function (m) {
        arr(m.addedNodes).forEach(function (n) {
          if (containsFallback(n)) {
            found = true;
          }
        });
      });

      if (found) {
        scheduleCleanup();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    scheduleCleanup();

    console.log("[404_RNF] Safe V393 fallback hide installed. Containers are preserved.");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }

  window.__404_RNF_safeRemoveV393FallbackOnly = function () {
    var count = removeOnlyFallbackSvg();
    console.log("[404_RNF] remaining svg.hm-map-svg =", count);
    return count;
  };

})();
/* 404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_END */
'''

def remove_block(text: str, start: str, end: str) -> str:
    while start in text:
        before = text.split(start, 1)[0]
        rest = text.split(start, 1)[1]
        if end in rest:
            after = rest.split(end, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"
    return text

targets = []

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    original = txt

    for start, end in OLD_BLOCKS:
        txt = remove_block(txt, start, end)

    # Clean empty script tags left behind by removed injected code.
    txt = re.sub(r"<script>\s*</script>\s*", "", txt, flags=re.IGNORECASE)

    should_patch = (
        "hmVariable" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt or
        "HM KPI well map fallback rendered" in txt
    )

    if should_patch:
        if p.suffix.lower() == ".html" and "</body>" in txt.lower():
            lower = txt.lower()
            idx = lower.rfind("</body>")
            txt = txt[:idx] + "\n<script>\n" + safe_patch + "\n</script>\n" + txt[idx:]
        else:
            txt = txt.rstrip() + "\n\n" + safe_patch + "\n"

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        targets.append(str(p))

print("[OK] Cleaned old patches and installed safe patch in:")
for t in targets:
    print(" -", t)
