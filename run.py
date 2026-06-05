from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict


def _load_env_file(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return

    for raw in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and (key not in os.environ or not os.environ.get(key)):
            os.environ[key] = value


def _extract_message(payload: Dict[str, Any]) -> str:
    for key in ["message", "query", "question", "input", "prompt"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if "messages" in payload and isinstance(payload["messages"], list):
        for item in reversed(payload["messages"]):
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    raise ValueError(
        "Input JSON must contain one of: message, query, question, input, prompt, "
        "or messages[{content: ...}]."
    )


def run_cli(input_path: str, output_path: str) -> None:
    _load_env_file(".env")

    from app.copilot_orchestrator_v700 import run_submission_message_v700

    with open(input_path, "r", encoding="utf-8-sig") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object.")

    message = _extract_message(payload)
    result = run_submission_message_v700(message)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Wrote output to {output_path}")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    _load_env_file(".env")

    import uvicorn
    from app.main import app
    from app.copilot_orchestrator_v700 import install_v700_routes

    install_v700_routes(app)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="404 Reservoir Not Found runner")
    parser.add_argument("--input", dest="input_path", help="Input JSON file")
    parser.add_argument("--output", dest="output_path", help="Output JSON file")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)

    args = parser.parse_args()

    if args.input_path or args.output_path:
        if not args.input_path or not args.output_path:
            raise SystemExit("Both --input and --output are required for CLI mode.")

        run_cli(args.input_path, args.output_path)
        return

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
