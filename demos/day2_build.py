"""Day 2 of sutradhara: day2_build.py.

Demo of the full day-2 stack: core_tools() giving the model a sandboxed
scratch directory, and security.Policy sitting in loop.py's before_tool
socket. Run with a task on the command line, e.g.:
    python3 demos/day2_build.py "Create fib.py with an iterative fib(n)..."
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sutradhara import provider
from sutradhara.loop import run_loop
from sutradhara.security import Policy
from sutradhara.tools import core_tools

SYSTEM = (
    "You are a careful coding assistant with file and shell tools scoped to a "
    "working directory. Use them to complete the task, verify your own work "
    "(e.g. by running code you write), and give a clear final answer."
)


def on_event(kind, payload):
    """Print each assistant reply and tool result as the loop runs."""
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result: {payload['result']}")


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "List the files here."
    workdir = tempfile.mkdtemp(prefix="sutradhara_day2_")
    print(f"scratch dir: {workdir}")
    print(f"user: {task}")

    tools = {t.name: t for t in core_tools(workdir)}
    policy = Policy("yolo")
    messages = [{"role": "user", "text": task}]
    answer = run_loop(provider.DEFAULT_MODEL, SYSTEM, messages, tools, on_event, policy.check)
    print(f"final answer: {answer}")


if __name__ == "__main__":
    main()
