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
    ("/* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */", "/* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */"),
]

TARGET_LOG = "HM KPI well map fallback rendered"

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
    text = re.sub(r"<script>\s*</script>\s*", "", text, flags=re.IGNORECASE)
    return text

def find_matching_brace(text: str, open_pos: int):
    """
    JS-ish brace matcher that ignores strings and comments.
    open_pos must point to '{'.
    """
    depth = 0
    i = open_pos
    n = len(text)
    state = "code"
    quote = None

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch in ["'", '"', "`"]:
                state = "string"
                quote = ch
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i

        elif state == "line_comment":
            if ch in "\r\n":
                state = "code"

        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue

        elif state == "string":
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                state = "code"
                quote = None

        i += 1

    return None

def find_function_candidates(text: str):
    """
    Returns candidates as dicts with function name, start, open_brace, close_brace.
    Includes function declarations, arrow functions, and object/class methods.
    """
    patterns = [
        ("function_decl", r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
        ("function_expr", r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\([^)]*\)\s*\{"),
        ("arrow_expr", r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{"),
        ("arrow_onearg", r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>\s*\{"),
        ("method", r"([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
    ]

    out = []

    for kind, pat in patterns:
        for m in re.finditer(pat, text, flags=re.MULTILINE):
            open_brace = text.find("{", m.start(), m.end() + 1)
            if open_brace < 0:
                continue
            close_brace = find_matching_brace(text, open_brace)
            if close_brace is None:
                continue
            out.append({
                "kind": kind,
                "name": m.group(1),
                "start": m.start(),
                "open": open_brace,
                "close": close_brace,
            })

    # Deduplicate by opening brace
    seen = set()
    uniq = []
    for c in sorted(out, key=lambda x: (x["open"], x["close"])):
        if c["open"] in seen:
            continue
        seen.add(c["open"])
        uniq.append(c)
    return uniq

def patch_real_outer_renderer(text: str, file_label: str):
    if TARGET_LOG not in text:
        return text, False, "target log not found"

    log_idx = text.find(TARGET_LOG)
    candidates = find_function_candidates(text)

    containing = [
        c for c in candidates
        if c["open"] < log_idx < c["close"]
    ]

    if not containing:
        return text, False, "no enclosing function found"

    # Prefer the smallest function block that actually contains the log,
    # but avoid tiny helpers by requiring that the block text contains map/SVG/fallback terms.
    scored = []
    for c in containing:
        body = text[c["open"]:c["close"]]
        score = 0
        low_name = c["name"].lower()
        low_body = body.lower()

        if "v393" in low_body:
            score += 10
        if "hm-map-svg" in low_body:
            score += 10
        if "hm-well-point-v393" in low_body:
            score += 10
        if "fallback" in low_body:
            score += 8
        if "render" in low_name:
            score += 8
        if "map" in low_name:
            score += 6
        if "fallback" in low_name:
            score += 8
        if "innerhtml" in low_body or "appendchild" in low_body or "insertadjacenthtml" in low_body:
            score += 6

        size = c["close"] - c["open"]
        scored.append((score, -size, c))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    chosen = scored[0][2]

    body_preview = text[chosen["open"]:chosen["close"]][:500].replace("\n", " ")

    guard = f"""
  /* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */
  if (window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER === true) {{
    console.log("[404_RNF] V393 outer HM KPI fallback renderer skipped", {{
      functionName: "{chosen['name']}",
      file: "{file_label}"
    }});
    return;
  }}
  /* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */
"""

    insert_pos = chosen["open"] + 1

    local = text[insert_pos:insert_pos + 1200]
    if "404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER" in local:
        return text, True, f"already patched {chosen['name']}"

    patched = text[:insert_pos] + guard + text[insert_pos:]

    details = (
        f"patched function={chosen['name']} kind={chosen['kind']} "
        f"start={chosen['start']} open={chosen['open']} close={chosen['close']} "
        f"preview={body_preview[:180]}"
    )
    return patched, True, details

def install_global_flag(text: str, path: Path) -> str:
    if "window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER = true" in text:
        return text

    flag = """
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_START */
window.__404_RNF_DISABLE_V393_HM_KPI_OUTER_RENDERER = true;
/* 404_RNF_DISABLE_V393_OUTER_RENDERER_END */
"""

    # For JS, prepend.
    if path.suffix.lower() == ".js":
        return flag + "\n" + text

    # For HTML, inject into head.
    if path.suffix.lower() == ".html" and "</head>" in text.lower():
        lower = text.lower()
        idx = lower.find("</head>")
        return text[:idx] + "\n<script>\n" + flag + "\n</script>\n" + text[idx:]

    return flag + "\n" + text

changed = []
patch_reports = []

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue

    original = txt
    txt = strip_old_patches(txt)

    relevant = (
        TARGET_LOG in txt or
        "hmVariable" in txt or
        "hm-map-svg" in txt or
        "hm-well-point-v393" in txt
    )

    if TARGET_LOG in txt:
        txt, ok, detail = patch_real_outer_renderer(txt, str(p))
        patch_reports.append(f"{p}: {detail}")

    if relevant:
        txt = install_global_flag(txt, p)

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        changed.append(str(p))

print("[OK] Changed files:")
for c in changed:
    print(" -", c)

print("\n[PATCH REPORT]")
for r in patch_reports:
    print(r)

if not any("patched function=" in r or "already patched" in r for r in patch_reports):
    raise SystemExit("Failed to patch the real V393 renderer function.")

# Verify no old bad patches remain.
joined = ""
for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    try:
        joined += "\n" + p.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        pass

bad = [
    "404_RNF_DISABLE_V393_SOURCE_RENDERER_START",
    "404_RNF_SAFE_HIDE_V393_FALLBACK_ONLY_START",
    "404_RNF_DISABLE_V393_FALLBACK_HM_MAP_START",
    "404_RNF_V393_REPLACE_NOT_APPEND_FIX_START",
    "404_RNF_V393_HM_MAP_SVG_DUPLICATE_FIX_START",
    "404_RNF_HM_VARIABLE_MAP_OVERLAY_GUARD_START",
]

left = [b for b in bad if b in joined]
if left:
    raise SystemExit("Old/bad patch markers still present: " + ", ".join(left))

print("[OK] Old/bad patch markers removed")
print("[OK] Outer renderer patch installed")
