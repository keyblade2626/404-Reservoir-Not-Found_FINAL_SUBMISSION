from pathlib import Path
import re

ROOT = Path(".").resolve()
APP = ROOT / "app"
WEB = ROOT / "web"

FRONTEND_BAD_BLOCKS = [
    ("/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_START */", "/* 404_RNF_CHAT_ANSWER_COMPACT_DISPLAY_FIX_END */"),
]

BACKEND_OLD_BLOCKS = [
    ("# --- 404_RNF_BACKEND_COMPACT_CHAT_ANSWERS_START ---", "# --- 404_RNF_BACKEND_COMPACT_CHAT_ANSWERS_END ---"),
    ("# --- 404_RNF_BACKEND_FINAL_ANSWER_SYNTHESIZER_START ---", "# --- 404_RNF_BACKEND_FINAL_ANSWER_SYNTHESIZER_END ---"),
    ("# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_START ---", "# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_END ---"),
]

def remove_block(text: str, start: str, end: str) -> str:
    while start in text:
        before = text.split(start, 1)[0]
        rest = text.split(start, 1)[1]
        if end in rest:
            after = rest.split(end, 1)[1]
            text = before.rstrip() + "\n" + after.lstrip()
        else:
            text = before.rstrip() + "\n"
    return text

print("[INFO] Removing old unsafe frontend chat cleanup patches if present")

for p in list(WEB.glob("**/*.js")) + list(WEB.glob("**/*.html")):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    original = txt

    for start, end in FRONTEND_BAD_BLOCKS:
        txt = remove_block(txt, start, end)

    txt = re.sub(r"<script>\s*</script>\s*", "", txt, flags=re.I)

    if txt != original:
        p.write_text(txt, encoding="utf-8")
        print("[OK] Cleaned frontend file:", p)

print("[INFO] Creating app/final_answer_synthesizer_llm.py")

module = r'''
from __future__ import annotations

import copy
import json
import os
import re
from typing import Any


DIAGNOSTIC_MARKERS = [
    "Main evidence:",
    "Hypothesis ranking:",
    "Most likely explanation:",
    "This is a model-specific reservoir diagnosis",
    "Integrated diagnosis:",
]


def _compact(value: Any, limit: int = 16000) -> str:
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)

    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > limit:
        return text[:limit] + " ...[truncated]"

    return text


def _should_rewrite_answer(text: str) -> bool:
    if not isinstance(text, str):
        return False

    if len(text.strip()) < 350:
        return False

    return any(marker in text for marker in DIAGNOSTIC_MARKERS)


def _find_candidate_answer_path(obj: Any, path: list[Any] | None = None) -> list[Any] | None:
    if path is None:
        path = []

    if isinstance(obj, dict):
        # Prefer canonical final answer keys.
        for key in ["answer", "response", "final_answer"]:
            value = obj.get(key)
            if isinstance(value, str) and _should_rewrite_answer(value):
                return path + [key]

        for key, value in obj.items():
            found = _find_candidate_answer_path(value, path + [key])
            if found is not None:
                return found

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found = _find_candidate_answer_path(value, path + [i])
            if found is not None:
                return found

    return None


def _get_by_path(obj: Any, path: list[Any]) -> Any:
    cur = obj
    for key in path:
        cur = cur[key]
    return cur


def _set_by_path(obj: Any, path: list[Any], value: Any) -> None:
    cur = obj
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def _extract_user_question(payload: Any) -> str:
    keys = [
        "message",
        "question",
        "query",
        "user_question",
        "input_message",
        "prompt",
    ]

    found: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in keys and isinstance(v, str):
                    if len(v.strip()) > 5:
                        found.append(v.strip())
                else:
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(payload)

    if found:
        return found[0]

    return ""


def _extract_structured_context(payload: Any, raw_answer: str) -> str:
    # Keep the raw answer plus a compacted view of the JSON payload so the LLM
    # can use structured evidence, but do not send huge UI payloads if avoidable.
    safe_payload = copy.deepcopy(payload)

    def prune(x: Any) -> Any:
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                lk = str(k).lower()
                if lk in {
                    "html",
                    "svg",
                    "image",
                    "image_base64",
                    "data_uri",
                    "figure",
                    "plotly_json",
                }:
                    out[k] = "[omitted visual payload]"
                elif isinstance(v, str) and len(v) > 3000:
                    out[k] = v[:3000] + " ...[truncated]"
                else:
                    out[k] = prune(v)
            return out

        if isinstance(x, list):
            if len(x) > 40:
                return [prune(v) for v in x[:40]] + ["...[list truncated]"]
            return [prune(v) for v in x]

        return x

    safe_payload = prune(safe_payload)

    return (
        "RAW TOOL-AGGREGATED ANSWER:\n"
        + raw_answer
        + "\n\nSTRUCTURED RESPONSE PAYLOAD:\n"
        + _compact(safe_payload, limit=18000)
    )


def _fallback_if_llm_unavailable(raw_answer: str) -> str:
    # Fallback intentionally light: do not invent, do not over-transform.
    # It only removes obvious broken fragments and duplicate visualization narration.
    text = raw_answer

    text = text.replace("Reservoir Technical review review", "Reservoir technical review")
    text = text.replace("candidate should remain conservative..", "candidate should remain conservative.")
    text = text.replace("This is a...", "")

    text = re.sub(
        r"\n?- Streamline evidence:\s*I detected a true streamline visualization request\..*?(?=\n\n|\nHypothesis ranking:|$)",
        "",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"I built an interactive WCT profile for\s+HW-\d+[A-Z]?\.\s*WCT is computed as water rate divided by oil plus water rate\.",
        "The WCT profile is available in the evidence panel.",
        text,
        flags=re.I,
    )

    return text.strip()


def _call_llm_final_writer(user_question: str, evidence_context: str) -> str | None:
    api_key = (
        os.getenv("COMPASS_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    if not api_key:
        print("[INFO] LLM final writer skipped: COMPASS_API_KEY / OPENAI_API_KEY not set")
        return None

    model = (
        os.getenv("COMPASS_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("FINAL_WRITER_MODEL")
        or "gpt-4o-mini"
    )

    base_url = (
        os.getenv("COMPASS_BASE_URL")
        or os.getenv("COMPASS_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or None
    )

    try:
        from openai import OpenAI
    except Exception as exc:
        print("[WARN] LLM final writer skipped: openai package unavailable:", repr(exc))
        return None

    try:
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)

        system_prompt = """You are a senior reservoir engineer and final-answer writer.

You receive evidence from multiple diagnostic agents.
Your job is to write the final answer only.

Rules:
- Start with the conclusion.
- Do not repeat tool outputs.
- Do not mention that you created charts, maps, tables, or interactive visuals.
- Do not say "I built", "I loaded", or "I highlighted".
- Do not include unfinished fragments such as "This is a...".
- Do not ask for streamline timing unless the user explicitly asked for streamlines.
- Keep the answer focused on the user's question.
- Separate evidence from interpretation.
- Rank hypotheses clearly.
- End with practical next checks.
- Use only the evidence provided.
- Do not invent numbers.
- Write in concise professional reservoir-engineering English.

Required output structure:
1. Conclusion
2. Key evidence
3. Hypothesis ranking
4. Recommended next checks
"""

        user_prompt = f"""User question:
{user_question or "[not available]"}

Evidence package:
{evidence_context}

Write the final answer now.
"""

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=900,
        )

        answer = completion.choices[0].message.content

        if not answer or len(answer.strip()) < 80:
            print("[WARN] LLM final writer returned empty/short answer")
            return None

        print("[OK] LLM final writer synthesized final answer")
        return answer.strip()

    except Exception as exc:
        print("[WARN] LLM final writer failed, using fallback/raw answer:", repr(exc))
        return None


def synthesize_final_answer_payload(payload: Any) -> Any:
    path = _find_candidate_answer_path(payload)

    if path is None:
        return payload

    new_payload = copy.deepcopy(payload)
    raw_answer = _get_by_path(new_payload, path)

    if not isinstance(raw_answer, str):
        return payload

    user_question = _extract_user_question(new_payload)
    evidence_context = _extract_structured_context(new_payload, raw_answer)

    llm_answer = _call_llm_final_writer(
        user_question=user_question,
        evidence_context=evidence_context,
    )

    final_answer = llm_answer or _fallback_if_llm_unavailable(raw_answer)

    _set_by_path(new_payload, path, final_answer)

    # Add light metadata for trace/debugging without changing UI semantics.
    try:
        if isinstance(new_payload, dict):
            new_payload.setdefault("final_writer", {})
            new_payload["final_writer"] = {
                "enabled": True,
                "mode": "llm" if llm_answer else "fallback",
                "answer_path": [str(x) for x in path],
            }
    except Exception:
        pass

    return new_payload
'''

