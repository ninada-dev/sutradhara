"""Day 3 of sutradhara: context.py.

Teaches context compaction: past budget, summarize the old transcript and
keep the recent tail verbatim. The summary is just another user message —
the model never sees raw internal bookkeeping.
"""

CHARS_PER_TOKEN = 4
KEEP_RECENT = 6
_CLIP_CHARS = 400


def estimate_tokens(messages):
    """Cheap token estimate: total message character length divided by CHARS_PER_TOKEN."""
    return sum(len(str(m)) for m in messages) // CHARS_PER_TOKEN


def compact(model, messages, budget_tokens):
    """Summarize old messages into one dense recap, keeping the recent tail verbatim.

    Unchanged when already within budget or too short to bother summarizing.
    """
    if estimate_tokens(messages) <= budget_tokens or len(messages) <= KEEP_RECENT + 1:
        return messages

    from . import provider

    old, recent = messages[:-KEEP_RECENT], messages[-KEEP_RECENT:]
    # A tool result only makes sense right after the call that produced it;
    # starting the kept slice on one would be a dangling reference.
    while recent and recent[0]["role"] == "tool":
        recent = recent[1:]

    summary = provider.complete(
        model,
        "You compress agent transcripts. Preserve: the original task, every "
        "file created or edited and its purpose, key decisions, unresolved "
        "errors, and what remains to be done. Be dense and factual.",
        [{"role": "user", "text": _render(old)}],
        [],
    )["text"]

    return [{"role": "user", "text": f"[Conversation so far, compacted]\n{summary}"}] + recent


def _render(messages):
    """Flatten messages into a plain-text transcript for the summarizer to read."""
    lines = []
    for m in messages:
        if m["role"] == "tool":
            lines.append(f"tool[{m['name']}]: {m['text'][:_CLIP_CHARS]}")
            continue
        line = f"{m['role']}: {m.get('text', '')[:_CLIP_CHARS]}"
        for call in m.get("tool_calls", []):
            line += f" (calls {call['name']}({call['args']}))"
        lines.append(line)
    return "\n".join(lines)
