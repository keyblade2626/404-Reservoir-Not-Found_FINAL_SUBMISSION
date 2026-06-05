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
    ("/* 404_RNF_DISABLE_V393_SOURCE_RENDERER_START */", "/* 404_RNF_DISABLE_V393_SOURCE_RENDERER_END */"),
]

SOURCE_MARKER = "/* 404_RNF_DISABLE_V393_SOURCE_RENDERER_START */"

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

def strip_old_patches(text: str) -> str:
    for start, end in OLD_BLOCKS:
        text = remove_block(text, start, end)

    # Remove empty script tags left by prior injected patches.
    text = re.sub(r"<script>\s*</script>\s*", "", text, flags=re.IGNORECASE)
    return text

def find_enclosing_function_insert_pos(text: str, idx: int):
    """
    Finds nearest enclosing function-like block before the V393 console log.
    We insert after the opening brace, so the fallback renderer returns before creating DOM.
    """
    start_window = max(0, idx - 12000)
    window = text[start_window:idx]

    patterns = [
        r"(?:async\s+)?function\s+[\w$]+\s*\([^)]*\)\s*\{",
        r"(?:const|let|var)\s+[\w$]+\s*=\s*(?:async\s*)?function\s*\([^)]*\)\s*\{",
        r"(?:const|let|var)\s+[\w$]+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{",
        r"(?:const|let|var)\s+[\w$]+\s*=\s*(?:async\s*)?[\w$]+\s*=>\s*\{",
    ]

    candidates = []

    for pat in patterns:
        for m in re.finditer(pat, window, flags=re.MULTILINE):
            candidates.append((start_window + m.start(), start_window + m.end(), m.group(0)))

    if not candidates:
        return None

    # nearest function-like opening before log
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]

def patch_v393_renderer(text: str):
    target = "HM KPI well map fallback rendered"

    if target not in text:
        return text, False, "target log not found"

    idx = text.find(target)

    insert_pos = find_enclosing_function_insert_pos(text, idx)

    if insert_pos is None:
        return text, False, "could not find enclosing function"

    guard = """
  /* 404_RNF_DISABLE_V393_SOURCE_RENDERER_START */
  if (window.__404_RNF_DISABLE_V393_HM_KPI_FALLBACK_RENDERER === true) {
    console.log("[404_RNF] V393 HM KPI fallback renderer skipped at source");
    return;
  }
  /* 404_RNF_DISABLE_V393_SOURCE_RENDERER_END */
"""

    # Avoid duplicate if rerun.
    local = text[max(0, insert_pos - 300):insert_pos + 800]
    if "404_RNF_DISABLE_V393_HM_KPI_FALLBACK_RENDERER" in local:
        return text, True, "already patched"

    text = text[:insert_pos] + guard + text[insert_pos:]
    return text, True, "patched"

def install_global_flag(text: str, path: Path) -> str:
    flag_block = """
/* 404_RNF_DISABLE_V393_SOURCE_RENDERER_START */
window.__404_RNF_DISABLE_V393_HM_KPI_FALLBACK_RENDERER = true;
/* 404_RNF_DISABLE_V393_SOURCE_RENDERER_END */
"""

    if "window.__404_RNF_DISABLE_V393_HM_KPI_FALLBACK_RENDERER = true" in text:
        return text

    if path.suffix.lower() == ".html" and "</head>" in text.lower():
        lower = text.lower()
        idx = lower.find("</head>")
        return text[:idx] + "\n<script>\n" + flag_block + "\n</script>\n" + text[idx:]

    return flag_block + "\n" + text

changed = []
errors = []

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    original = txt
    txt = strip_old_patches(txt)

    # Install global flag in files that own the dashboard dropdown or renderer.
    owns_dashboard = (
        "hmVariable" in txt or
        "HM KPI well map fallback rendered" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt
    )

    patched_renderer = False
    reason = ""

    if "HM KPI well map fallback rendered" in txt:
        txt, patched_renderer, reason = patch_v393_renderer(txt)
        print(f"[INFO] Renderer patch in {p}: {reason}")

    if owns_dashboard:
        txt = install_global_flag(txt, p)

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        changed.append(str(p))

print("[OK] Changed files:")
for x in changed:
    print(" -", x)

if not changed:
    raise SystemExit("No frontend files were changed; V393 renderer may be in a different file.")

# Verify that no old aggressive markers remain.
joined = ""
for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        joined += "\n" + p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        pass

bad_markers = [
    "404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_START",
    "404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_START",
    "404_RNF_V393_REPLACE_NOT_APPEND_FIX_START",
    "404_RNF_DISABLE_V393_FALLBACK_HM_MAP_START",
    "404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_START",
]

left = [m for m in bad_markers if m in joined]

if left:
    raise SystemExit("Old aggressive markers still present: " + ", ".join(left))

if "404_RNF_DISABLE_V393_HM_KPI_FALLBACK_RENDERER" not in joined:
    raise SystemExit("Source renderer disable flag was not installed.")

print("[OK] Old aggressive patches removed")
print("[OK] V393 source renderer disable installed")
