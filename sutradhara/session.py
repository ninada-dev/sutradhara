"""sutradhara: session.py.

Teaches durable sessions: every message is appended to a JSONL file the
instant it happens, so a crash mid-run loses at most one in-flight tool call.
Design rule: load() always hands back a conversation that satisfies the
tool-call/response pairing rule — a torn session gets repaired, not just
detected.
"""

import json
import os
import re
import time

SESSION_DIR = ".sutradhara/sessions"


def new_session(workdir, label="session"):
    """Create the session directory and return a fresh, unique session file path."""
    root = os.path.join(workdir, SESSION_DIR)
    os.makedirs(root, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", label).strip("-")[:40] or "session"
    return os.path.join(root, f"{int(time.time())}-{slug}.jsonl")


def append(path, message):
    """Append one message to the session file as a single JSON line."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def load(path):
    """Parse a session file, repairing any tool calls a crash left unanswered."""
    messages = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                break  # torn tail from a mid-write crash: stop, keep what parsed
    return _repair(messages)


def latest(workdir):
    """Return the newest session file's path, or None if there isn't one yet."""
    root = os.path.join(workdir, SESSION_DIR)
    if not os.path.isdir(root):
        return None
    sessions = sorted(f for f in os.listdir(root) if f.endswith(".jsonl"))
    return os.path.join(root, sessions[-1]) if sessions else None


def _repair(messages):
    """Synthesize results for any tool_calls a crash left unanswered."""
    last_assistant = None
    for i, m in enumerate(messages):
        if m["role"] == "assistant":
            last_assistant = i
    if last_assistant is None:
        return messages

    calls = messages[last_assistant].get("tool_calls", [])
    answered = sum(1 for m in messages[last_assistant + 1:] if m["role"] == "tool")
    for call in calls[answered:]:
        messages.append({
            "role": "tool",
            "name": call["name"],
            "text": "Interrupted before this ran (process restarted).",
        })
    return messages
