"""
llm access in one place so the provider can be swapped. currently Google Gemini
(REST generateContent with structured json output), called with httpx.
"""
import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    """the call failed for this input; others may still work"""


class LLMRateLimitError(LLMError):
    """rate limit or quota hit: stop calling until the next run"""


class LLMOverloadedError(LLMError):
    """model temporarily overloaded (503); failed calls still count against the free-tier quota"""


def _gemini_schema(schema: dict) -> dict:
    #callers pass json-schema style lowercase types; gemini's schema uses STRING, OBJECT, ...
    out = {}
    for key, value in schema.items():
        if key == "type":
            out[key] = value.upper()
        elif key == "properties":
            out[key] = {name: _gemini_schema(prop) for name, prop in value.items()}
        elif key == "items":
            out[key] = _gemini_schema(value)
        else:
            out[key] = value
    return out


async def generate_json(system: str, prompt: str, schema: dict, timeout: float = 120.0) -> Any:
    """
    run one prompt and return the parsed json reply, which follows `schema`
    (json-schema style: type, properties, items, enum, nullable, required).
    raises LLMRateLimitError on 429 / quota errors and LLMError on anything else.
    """
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set")

    body ={
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(schema),
        },
    }
    url = GEMINI_URL.format(model=settings.GEMINI_MODEL)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body, headers={"x-goog-api-key": settings.GEMINI_API_KEY})
    except httpx.HTTPError as exc:
        raise LLMError(f"gemini request failed: {exc}") from exc

    if resp.status_code != 200:
        try:
            error = resp.json().get("error", {})
        except ValueError:
            error =   {}
        message = f"gemini {resp.status_code}: {error.get('message', resp.text[:200])}"
        if resp.status_code == 429 or error.get("status") == "RESOURCE_EXHAUSTED":
            raise LLMRateLimitError(message)
        if resp.status_code == 503:
            raise LLMOverloadedError(message)
        raise LLMError(message)

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "no candidates")
        raise LLMError(f"gemini returned no answer ({reason})")
    text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))
    try:
        return json.loads(text)
    except ValueError as exc:
        raise LLMError (f"gemini reply is not valid json: {text[:200]}") from exc