from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))

from app import relperm_sensitivity_agent as mod

rows = mod.load_context_rows()

summary = []

print("\n=== RELPERM BACKEND CANDIDATE TEST ===")

for row in rows:
    well = mod.norm_well(row.get("well"))
    if not well:
        continue

    result = mod.build_relperm_sensitivity_cached_v96(well)

    item = {
        "well": well,
        "ok": result.get("ok"),
        "eligible": result.get("eligible"),
        "model": result.get("model"),
        "target_bias": result.get("target_bias"),
        "factor": result.get("factor"),
        "message": result.get("message"),
        "bridge": result.get("eligibility_bridge"),
        "bridge_confidence": result.get("bridge_confidence"),
    }

    summary.append(item)

    print(
        f"{well:8s} eligible={str(item['eligible']):5s} "
        f"model={str(item['model']):25s} "
        f"bias={str(item['target_bias']):20s} "
        f"factor={str(item['factor']):8s} "
        f"bridge={str(item['bridge'])}"
    )
    print("   ", item["message"])

eligible = [x for x in summary if x.get("eligible")]
print("\nEligible count:", len(eligible))
print("Eligible wells:", [x["well"] for x in eligible])

Path("artifacts/relperm/relperm_candidate_test_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False, default=str),
    encoding="utf-8"
)

if len(eligible) == 0:
    raise SystemExit("No eligible RelPerm candidates after bridge patch.")

print("\n[OK] At least one RelPerm candidate is now available.")
print("[OK] Summary written to artifacts/relperm/relperm_candidate_test_summary.json")
