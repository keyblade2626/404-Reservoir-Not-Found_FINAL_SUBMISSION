from pathlib import Path
import json

for name in ["README.md", "ARCHITECTURE.md", "metadata.json"]:
    p = Path(name)
    txt = p.read_text(encoding="utf-8-sig")
    p.write_text(txt, encoding="utf-8")
    print("[OK] UTF-8 no BOM:", name)

json.load(open("metadata.json", encoding="utf-8"))
print("[OK] metadata.json valid JSON")
