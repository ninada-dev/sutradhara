"""Day 1 of ninada: provider.py.

Teaches the wire boundary between a neutral, storage-friendly message format
and the Gemini REST API. Design rule: nothing above this module should ever
touch Gemini's JSON shape directly — complete() is the only door in or out.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-flash-lite"


def api_key():
    """Return the configured API key, checking ODYSSEUS_API_KEY then GEMINI_API_KEY."""
    key = os.environ.get("ODYSSEUS_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key set. Export ODYSSEUS_API_KEY or GEMINI_API_KEY."
        )
    return key


def _to_wire(messages):
    """Translate neutral messages into Gemini `contents`.

    Tool call signatures are opaque tokens Gemini issued with the original
    call; they must be echoed back verbatim as thoughtSignature or Gemini 3
    rejects the follow-up turn.
    """
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": msg["text"]}]})
        elif role == "assistant":
            parts = []
            if msg.get("text"):
                parts.append({"text": msg["text"]})
            for call in msg.get("tool_calls", []):
                part = {"functionCall": {"name": call["name"], "args": call["args"]}}
                if call.get("signature"):
                    part["thoughtSignature"] = call["signature"]
                parts.append(part)
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            contents.append({
                "role": "user",
                "parts": [{"functionResponse": {
                    "name": msg["name"],
                    "response": {"result": msg["text"]},
                }}],
            })
    return contents


def _from_wire(data):
    """Parse a Gemini response body into the neutral {text, tool_calls, usage} shape."""
    text = ""
    tool_calls = []
    candidate = data.get("candidates", [{}])[0]
    for part in candidate.get("content", {}).get("parts", []):
        if "text" in part and not part.get("thought"):
            text += part["text"]
        elif "functionCall" in part:
            call = part["functionCall"]
            tool_calls.append({
                "name": call["name"],
                "args": call.get("args", {}),
                "signature": part.get("thoughtSignature"),
            })
    usage_meta = data.get("usageMetadata", {})
    usage = {
        "input": usage_meta.get("promptTokenCount", 0),
        "output": usage_meta.get("candidatesTokenCount", 0),
    }
    return {"text": text, "tool_calls": tool_calls, "usage": usage}


def complete(model, system, messages, tools):
    """Run one non-streaming completion and return {text, tool_calls, usage}."""
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _to_wire(messages),
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 65536},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [t["schema"] for t in tools]}]
    url = f"{API_ROOT}/{model}:generateContent?key={api_key()}"
    return _from_wire(_post(url, body))


def _post(url, body, retries=5):
    """POST JSON with retry on transient errors (429/500/502/503, URLError, timeout)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
