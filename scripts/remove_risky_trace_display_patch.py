from pathlib import Path
import re

WEB = Path("web")

RISKY_TRACE_START = "/* 404_RNF_TRACE_DISPLAY_ONLY_FIX_START */"
RISKY_TRACE_END = "/* 404_RNF_TRACE_DISPLAY_ONLY_FIX_END */"

changed = []

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

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    original = txt

    txt = remove_block(txt, RISKY_TRACE_START, RISKY_TRACE_END)
    txt = re.sub(r"<script>\s*</script>\s*", "", txt, flags=re.I)

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        changed.append(str(p))

print("[OK] Removed risky trace display patch from:")
for c in changed:
    print(" -", c)

if not changed:
    print("[INFO] No risky trace display patch was present.")
