from pathlib import Path

p = Path("app/relperm_mobility_agent.py")
txt = p.read_text(encoding="utf-8-sig")

# Your data folder contains RELPERM.ixf. Windows ignores case, Docker/Linux does not.
txt = txt.replace('IXF_PATH = MODEL_DIR / "RELPERM.IXF"', 'IXF_PATH = MODEL_DIR / "RELPERM.ixf"')

p.write_text(txt, encoding="utf-8")
print("[OK] relperm_mobility_agent.py filename case aligned")
