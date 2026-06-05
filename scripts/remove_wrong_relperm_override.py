from pathlib import Path

p = Path("app/relperm_sensitivity_agent.py")
txt = p.read_text(encoding="utf-8-sig")

marker = "# --- 404_RNF_FINAL_RELPERM_PRT_IXF_MAPPING_OVERRIDE ---"

if marker in txt:
    txt = txt.split(marker)[0].rstrip() + "\n"
    p.write_text(txt, encoding="utf-8")
    print("[OK] Removed final diagnosis-folder override from relperm_sensitivity_agent.py")
else:
    p.write_text(txt, encoding="utf-8")
    print("[OK] No final diagnosis-folder override found")
