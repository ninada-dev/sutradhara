"""sutradhara: cli.py.

Teaches the front door: turning Harness into something you run from a
terminal, headless (-p) or interactive. Design rule: the CLI only prints and
asks — every real behavior (tools, policy, sessions) lives in Harness.
"""

import argparse
import sys

from .harness import Harness
from .security import Policy

_DIM, _RESET = "\033[2m", "\033[0m"


def _clip(value, limit=40):
    """Stringify and truncate a value so a tool-call line stays one line."""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _print_event(kind, payload):
    """Print assistant text plainly; each tool call as one line, its result dimmed under it."""
    if kind == "assistant":
        if payload["text"]:
            print(payload["text"])
        for call in payload["tool_calls"]:
            args = ", ".join(f"{k}={_clip(v)}" for k, v in call["args"].items())
            print(f"-> {call['name']}({args})")
    elif kind == "tool_end":
        result = str(payload["result"])
        print(f"{_DIM}{result.splitlines()[0] if result else ''}{_RESET}")


def _approve(call, reason):
    """Ask the user to approve a gated tool call; anything but 'y', including EOF, refuses."""
    try:
        return input(f"{reason} [y/N] ").strip().lower() == "y"
    except EOFError:
        return False


def _parse_args(argv):
    """Parse CLI arguments into an argparse.Namespace."""
    parser = argparse.ArgumentParser(prog="sutradhara")
    parser.add_argument("-p", "--prompt", help="Run one task headlessly and exit")
    parser.add_argument("-d", "--workdir", default=".", help="Working directory")
    parser.add_argument("-m", "--model", default=None, help="Override the model")
    parser.add_argument("--mode", choices=["safe", "yolo", "read-only"], default=None,
                         help="Policy mode (default: safe interactively, yolo with -p)")
    parser.add_argument("--resume", action="store_true", help="Resume the latest session")
    parser.add_argument("--max-turns", type=int, default=120, help="Turn cap")
    return parser.parse_args(argv)


def main(argv=None):
    """Entry point: dispatch to headless (-p) or interactive mode."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    mode = args.mode or ("yolo" if args.prompt else "safe")
    policy = Policy(mode, approver=_approve)

    harness = Harness(workdir=args.workdir, model=args.model, policy=policy,
                       on_event=_print_event, max_turns=args.max_turns)
    if args.resume:
        harness.resume()

    if args.prompt:
        harness.run(args.prompt)
        return 0

    return _interactive(harness, mode)


def _interactive(harness, mode):
    """Read-prompt-run until Ctrl-D; Ctrl-C interrupts one run without exiting."""
    print(f"sutradhara — model: {harness.model}  mode: {mode}  jail: {harness.workdir}")
    while True:
        try:
            task = input("> ")
        except EOFError:
            print()
            return 0
        if not task.strip():
            continue
        try:
            harness.run(task)
        except KeyboardInterrupt:
            print(f"\ninterrupted — session log is safe at {harness.session_path}; "
                  f"--resume continues it")
