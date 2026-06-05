import json
from pathlib import Path

required = [
    "timestamp",
    "run_id",
    "agent_name",
    "action",
    "input_summary",
    "output_summary",
    "target_agent",
    "confidence",
    "retry_count",
    "status",
]

paths = sorted(Path("logs").glob("trace-example-*.jsonl"))

if len(paths) != 4:
    raise SystemExit(f"Expected 4 trace-example JSONL files, found {len(paths)}")

for path in paths:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            missing = [k for k in required if k not in obj]
            if missing:
                raise SystemExit(f"{path}:{lineno} missing keys: {missing}")
            count += 1

    if count == 0:
        raise SystemExit(f"{path} has zero events")

    print(f"[OK] {path} events={count}")

print("[OK] All official JSONL traces are valid")
