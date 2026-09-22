"""OpenAI-compatible provider helpers for AkashAI.

Supports self-hosted/free OpenAI-compatible endpoints such as a personal
GPT-OSS proxy. The endpoint URL is configured through environment variables.
"""

import os
import httpx

AI_COMPAT_URL = os.getenv("AI_COMPAT_URL", "").strip().rstrip("/")
AI_COMPAT_API_KEY = os.getenv("AI_COMPAT_API_KEY", "").strip()
AI_COMPAT_MODEL = os.getenv("AI_COMPAT_MODEL", "gpt-oss-120b").strip()
AI_COMPAT_TIMEOUT = float(os.getenv("AI_COMPAT_TIMEOUT", "120"))


def configured() -> bool:
    return bool(AI_COMPAT_URL)


def chat(messages, *, timeout=None):
    """Call an OpenAI-compatible chat endpoint.

    This is intentionally separate from the main provider loop so AkashAI can
    use free/self-hosted endpoints without requiring a vendor API key.
    """
    if not AI_COMPAT_URL:
        raise RuntimeError("AI_COMPAT_URL is not configured.")

    url = AI_COMPAT_URL
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    headers = {"Content-Type": "application/json"}
    if AI_COMPAT_API_KEY:
        headers["Authorization"] = f"Bearer {AI_COMPAT_API_KEY}"

    payload = {
        "model": AI_COMPAT_MODEL,
        "messages": messages,
        "stream": False,
    }

    r = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout or AI_COMPAT_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]
