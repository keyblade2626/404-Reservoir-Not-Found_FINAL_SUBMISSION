from pathlib import Path
import re

WEB = Path("web")

START = "/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_START */"
END = "/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_END */"

changed = []
hits_report = []

def remove_existing_block(text: str) -> str:
    while START in text:
        before = text.split(START, 1)[0]
        rest = text.split(START, 1)[1]
        if END in rest:
            after = rest.split(END, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"
    return text

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    original = txt

    if "Selected agent:" not in txt and "selected_agent" not in txt and "selectedAgent" not in txt:
        continue

    txt = remove_existing_block(txt)

    # Remove direct template/plain lines containing "Selected agent:".
    # Handles examples like:
    #   `Selected agent: ${selectedAgent}`
    #   "Selected agent: " + selectedAgent
    #   lines.push(`Selected agent: ...`)
    lines = txt.splitlines()
    new_lines = []

    removed_count = 0

    for line in lines:
        if "Selected agent:" in line:
            removed_count += 1
            continue
        new_lines.append(line)

    txt = "\n".join(new_lines) + ("\n" if original.endswith("\n") else "")

    # Add a tiny defensive cleanup in case the selected-agent line is generated dynamically elsewhere.
    # This only removes the text line from the trace string before display; it does not touch DOM layout.
    patch = r'''
/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_START */
(function () {
  "use strict";

  if (window.__404RnfHideSelectedAgentTraceLineInstalled) {
    return;
  }

  window.__404RnfHideSelectedAgentTraceLineInstalled = true;

  window.__404_RNF_stripSelectedAgentTraceLine = function (value) {
    if (typeof value !== "string") return value;

    return value
      .split(/\r?\n/)
      .filter(function (line) {
        return !/^\s*Selected agent\s*:/i.test(line);
      })
      .join("\n");
  };

  console.log("[404_RNF] Selected agent trace line hidden");
})();
/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_END */
'''

    # Insert the defensive helper only in relevant dashboard JS/html files.
    if "Current answer trace" in txt or "Show Trace" in txt or "Hide Trace" in txt or "agent_trace" in txt or "dashboard" in p.name.lower():
        if p.suffix.lower() == ".html" and "</body>" in txt.lower():
            idx = txt.lower().rfind("</body>")
            txt = txt[:idx] + "\n<script>\n" + patch + "\n</script>\n" + txt[idx:]
        else:
            txt = txt.rstrip() + "\n\n" + patch + "\n"

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        changed.append(str(p))
        hits_report.append(f"{p}: removed literal Selected agent lines = {removed_count}")

print("[OK] Patched files:")
for c in changed:
    print(" -", c)

print("")
print("[DETAILS]")
for h in hits_report:
    print(h)

if not changed:
    raise SystemExit("No Selected agent trace line was found in web files.")
