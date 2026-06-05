import os
import json
import urllib.request
import urllib.error
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
key = os.getenv("OPENAI_API_KEY", "")
model = os.getenv("CHAT_MODEL") or os.getenv("COMPASS_MODEL") or "gpt-4.1"

if not base:
    raise SystemExit("OPENAI_BASE_URL missing")
if not key:
    raise SystemExit("OPENAI_API_KEY missing")

print("base:", base)
print("model:", model)

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Reply with exactly: Compass API gateway OK"}
    ],
    "temperature": 0
}

req = urllib.request.Request(
    f"{base}/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    },
    method="POST"
)

result = {
    "base_url": base,
    "model": model,
    "endpoint": f"{base}/chat/completions",
    "status": None,
    "ok": False,
    "body_preview": None
}

try:
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        result["status"] = resp.status
        result["ok"] = True
        result["body_preview"] = body[:1200]
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    result["status"] = e.code
    result["body_preview"] = body[:1200]
except Exception as e:
    result["body_preview"] = repr(e)

Path("logs/compass_api_gateway_generation_test.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(result, indent=2, ensure_ascii=False))

if not result["ok"]:
    raise SystemExit("Generation failed against api.core42.ai gateway")
