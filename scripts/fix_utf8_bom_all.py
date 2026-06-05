from pathlib import Path

paths = []
for folder in ["input_examples", "output_examples", "logs"]:
    d = Path(folder)
    if d.exists():
        paths.extend(d.glob("*.json"))
        paths.extend(d.glob("*.jsonl"))

for name in ["metadata.json", "README.md", "ARCHITECTURE.md"]:
    p = Path(name)
    if p.exists():
        paths.append(p)

for p in sorted(set(paths)):
    try:
        txt = p.read_text(encoding="utf-8-sig")
        p.write_text(txt, encoding="utf-8")
        print("[OK] UTF-8 no BOM:", p)
    except Exception as exc:
        print("[WARN] Could not rewrite", p, exc)
