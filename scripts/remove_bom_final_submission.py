from pathlib import Path

paths = []

for folder in ["input_examples", "output_examples", "logs"]:
    d = Path(folder)
    if d.exists():
        paths.extend(d.glob("*.json"))
        paths.extend(d.glob("*.jsonl"))
        paths.extend(d.glob("*.md"))

for name in ["README.md", "ARCHITECTURE.md", "metadata.json", ".env.example"]:
    p = Path(name)
    if p.exists():
        paths.append(p)

for p in sorted(set(paths)):
    txt = p.read_text(encoding="utf-8-sig")
    p.write_text(txt, encoding="utf-8")
    print("[OK] UTF-8 no BOM:", p)
