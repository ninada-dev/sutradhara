"""Minimal, standalone Gemini client for the penelope repro.

Deliberately not importing sutradhara.provider -- penelope is a separate
project testing a separate claim, and shouldn't depend on the harness it's
partly inspired by. Same API key (ODYSSEUS_API_KEY / GEMINI_API_KEY), same
free-tier-accessible model, minimal wire handling: just enough to send a
prompt and get text back.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.1-flash-lite"


def _api_key():
    key = os.environ.get("ODYSSEUS_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No API key set. Export ODYSSEUS_API_KEY or GEMINI_API_KEY.")
    return key


def complete(prompt, retries=5):
    """Send one prompt, return the model's text response."""
    url = f"{API_ROOT}/{MODEL}:generateContent?key={_api_key()}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                parsed = json.loads(resp.read())
                parts = parsed["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode()[:300]}") from exc
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
