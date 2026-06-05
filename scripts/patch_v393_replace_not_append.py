from pathlib import Path

ROOT = Path(".").resolve()
WEB = ROOT / "web"

START = "/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_START */"
END = "/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_END */"

patch = r'''
/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_START */
(function () {
  "use strict";

  if (window.__404RnfV393ReplaceNotAppendInstalled) {
    return;
  }
  window.__404RnfV393ReplaceNotAppendInstalled = true;

  function arr(x) {
    return Array.prototype.slice.call(x || []);
  }

  function isHmMapNode(node) {
    if (!node || node.nodeType !== 1) return false;

    if (node.matches && node.matches("svg.hm-map-svg")) return true;

    if (node.querySelector && node.querySelector("svg.hm-map-svg")) return true;

    if (node.classList && node.classList.contains("hm-well-point-v393")) return true;

    if (node.querySelector && node.querySelector(".hm-well-point-v393")) return true;

    return false;
  }

  function containsHmMapHtml(html) {
    html = String(html || "");
    return (
      html.indexOf("hm-map-svg") >= 0 ||
      html.indexOf("hm-well-point-v393") >= 0 ||
      html.indexOf("History Match KPI Well Map") >= 0
    );
  }

  function getVariable() {
    var sel = document.getElementById("hmVariable");
    return sel ? String(sel.value || "overall").toLowerCase() : "overall";
  }

  function svgVariable(svg) {
    var text = String((svg && svg.textContent) || "").toLowerCase();

    if (text.indexOf("color by oil") >= 0) return "oil";
    if (text.indexOf("color by water") >= 0) return "water";
    if (text.indexOf("color by gas") >= 0) return "gas";
    if (text.indexOf("color by bhp") >= 0) return "bhp";
    if (text.indexOf("color by overall") >= 0) return "overall";

    return "";
  }

  function visible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    return r.width > 20 && r.height > 20;
  }

  function findBestMapRoot(fromNode) {
    var node = fromNode && fromNode.nodeType === 1 ? fromNode : null;

    if (!node) return document.body;

    var current = node;
    var best = null;
    var safety = 0;

    while (current && current !== document.body && safety < 12) {
      var idClass = String((current.id || "") + " " + (current.className || "")).toLowerCase();
      var count = current.querySelectorAll ? current.querySelectorAll("svg.hm-map-svg").length : 0;

      if (
        idClass.indexOf("fixed") >= 0 ||
        idClass.indexOf("pattern") >= 0 ||
        idClass.indexOf("map") >= 0 ||
        idClass.indexOf("hm") >= 0 ||
        count > 0
      ) {
        best = current;
      }

      current = current.parentElement;
      safety += 1;
    }

    return best || node.parentElement || document.body;
  }

  function removeDirectOrphanRects(root) {
    if (!root || !root.children) return;

    arr(root.children).forEach(function (child) {
      var tag = String(child.tagName || "").toLowerCase();

      // You explicitly saw this:
      // <rect ...></rect> outside <svg class="hm-map-svg">
      // This is a stale/orphan map background layer.
      if (tag === "rect") {
        child.remove();
      }
    });
  }

  function removeOldMapSvgs(root, keep) {
    if (!root || !root.querySelectorAll) return;

    arr(root.querySelectorAll("svg.hm-map-svg")).forEach(function (svg) {
      if (keep && svg === keep) return;
      svg.remove();
    });

    removeDirectOrphanRects(root);
  }

  function cleanupAfterRender(root) {
    root = root || document.body;

    var all = arr(document.querySelectorAll("svg.hm-map-svg")).filter(visible);

    if (all.length <= 1) {
      removeDirectOrphanRects(root);
      return;
    }

    var currentVar = getVariable();

    var matching = all.filter(function (svg) {
      return svgVariable(svg) === currentVar;
    });

    var keep = matching.length ? matching[matching.length - 1] : all[all.length - 1];

    all.forEach(function (svg) {
      if (svg !== keep) {
        svg.remove();
      }
    });

    arr(document.querySelectorAll("rect")).forEach(function (r) {
      var parent = r.parentElement;
      if (!parent) return;

      // Remove only orphan SVG rects that are not inside an SVG.
      if (String(parent.tagName || "").toLowerCase() !== "svg") {
        var w = r.getAttribute("width");
        var h = r.getAttribute("height");
        var fill = String(r.getAttribute("fill") || "");

        if (
          (w === "920" || w === "100%" || Number(w) > 300) &&
          (h === "600" || h === "100%" || Number(h) > 200) &&
          fill.indexOf("rgba") >= 0
        ) {
          r.remove();
        }
      }
    });
  }

  function preCleanForMapInsertion(target) {
    var root = findBestMapRoot(target);
    removeOldMapSvgs(root, null);
    cleanupAfterRender(root);
  }

  function postCleanSoon(target) {
    window.clearTimeout(window.__404RnfV393PostClean1);
    window.clearTimeout(window.__404RnfV393PostClean2);
    window.clearTimeout(window.__404RnfV393PostClean3);

    window.__404RnfV393PostClean1 = window.setTimeout(function () {
      cleanupAfterRender(findBestMapRoot(target));
    }, 0);

    window.__404RnfV393PostClean2 = window.setTimeout(function () {
      cleanupAfterRender(findBestMapRoot(target));
    }, 80);

    window.__404RnfV393PostClean3 = window.setTimeout(function () {
      cleanupAfterRender(findBestMapRoot(target));
    }, 300);
  }

  // Patch appendChild
  var originalAppendChild = Node.prototype.appendChild;
  Node.prototype.appendChild = function (child) {
    if (isHmMapNode(child)) {
      preCleanForMapInsertion(this);
      var result = originalAppendChild.call(this, child);
      postCleanSoon(this);
      return result;
    }

    return originalAppendChild.call(this, child);
  };

  // Patch insertBefore
  var originalInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function (newNode, referenceNode) {
    if (isHmMapNode(newNode)) {
      preCleanForMapInsertion(this);
      var result = originalInsertBefore.call(this, newNode, referenceNode);
      postCleanSoon(this);
      return result;
    }

    return originalInsertBefore.call(this, newNode, referenceNode);
  };

  // Patch insertAdjacentHTML
  var originalInsertAdjacentHTML = Element.prototype.insertAdjacentHTML;
  Element.prototype.insertAdjacentHTML = function (position, html) {
    if (containsHmMapHtml(html)) {
      preCleanForMapInsertion(this);
      var result = originalInsertAdjacentHTML.call(this, position, html);
      postCleanSoon(this);
      return result;
    }

    return originalInsertAdjacentHTML.call(this, position, html);
  };

  // Patch innerHTML setter.
  // This catches code like:
  // container.innerHTML += mapHtml
  var innerDesc = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");

  if (innerDesc && innerDesc.set && innerDesc.get) {
    Object.defineProperty(Element.prototype, "innerHTML", {
      configurable: true,
      enumerable: innerDesc.enumerable,
      get: function () {
        return innerDesc.get.call(this);
      },
      set: function (value) {
        var hasMap = containsHmMapHtml(value);

        if (hasMap) {
          preCleanForMapInsertion(this);
        }

        innerDesc.set.call(this, value);

        if (hasMap) {
          postCleanSoon(this);
        }
      }
    });
  }

  function installDropdownCleanup() {
    var sel = document.getElementById("hmVariable");

    if (sel && !sel.__404RnfV393DropdownBound) {
      sel.__404RnfV393DropdownBound = true;

      sel.addEventListener("change", function () {
        postCleanSoon(document.body);
      }, true);
    }
  }

  var observer = new MutationObserver(function (mutations) {
    var detected = false;

    mutations.forEach(function (m) {
      arr(m.addedNodes).forEach(function (n) {
        if (isHmMapNode(n)) detected = true;
      });
    });

    if (detected) {
      postCleanSoon(document.body);
    }
  });

  function install() {
    installDropdownCleanup();

    try {
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
    } catch (e) {}

    postCleanSoon(document.body);

    console.log("[404_RNF] V393 replace-not-append map fix installed");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }

  window.__404_RNF_cleanupV393HmMaps = function () {
    cleanupAfterRender(document.body);
    var count = document.querySelectorAll("svg.hm-map-svg").length;
    console.log("[404_RNF] hm-map-svg count after cleanup =", count, "selected =", getVariable());
    return count;
  };

})();
/* 404_RNF_V393_REPLACE_NOT_APPEND_FIX_END */
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
        "HM KPI well map fallback rendered" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt or
        "hmVariable" in txt
    ):
        targets.append(p)

if not targets:
    raise SystemExit("No web target found for V393 replace-not-append fix.")

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
