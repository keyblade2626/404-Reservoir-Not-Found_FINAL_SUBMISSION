from pathlib import Path
import re

p = Path("web/landing.html")
html = p.read_text(encoding="utf-8-sig")

style_block = r'''
<style id="activate-case-loading-style">
  .activate-case-loading-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: none;
    align-items: center;
    justify-content: center;
    background: rgba(3, 10, 24, 0.72);
    backdrop-filter: blur(8px);
  }

  .activate-case-loading-overlay.is-visible {
    display: flex;
  }

  .activate-case-loading-card {
    width: min(520px, calc(100vw - 40px));
    padding: 28px 30px;
    border-radius: 22px;
    background: linear-gradient(145deg, rgba(8, 20, 38, 0.98), rgba(14, 38, 58, 0.98));
    border: 1px solid rgba(110, 231, 255, 0.35);
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
    color: #f4fbff;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    text-align: center;
  }

  .activate-case-loading-spinner {
    width: 54px;
    height: 54px;
    margin: 0 auto 18px auto;
    border-radius: 50%;
    border: 4px solid rgba(255, 255, 255, 0.22);
    border-top-color: #6ee7ff;
    border-right-color: #82f7b4;
    animation: activateCaseSpin 0.9s linear infinite;
  }

  @keyframes activateCaseSpin {
    to {
      transform: rotate(360deg);
    }
  }

  .activate-case-loading-title {
    margin: 0 0 8px 0;
    font-size: 21px;
    font-weight: 800;
    letter-spacing: -0.02em;
  }

  .activate-case-loading-text {
    margin: 0;
    color: rgba(244, 251, 255, 0.82);
    font-size: 15px;
    line-height: 1.45;
  }

  .activate-case-loading-subtext {
    margin-top: 14px;
    color: rgba(130, 247, 180, 0.9);
    font-size: 13px;
    font-weight: 650;
  }
</style>
'''

overlay_block = r'''
<div id="activateCaseLoadingOverlay" class="activate-case-loading-overlay" aria-live="polite" aria-hidden="true">
  <div class="activate-case-loading-card">
    <div class="activate-case-loading-spinner"></div>
    <h3 class="activate-case-loading-title">Activating case and rebuilding diagnostics...</h3>
    <p class="activate-case-loading-text">
      The model files are being activated and the diagnostic KPI pipeline is running.
      This may take a few minutes. Please keep this page open.
    </p>
    <div class="activate-case-loading-subtext">Preparing dashboard evidence and well diagnostics</div>
  </div>
</div>
'''

script_block = r'''
<script id="activate-case-loading-script">
(function () {
  function getOverlay() {
    return document.getElementById("activateCaseLoadingOverlay");
  }

  function showActivateCaseLoading() {
    var overlay = getOverlay();
    if (!overlay) return;
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");

    document.querySelectorAll("button, input[type='button'], input[type='submit']").forEach(function (btn) {
      var txt = (btn.innerText || btn.value || "").toLowerCase();
      if (txt.includes("activate")) {
        btn.disabled = true;
        btn.dataset.originalText = btn.innerText || btn.value || "";
        if (btn.innerText) {
          btn.innerText = "Activating...";
        } else if (btn.value) {
          btn.value = "Activating...";
        }
      }
    });
  }

  function hideActivateCaseLoading() {
    var overlay = getOverlay();
    if (!overlay) return;
    overlay.classList.remove("is-visible");
    overlay.setAttribute("aria-hidden", "true");

    document.querySelectorAll("button, input[type='button'], input[type='submit']").forEach(function (btn) {
      if (btn.dataset.originalText) {
        if (btn.innerText) {
          btn.innerText = btn.dataset.originalText;
        } else if (btn.value) {
          btn.value = btn.dataset.originalText;
        }
        delete btn.dataset.originalText;
      }
      btn.disabled = false;
    });
  }

  function isActivateRequest(input) {
    var url = "";
    if (typeof input === "string") {
      url = input;
    } else if (input && input.url) {
      url = input.url;
    }

    return (
      url.includes("/api/completed-run/activate") ||
      url.includes("/api/activate-uploaded-case/")
    );
  }

  document.addEventListener("click", function (event) {
    var el = event.target;
    if (!el) return;

    var btn = el.closest ? el.closest("button, a, input[type='button'], input[type='submit']") : null;
    if (!btn) return;

    var txt = (btn.innerText || btn.value || btn.getAttribute("aria-label") || "").toLowerCase();
    var href = (btn.getAttribute("href") || "").toLowerCase();
    var dataAction = (btn.getAttribute("data-action") || "").toLowerCase();

    if (
      txt.includes("activate") ||
      href.includes("activate") ||
      dataAction.includes("activate")
    ) {
      showActivateCaseLoading();
    }
  }, true);

  if (!window.__activateCaseFetchWrapped) {
    window.__activateCaseFetchWrapped = true;
    var originalFetch = window.fetch;

    window.fetch = function (input, init) {
      var activateRequest = isActivateRequest(input);

      if (activateRequest) {
        showActivateCaseLoading();
      }

      return originalFetch(input, init)
        .then(function (response) {
          if (activateRequest && !response.ok) {
            hideActivateCaseLoading();
          }
          return response;
        })
        .catch(function (error) {
          if (activateRequest) {
            hideActivateCaseLoading();
          }
          throw error;
        });
    };
  }

  window.showActivateCaseLoading = showActivateCaseLoading;
  window.hideActivateCaseLoading = hideActivateCaseLoading;
})();
</script>
'''

# Remove old blocks if present.
html = re.sub(r'\n?<style id="activate-case-loading-style">[\s\S]*?</style>\s*', "\n", html)
html = re.sub(r'\n?<div id="activateCaseLoadingOverlay"[\s\S]*?</div>\s*</div>\s*', "\n", html)
html = re.sub(r'\n?<script id="activate-case-loading-script">[\s\S]*?</script>\s*', "\n", html)

# Insert style before </head> if possible.
if "</head>" in html:
    html = html.replace("</head>", style_block + "\n</head>", 1)
else:
    html = style_block + "\n" + html

# Insert overlay and script before </body> if possible.
insert_block = overlay_block + "\n" + script_block

if "</body>" in html:
    html = html.replace("</body>", insert_block + "\n</body>", 1)
else:
    html = html + "\n" + insert_block

p.write_text(html, encoding="utf-8")

print("[OK] web/landing.html patched with Activate loading overlay")
print("style:", "activate-case-loading-style" in html)
print("overlay:", "activateCaseLoadingOverlay" in html)
print("script:", "activate-case-loading-script" in html)
