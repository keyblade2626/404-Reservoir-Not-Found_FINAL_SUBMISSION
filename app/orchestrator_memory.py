
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


MEMORY_PATH = Path("logs/orchestrator_memory.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_memory() -> Dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {}

    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_memory(data: Dict[str, Any]) -> Dict[str, Any]:
    MEMORY_PATH.parent.mkdir(exist_ok=True)

    data = dict(data or {})
    data["updated_at"] = _now()

    MEMORY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return data


def update_memory(**kwargs) -> Dict[str, Any]:
    mem = load_memory()
    mem.update({k: v for k, v in kwargs.items() if v is not None})
    return save_memory(mem)


def resolve_ordinal_candidate(text: str) -> Optional[str]:
    q = str(text or "").lower()
    mem = load_memory()
    wells = mem.get("candidate_wells") or []

    if not wells:
        return None

    ordinal_map = {
        "first": 0,
        "1st": 0,
        "primo": 0,
        "prima": 0,
        "second": 1,
        "2nd": 1,
        "secondo": 1,
        "seconda": 1,
        "third": 2,
        "3rd": 2,
        "terzo": 2,
        "terza": 2,
        "fourth": 3,
        "4th": 3,
        "quarto": 3,
        "quarta": 3,
        "fifth": 4,
        "5th": 4,
        "quinto": 4,
        "quinta": 4,
    }

    for key, idx in ordinal_map.items():
        if key in q and idx < len(wells):
            return wells[idx]

    return None
