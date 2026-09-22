"""OpenAI-compatible provider helpers for AkashAI.

Supports self-hosted/free OpenAI-compatible endpoints such as a personal
GPT-OSS proxy. The endpoint URL is configured through environment variables.
"""

import os
import httpx

def _settings():
    return (
        os.getenv("AI_COMPAT_URL", "").strip().rstrip("/"),
        os.getenv("AI_COMPAT_API_KEY", "").strip(),
        os.getenv("AI_COMPAT_MODEL", "gpt-oss-120b").strip(),
        float(os.getenv("AI_COMPAT_TIMEOUT", "120")),
    )


def configured() -> bool:
    return bool(_settings()[0])


def chat(messages, *, timeout=None):
    """Call an OpenAI-compatible chat endpoint.

    This is intentionally separate from the main provider loop so AkashAI can
    use free/self-hosted endpoints without requiring a vendor API key.
    """
    ai_url, api_key, model, default_timeout = _settings()
    if not ai_url:
        raise RuntimeError("AI_COMPAT_URL is not configured.")

    url = ai_url
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    r = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout or default_timeout,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]
