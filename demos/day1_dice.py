"""Day 1 of ninada: day1_dice.py.

Smallest possible demo of the loop: one hand-written tool, no framework
scaffolding, so the user/assistant/tool/assistant transcript is visible end
to end.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ninada import provider
from ninada.loop import run_loop


class RollDice:
    """A tool that rolls `count` six-sided dice and reports the results."""

    spec = {"schema": {
        "name": "roll_dice",
        "description": "Roll count six-sided dice",
        "parameters": {
            "type": "object",
            "properties": {"count": {"type": "string", "description": "How many dice"}},
            "required": ["count"],
        },
    }}

    def run(self, count):
        rolls = [random.randint(1, 6) for _ in range(int(count))]
        return {"rolls": rolls, "total": sum(rolls)}


def on_event(kind, payload):
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result: {payload['result']}")


def before_tool(call):
    return None  # always allow


def main():
    task = "Roll 3 dice and tell me whether the total beats 10"
    print(f"user: {task}")
    messages = [{"role": "user", "text": task}]
    tools = {"roll_dice": RollDice()}
    run_loop(provider.DEFAULT_MODEL, "You are a helpful assistant.", messages,
              tools, on_event, before_tool)


if __name__ == "__main__":
    main()
