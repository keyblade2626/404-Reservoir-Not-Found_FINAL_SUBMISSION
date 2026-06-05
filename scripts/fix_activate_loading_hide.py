from pathlib import Path
import re

p = Path("web/landing.html")
html = p.read_text(encoding="utf-8-sig")

new_script = r'''
<script id="activate-case-loading-script">
(function () {
  var activateLoadingSafetyTimer = null;

  function getOverlay() {
    return document.getElementById("activateCaseLoadingOverlay");
  }

  function setActivateButtonsDisabled(disabled) {
    document.querySelectorAll("button, input[type='button'], input[type='submit']").forEach(function (btn) {
      var txt = (btn.innerText || btn.value || "").toLowerCase();

      if (txt.includes("activate") || btn.dataset.activateLoadingManaged === "true") {
        if (disabled) {
          btn.dataset.activateLoadingManaged = "true";
          btn.disabled = true;

          if (!btn.dataset.originalText) {
            btn.dataset.originalText = btn.innerText || btn.value || "";
          }

          if (btn.innerText) {
            btn.innerText = "Activating...";
          } else if (btn.value) {
            btn.value = "Activating...";
          }
        } else {
          if (btn.dataset.originalText) {
            if (btn.innerText) {
              btn.innerText = btn.dataset.originalText;
            } else if (btn.value) {
              btn.value = btn.dataset.originalText;
            }
          }

          btn.disabled = false;
          delete btn.dataset.originalText;
          delete btn.dataset.activateLoadingManaged;
        }
      }
    });
  }

  function showActivateCaseLoading() {
    var overlay = getOverlay();
    if (!overlay) return;

    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    setActivateButtonsDisabled(true);

    if (activateLoadingSafetyTimer) {
      clearTimeout(activateLoadingSafetyTimer);
    }

    // Safety fallback: never keep the overlay forever.
    activateLoadingSafetyTimer = setTimeout(function () {
      hideActivateCaseLoading();
    }, 5 * 60 * 1000);
  }

  function hideActivateCaseLoading() {
    var overlay = getOverlay();

    if (activateLoadingSafetyTimer) {
      clearTimeout(activateLoadingSafetyTimer);
      activateLoadingSafetyTimer = null;
    }

    if (overlay) {
      overlay.classList.remove("is-visible");
      overlay.setAttribute("aria-hidden", "true");
    }

    setActivateButtonsDisabled(false);
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
          if (activateRequest) {
            // The activation + diagnostics pipeline is complete when the response returns.
            // Hide overlay shortly after success so the UI can update or navigate.
            setTimeout(function () {
              hideActivateCaseLoading();
            }, response.ok ? 500 : 0);
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

  // Extra safety: if the user returns to the page from browser cache, do not show stale overlay.
  window.addEventListener("pageshow", function () {
    hideActivateCaseLoading();
  });

  window.showActivateCaseLoading = showActivateCaseLoading;
  window.hideActivateCaseLoading = hideActivateCaseLoading;
})();
</script>
'''

html2 = re.sub(
    r'<script id="activate-case-loading-script">[\s\S]*?</script>',
    new_script,
    html,
    count=1
)

if html2 == html:
    raise SystemExit("activate-case-loading-script block not found in landing.html")

p.write_text(html2, encoding="utf-8")
print("[OK] Fixed activate loading overlay hide logic")
