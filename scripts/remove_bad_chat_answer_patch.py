from pathlib import Path
import re

WEB = Path("web")

START = "/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_START */"
END = "/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_END */"

changed = []

def remove_block(text: str) -> str:
    while START in text:
        before = text.split(START, 1)[0]
        rest = text.split(START, 1)[1]

        if END in rest:
            after = rest.split(END, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"

    text = re.sub(r"<script>\s*</script>\s*", "", text, flags=re.IGNORECASE)
    return text

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    new = remove_block(txt)

    if new != txt:
        p.write_text(new, encoding="utf-8")
        changed.append(str(p))

print("[OK] Files cleaned:")
for c in changed:
    print(" -", c)

if not changed:
    print("[INFO] No bad chat answer patch marker found.")
