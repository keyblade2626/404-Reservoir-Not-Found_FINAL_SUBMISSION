
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(".")


REQUIRED_FILES = [
    "run.py",
    "metadata.json",
    ".env.example",
    "README.md",
    "ARCHITECTURE.md",
]


REQUIRED_DIRS = [
    "input_examples",
    "output_examples",
    "logs",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print("[FAIL]", msg)


def ok(msg: str) -> None:
    print("[OK]", msg)


def main() -> None:
    errors: list[str] = []

    print("=== Required files ===")
    for rel in REQUIRED_FILES:
        p = ROOT / rel
        if p.exists() and p.is_file():
            ok(rel)
        else:
            fail(f"Missing required file: {rel}", errors)

    print("\n=== Required directories ===")
    for rel in REQUIRED_DIRS:
        p = ROOT / rel
        if p.exists() and p.is_dir():
            ok(rel)
        else:
            fail(f"Missing required directory: {rel}", errors)

    print("\n=== metadata.json JSON validation ===")
    try:
        metadata = read_json(ROOT / "metadata.json")
        ok("metadata.json is valid JSON")
    except Exception as exc:
        metadata = {}
        fail(f"metadata.json is invalid JSON: {exc}", errors)

    expected_metadata_keys = [
        "schema_version",
        "project_name",
        "description",
        "runtime",
        "environment_variables",
        "agents",
        "capabilities",
        "input_schema",
        "output_schema",
        "example_inputs",
        "example_outputs",
        "logs",
    ]

    for key in expected_metadata_keys:
        if key in metadata:
            ok(f"metadata key present: {key}")
        else:
            fail(f"metadata key missing: {key}", errors)

    print("\n=== .env.example check ===")
    env_path = ROOT / ".env.example"
    if env_path.exists():
        env_text = env_path.read_text(encoding="utf-8-sig", errors="ignore")

        for var in ["COMPASS_API_KEY", "HOST", "PORT"]:
            if var in env_text:
                ok(f".env.example contains {var}")
            else:
                fail(f".env.example missing {var}", errors)

        forbidden_markers = [
            "sk-",
            "AIza",
            "eyJ",
            "real_",
            "actual_",
        ]

        for marker in forbidden_markers:
            if marker in env_text:
                fail(f".env.example may contain a real credential marker: {marker}", errors)
    else:
        fail(".env.example missing", errors)

    print("\n=== Examples check ===")
    inputs = sorted((ROOT / "input_examples").glob("*.json")) if (ROOT / "input_examples").exists() else []
    outputs = sorted((ROOT / "output_examples").glob("*.json")) if (ROOT / "output_examples").exists() else []
    logs = sorted((ROOT / "logs").glob("example_*_agent_trace.json")) if (ROOT / "logs").exists() else []

    if len(inputs) >= 3:
        ok(f"input_examples count = {len(inputs)}")
    else:
        fail(f"Need at least 3 input examples, found {len(inputs)}", errors)

    if len(outputs) >= 3:
        ok(f"output_examples count = {len(outputs)}")
    else:
        fail(f"Need at least 3 output examples, found {len(outputs)}", errors)

    if len(logs) >= 3:
        ok(f"example logs count = {len(logs)}")
    else:
        fail(f"Need at least 3 example logs, found {len(logs)}", errors)

    for p in inputs + outputs + logs:
        try:
            read_json(p)
            ok(f"valid JSON: {p}")
        except Exception as exc:
            fail(f"Invalid JSON file {p}: {exc}", errors)

    print("\n=== Example correspondence check ===")
    input_stems = [p.stem for p in inputs]

    for stem in input_stems:
        suffix = stem.replace("example_", "")
        expected_output = ROOT / "output_examples" / f"example_{suffix}_output.json"
        expected_log = ROOT / "logs" / f"example_{suffix}_agent_trace.json"

        if expected_output.exists():
            ok(f"output exists for {stem}")
        else:
            fail(f"missing output for {stem}: {expected_output}", errors)

        if expected_log.exists():
            ok(f"log exists for {stem}")
        else:
            fail(f"missing log for {stem}: {expected_log}", errors)

    print("\n=== Summary ===")
    if errors:
        print(f"FAILED with {len(errors)} issue(s).")
        for e in errors:
            print("-", e)
        raise SystemExit(1)

    print("All required submission files look present and valid.")


if __name__ == "__main__":
    main()