(APP / "final_answer_synthesizer_llm.py").write_text(module, encoding="utf-8")
print("[OK] Wrote app/final_answer_synthesizer_llm.py")

# 3) Patch FastAPI app with middleware.
candidates = []
for p in APP.glob("**/*.py"):
    txt = p.read_text(encoding="utf-8-sig", errors="ignore")
    if "FastAPI(" in txt and re.search(r"\bapp\s*=", txt):
        candidates.append(p)

if not candidates:
    raise SystemExit("Could not find FastAPI app file.")

target = None
for p in candidates:
    if p.name == "main.py":
        target = p
        break
if target is None:
    target = candidates[0]

txt = target.read_text(encoding="utf-8-sig", errors="ignore")

for start, end in BACKEND_OLD_BLOCKS:
    txt = remove_block(txt, start, end)

middleware = r'''
# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_START ---
# True LLM final writer middleware.
# It rewrites only final JSON answer/response fields from chat endpoints.
# Frontend/dashboard DOM is not touched.

try:
    import json as _404_llm_json
    from fastapi.responses import JSONResponse as _404_llm_JSONResponse
    from app.final_answer_synthesizer_llm import synthesize_final_answer_payload as _404_synthesize_final_answer_payload

    @app.middleware("http")
    async def _404_llm_final_writer_middleware(request, call_next):
        response = await call_next(request)

        path = str(request.url.path or "")

        if path not in {
            "/run",
            "/api/agent-chat-v501",
            "/api/agent-chat",
            "/api/chat",
        }:
            return response

        content_type = str(response.headers.get("content-type", "")).lower()

        if "application/json" not in content_type:
            return response

        body = b""

        async for chunk in response.body_iterator:
            body += chunk

        try:
            payload = _404_llm_json.loads(body.decode("utf-8"))
        except Exception:
            return response

        new_payload = _404_synthesize_final_answer_payload(payload)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("content-type", None)

        return _404_llm_JSONResponse(
            content=new_payload,
            status_code=response.status_code,
            headers=headers,
        )

    print("[OK] LLM final writer middleware installed")

except Exception as _404_llm_final_writer_exc:
    print("[WARN] LLM final writer middleware not installed:", repr(_404_llm_final_writer_exc))

# --- 404_RNF_LLM_FINAL_WRITER_MIDDLEWARE_END ---
'''

txt = txt.rstrip() + "\n\n" + middleware + "\n"
target.write_text(txt, encoding="utf-8")

print("[OK] Patched FastAPI app file:", target)
