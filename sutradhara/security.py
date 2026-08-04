"""Day 2 of sutradhara: security.py.

Teaches the policy layer that plugs into loop.py's before_tool socket. Design
rule: deny patterns are a blocklist, not a sandbox — they catch known-bad
shell commands but are no substitute for resolve()'s path containment in
tools.py. They apply in every mode, including yolo, since yolo means "skip
approval," not "skip safety."
"""

import re

READ_TOOLS = {"read_file", "list_files", "grep"}

DENY_PATTERNS = [
    r"\brm\s+(-\S*(?:r\S*f|f\S*r)\S*|--recursive\s+--force|--force\s+--recursive)"
    r"\s+(/|~|\$HOME)(\s|$|/)",  # rm -rf (or -fr) targeting /, ~, or $HOME
    r"\bsudo\b",  # privilege escalation
    r"\bmkfs(\.\S+)?\b",  # reformatting a filesystem
    r"\bdd\s+if=",  # raw block-device writes
    r"\bcurl\s+\S+\s*\|\s*sh\b",  # fetch-and-execute
    r"\bgit\s+push\b[^\n]*--force\b",  # force-push can destroy remote history
    r">\s*/dev/sd[a-z]\d*\b",  # redirecting onto a raw disk device
]


class Policy:
    """Decides whether a tool call may run: mode gates it, approver can allow it in safe mode."""

    def __init__(self, mode="safe", approver=None):
        self.mode = mode
        self.approver = approver or (lambda call, reason: False)

    def check(self, call):
        """Return None to allow a call, or a reason string to block it.

        Order matters: deny patterns block even yolo mode, read tools and
        yolo mode skip approval entirely, read-only blocks anything left,
        and safe mode is the only path that consults the approver.
        """
        if call["name"] == "bash":
            command = call["args"].get("command", "")
            for pattern in DENY_PATTERNS:
                if re.search(pattern, command):
                    return f"command matches a denied pattern: {pattern}"

        if call["name"] in READ_TOOLS or self.mode == "yolo":
            return None

        if self.mode == "read-only":
            return f"read-only mode: {call['name']} is not a read tool"

        reason = f"approve {call['name']}({call['args']})?"
        if self.approver(call, reason):
            return None
        return f"not approved: {reason}"
