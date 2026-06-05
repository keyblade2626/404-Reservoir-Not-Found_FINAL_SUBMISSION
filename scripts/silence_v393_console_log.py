from pathlib import Path
import re

WEB = Path("web")

changed = []

pattern = re.compile(
    r'\s*console\.log\(\s*"\[404_RNF\]\s+V393 outer HM KPI fallback renderer skipped"\s*,\s*\{[\s\S]*?\}\s*\);\s*',
    flags=re.MULTILINE
)

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    new = pattern.sub('\n    // V393 fallback renderer intentionally skipped silently.\n', txt)

    if new != txt:
        p.write_text(new, encoding="utf-8")
        changed.append(str(p))

print("[OK] Changed files:")
for c in changed:
    print(" -", c)

if not changed:
    print("[INFO] No repeated V393 console.log found or already silenced.")
