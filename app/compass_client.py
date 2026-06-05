import os
import time
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI
from openai import OpenAIError

OFFICIAL_COMPASS_BASE_URL = "https://compass.core42.ai/v1"
WORKING_COMPASS_API_GATEWAY = "https://api.core42.ai/v1"
DEFAULT_BASE_URL = "https://api.core42.ai/v1"


load_dotenv()

def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default

def sample_mode_enabled() -> bool:
    return str(os.getenv("SAMPLE_MODE", "false")).strip().lower() == "true"

def get_compass_client() -> OpenAI:
    """
    OpenAI-compatible Compass client.

    Official Agentathon variables:
    - OPENAI_API_KEY
    - OPENAI_BASE_URL=https://api.core42.ai/v1

    Backward-compatible aliases are accepted for local development.
    """
    api_key = _env("OPENAI_API_KEY", "COMPASS_API_KEY")
    base_url = _env("OPENAI_BASE_URL", "COMPASS_API_BASE_URL", default=DEFAULT_BASE_URL)

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set it to your Compass API key."
        )

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

def get_chat_model() -> str:
    return _env("CHAT_MODEL", "COMPASS_MODEL", default="gpt-4.1")

def get_reasoning_model() -> str:
    return _env("REASONING_MODEL", "COMPASS_REASONING_MODEL", default="gpt-5.1")

def call_with_retry(fn, max_retries: int = 2, base_delay: float = 2.0):
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except OpenAIError as error:
            last_error = error

            if attempt < max_retries:
                wait_time = base_delay * (2 ** attempt)
                time.sleep(wait_time)
            else:
                raise last_error

def call_compass_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> str:
    """
    Main Compass chat helper.
    Uses Compass through the OpenAI-compatible API.
    """
    if sample_mode_enabled():
        raise RuntimeError(
            "SAMPLE_MODE=true. Real Compass calls are disabled. Set SAMPLE_MODE=false for contest mode."
        )

    client = get_compass_client()
    selected_model = model or get_chat_model()

    response = call_with_retry(
        lambda: client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )

    return response.choices[0].message.content or ""

def call_compass_reasoning(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> str:
    return call_compass_chat(
        messages=messages,
        model=get_reasoning_model(),
        temperature=temperature,
        max_tokens=max_tokens,
    )

def compass_health_check() -> Dict[str, Any]:
    """
    Lightweight Compass health check.
    """
    if sample_mode_enabled():
        return {
            "status": "sample_mode",
            "message": "SAMPLE_MODE=true. Compass call skipped. Set SAMPLE_MODE=false for final contest evaluation.",
            "base_url": _env("OPENAI_BASE_URL", "COMPASS_API_BASE_URL", default=DEFAULT_BASE_URL),
            "model": get_chat_model(),
        }

    client = get_compass_client()
    model = get_chat_model()

    response = call_with_retry(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Reply with OK only."}
            ],
            temperature=0,
            max_tokens=5,
        )
    )

    content = response.choices[0].message.content or ""

    return {
        "status": "ok" if "OK" in content.upper() else "unexpected_response",
        "base_url": _env("OPENAI_BASE_URL", "COMPASS_API_BASE_URL", default=DEFAULT_BASE_URL),
        "model": model,
        "response": content,
    }

def compass_is_configured() -> bool:
    return bool(_env("OPENAI_API_KEY", "COMPASS_API_KEY"))

if __name__ == "__main__":
    print(compass_health_check())

