from pathlib import Path
import re

WEB = Path("web")

BLOCKS = [
    ("/* 404_RNF_TRACE_DISPLAY_ONLY_FIX_START */", "/* 404_RNF_TRACE_DISPLAY_ONLY_FIX_END */"),
    ("/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_START */", "/* 404_RNF_HIDE_SELECTED_AGENT_TRACE_LINE_END */"),
    ("/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_START */", "/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_END */"),
]

def remove_block(text, start, end):
    while start in text:
        before = text.split(start, 1)[0]
        rest = text.split(start, 1)[1]
        if end in rest:
            after = rest.split(end, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"
    return text

changed = []

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    original = txt

    for start, end in BLOCKS:
        txt = remove_block(txt, start, end)

    txt = re.sub(r"<script>\s*</script>\s*", "", txt, flags=re.I)

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        changed.append(str(p))

print("[OK] Removed partial frontend patches from:")
for c in changed:
    print(" -", c)

if not changed:
    print("[INFO] No partial frontend trace/chat patch found.")
