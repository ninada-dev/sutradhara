"""Shared degradation/memory logic used by both the Temporal and DBOS repros.

Kept as plain, testable functions with no framework dependency -- the
Temporal activities and DBOS steps are thin wrappers around exactly these
functions, so both systems run against identical behavior. That's what
makes the comparison fair: neither framework's wrapper changes what the
function does or doesn't preserve.
"""

import sqlite3

from gemini import complete

COMPACTION_PROMPT = (
    "Summarize the following incident/engineering document concisely, in "
    "your own words. Preserve every important technical detail: root "
    "causes, specific numbers, names, versions, paths, and action items. "
    "Be dense and factual. Do not simply copy the text verbatim -- "
    "genuinely summarize and compress it.\n\nDocument:\n{text}"
)


def compact_once(text):
    """One round of LLM summarization. Always returns a non-empty string."""
    result = complete(COMPACTION_PROMPT.format(text=text))
    # A real compaction step is written to never crash the pipeline over an
    # empty reply -- it falls back to the input, and "succeeds" either way.
    return result.strip() or text


def write_memory(db_path, run_id, round_num, content):
    """Durably persist one round's content to a SQLite 'memory' table."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memory "
        "(run_id TEXT, round INTEGER, content TEXT, chars INTEGER)"
    )
    conn.execute(
        "INSERT INTO memory (run_id, round, content, chars) VALUES (?, ?, ?, ?)",
        (run_id, round_num, content, len(content)),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "chars_written": len(content)}
