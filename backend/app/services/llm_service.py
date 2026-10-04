"""
llm access in one place. every provider in PROVIDERS whose api key is set is enabled;
catalyst extraction asks all of them and compares the answers (cross-model voting).
Google Gemini uses its own REST api, the others an openai-compatible chat completions api,
all called with httpx. a new openai-compatible provider is one PROVIDERS entry + its key setting.
"""
import json
import logging
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Provider:
    name: str  # stored in catalysts.agreed_by
    kind: str  # "gemini" or "openai" (openai-compatible chat completions)
    key_setting: str
    model_setting: str
    interval_setting: str  # min seconds between calls, per provider
    base_url: str = ""

    @property
    def api_key(self) -> str:
        return getattr(settings, self.key_setting)

    @property
    def model(self) -> str:
        return getattr(settings, self.model_setting)

    @property
    def min_interval(self) -> float:
        return getattr(settings, self.interval_setting)


# order matters: when models agree, the first provider's wording is stored
PROVIDERS = [
    Provider("gemini", "gemini", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MIN_INTERVAL_SECONDS"),
]


def enabled_providers() -> list[Provider]:
    return [p for p in PROVIDERS if p.api_key]


def missing_key_message() -> str:
    return f"no LLM API key is set ({', '.join(p.key_setting for p in PROVIDERS)})"


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


def _openai_schema(schema: dict) -> dict:
    # strict json_schema mode: nullable becomes a ["x", "null"] type, objects allow no extra keys
    out = {k: v for k, v in schema.items() if k != "nullable"}
    if schema.get("nullable"):
        out["type"] = [schema["type"], "null"]
    if "properties" in schema:
        out["properties"] = {name: _openai_schema(prop) for name, prop in schema["properties"].items()}
        out["additionalProperties"] = False
    if "items" in schema:
        out["items"] = _openai_schema(schema["items"])
    return out


_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}


def validate(value: Any, schema: dict, path: str = "$") -> None:
    """check a reply against the json-schema subset callers use; raises LLMError"""
    if value is None:
        if schema.get("nullable"):
            return
        raise LLMError(f"invalid reply: {path} is null")
    expected = _TYPES.get(schema.get("type"))
    if expected and not isinstance(value, expected):
        raise LLMError(f"invalid reply: {path} is not {schema['type']}")
    if "enum" in schema and value not in schema["enum"]:
        raise LLMError(f"invalid reply: {path} = {str(value)[:50]!r} is not allowed")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise LLMError(f"invalid reply: {path}.{key} is missing")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}")
    elif isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")


def _raise_for_status(provider: Provider, resp: httpx.Response) -> None:
    if resp.status_code == 200:
        return
    try:
        error = resp.json().get("error", {})
    except ValueError:
        error =   {}
    if not isinstance(error, dict):
        error = {"message": str(error)}
    message = f"{provider.name} {resp.status_code}: {error.get('message', resp.text[:200])}"
    if resp.status_code == 429 or error.get("status") == "RESOURCE_EXHAUSTED":
        raise LLMRateLimitError(message)
    if resp.status_code == 503:
        raise LLMOverloadedError(message)
    raise LLMError(message)  # e.g. 413: this filing is too long for the provider's token limit


def _parse(provider: Provider, text: str, schema: dict) -> Any:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LLMError(f"{provider.name} reply is not valid json: {text[:200]}") from exc
    validate(data, schema)
    return data


async def _post(provider: Provider, url: str, body: dict, headers: dict, timeout: float) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMError(f"{provider.name} request failed: {exc}") from exc
    _raise_for_status(provider, resp)
    return resp


async def _gemini(provider: Provider, system: str, prompt: str, schema: dict, timeout: float) -> str:
    body ={
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(schema),
        },
    }
    url = GEMINI_URL.format(model=provider.model)
    data = (await _post(provider, url, body, {"x-goog-api-key": provider.api_key}, timeout)).json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "no candidates")
        raise LLMError(f"gemini returned no answer ({reason})")
    return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))


async def _openai_compatible(provider: Provider, system: str, prompt: str, schema: dict, timeout: float) -> str:
    body = {
        "model": provider.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "reply", "strict": True, "schema": _openai_schema(schema)},
        },
    }
    headers = {"Authorization": f"Bearer {provider.api_key}"}
    try:
        data = (await _post(provider, f"{provider.base_url}/chat/completions", body, headers, timeout)).json()
        return data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"{provider.name} returned an unexpected response") from exc


async def generate_json(system: str, prompt: str, schema: dict, provider: str = "gemini",
                        timeout: float = 120.0) -> Any:
    """
    run one prompt on one provider and return the parsed json reply, checked against `schema`
    (json-schema style: type, properties, items, enum, nullable, required).
    raises LLMRateLimitError on 429 / quota errors, LLMOverloadedError on 503 and LLMError
    on anything else, including a reply that doesn't match the schema.
    """
    p = next((p for p in PROVIDERS if p.name == provider), None)
    if p is None:
        raise LLMError(f"unknown llm provider: {provider}")
    if not p.api_key:
        raise LLMError(f"{p.key_setting} is not set")
    call = _gemini if p.kind == "gemini" else _openai_compatible
    return _parse(p, await call(p, system, prompt, schema, timeout), schema)
