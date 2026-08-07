"""sutradhara: tools.py.

Teaches how a plain function becomes something the model can call: a JSON
schema plus a runnable. Design rule: every filesystem tool routes through one
resolve() choke point, so the sandbox boundary is enforced in exactly one
place instead of six.
"""

import fnmatch
import inspect
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

_IGNORE = {".git", "node_modules", "__pycache__", ".venv"}


@dataclass
class Tool:
    """A named tool: the JSON schema the provider sends the model, plus the runnable."""

    name: str
    spec: dict
    run: Callable


def tool(description, **params):
    """Decorator turning a plain function into a Tool.

    Every parameter is typed "string" in the schema on purpose — it keeps the
    contract simple and pushes any real parsing (ints, paths) into the tool
    body, where a bad value becomes a clear ERROR result instead of a schema
    rejection.
    """
    def decorate(fn):
        required = [
            name for name, p in inspect.signature(fn).parameters.items()
            if p.default is inspect.Parameter.empty
        ]
        spec = {"schema": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    param: {"type": "string", "description": text}
                    for param, text in params.items()
                },
                "required": required,
            },
        }}
        return Tool(name=fn.__name__, spec=spec, run=fn)
    return decorate


def core_tools(workdir):
    """Build the six filesystem/shell tools, sandboxed to the real path of workdir."""
    root = os.path.realpath(workdir)

    def resolve(path):
        """Map a tool-supplied path into workdir, refusing anything that escapes it."""
        full = os.path.realpath(os.path.join(root, path))
        if full != root and not full.startswith(root + os.sep):
            raise PermissionError(f"{path!r} escapes the working directory")
        return full

    def _walk():
        """Yield every file's path relative to root, skipping noise directories."""
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE]
            for name in filenames:
                full = os.path.join(dirpath, name)
                yield os.path.relpath(full, root).replace(os.sep, "/")

    @tool("Read a file's contents with line numbers",
          path="File path, relative to the working directory")
    def read_file(path):
        """Return the file's contents, numbered, truncated past 4000 lines."""
        with open(resolve(path), encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        total = len(lines)
        body = "\n".join(f"{i}\t{line}" for i, line in enumerate(lines[:4000], start=1))
        if total > 4000:
            body += f"\n... truncated, {total} lines total"
        return body

    @tool("Write content to a file, creating parent directories as needed",
          path="File path, relative to the working directory", content="Full file content")
    def write_file(path, content):
        """Create (or overwrite) a file and report how much was written."""
        full = resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"

    @tool("Replace one exact snippet occurrence in a file",
          path="File path, relative to the working directory",
          old="Exact snippet to find; must be unique in the file", new="Replacement text")
    def edit_file(path, old, new):
        """Replace old with new, refusing when old isn't uniquely present."""
        full = resolve(path)
        with open(full, encoding="utf-8") as f:
            content = f.read()
        count = content.count(old)
        # Uniqueness, not just presence, is required so an edit can never land
        # on the wrong one of several identical snippets.
        if count == 0:
            return "ERROR: snippet not found — read the file and copy it exactly"
        if count > 1:
            return f"ERROR: snippet appears {count} times — include more context to make it unique"
        with open(full, "w", encoding="utf-8") as f:
            f.write(content.replace(old, new, 1))
        return f"Edited {path}"

    @tool("Run a shell command in the working directory",
          command="The shell command to run", timeout="Timeout in seconds")
    def bash(command, timeout="120"):
        """Run command via the shell, capturing combined output up to a size cap."""
        seconds = int(timeout)
        try:
            proc = subprocess.run(command, shell=True, cwd=root, timeout=seconds,
                                   capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {seconds}s"
        output = proc.stdout + proc.stderr
        if len(output) > 12000:
            output = output[:6000] + "\n... truncated ...\n" + output[-6000:]
        if not output.strip():
            return f"(exit {proc.returncode}, no output)"
        return output

    @tool("List files matching a glob pattern",
          pattern="Glob pattern to match, e.g. **/*.py (default **/*)")
    def list_files(pattern="**/*"):
        """List up to 500 matching relative paths, sorted, tallying any overflow."""
        matches = sorted(
            rel for rel in _walk()
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(os.path.basename(rel), pattern)
        )
        lines = matches[:500]
        if len(matches) > 500:
            lines.append(f"... and {len(matches) - 500} more")
        return "\n".join(lines)

    @tool("Search file contents for a regular expression",
          regex="Regular expression to search for",
          pattern="Glob restricting which files are searched (default *)")
    def grep(regex, pattern="*"):
        """Search matching files line by line, capping at 200 hits."""
        rx = re.compile(regex)
        hits = []
        for rel in _walk():
            if not (fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(os.path.basename(rel), pattern)):
                continue
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if rx.search(line):
                            hits.append(f"{rel}:{lineno}: {line.rstrip(chr(10))[:200]}")
                            if len(hits) >= 200:
                                return "\n".join(hits)
            except OSError:
                continue
        return "\n".join(hits)

    return [read_file, write_file, edit_file, bash, list_files, grep]
