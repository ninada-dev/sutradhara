"""sutradhara: memory.py.

Teaches durable memory: a per-project markdown file the agent can append to,
folded back into every future system prompt for that directory. Design rule:
memory is plain text sitting in the project, not a database — readable,
editable, and deletable like any other file the agent already knows how to touch.
"""

import os
import platform

MEMORY_FILE = "SUTRADHARA.md"

_BASE_PROMPT = (
    "You are Sutradhara, a small sharp coding agent working inside one "
    "directory with the tools provided. Act, don't narrate. Inspect before "
    "assuming. Prefer edit_file for small changes. Verify after building by "
    "running or re-reading. Never repeat a failing call unchanged. When "
    "complete, reply with a short summary and stop calling tools."
)


def build_system_prompt(workdir, extra=""):
    """Assemble the system prompt: base rules, platform/workdir, project memory, extra."""
    root = os.path.realpath(workdir)
    sections = [_BASE_PROMPT, f"Platform: {platform.system()}. Working directory: {root}."]

    memory_path = os.path.join(root, MEMORY_FILE)
    if os.path.isfile(memory_path):
        with open(memory_path, encoding="utf-8") as f:
            sections.append(f"Project memory ({MEMORY_FILE}):\n{f.read()}")

    if extra:
        sections.append(extra)

    return "\n\n".join(sections)


def remember(workdir, note):
    """Append a note to the project's memory file, creating it if needed."""
    with open(os.path.join(workdir, MEMORY_FILE), "a", encoding="utf-8") as f:
        f.write(f"- {note}\n")
    return f"Remembered in {MEMORY_FILE}"
