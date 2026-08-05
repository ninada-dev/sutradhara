"""Day 3 of sutradhara: day3_context.py.

Demo of the full day-3 stack: core_tools() and Policy from day 2, plus
context.compact() wired into run_loop's before_turn socket and a skills
catalog exposed through the system prompt and a use_skill tool. Usage:
    python3 demos/day3_context.py "<task>" [budget_tokens] [workdir]
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sutradhara import provider
from sutradhara.context import compact
from sutradhara.loop import run_loop
from sutradhara.security import Policy
from sutradhara.skills import catalog_prompt, read_skill
from sutradhara.tools import Tool, core_tools

BASE_SYSTEM = (
    "You are a careful coding assistant with file and shell tools scoped to a "
    "working directory. Use them to complete the task, verify your own work, "
    "and give a clear final answer."
)


def on_event(kind, payload):
    """Print each assistant reply and tool result, plus a note when compaction fires."""
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result: {payload['result']}")


def _use_skill_tool(workdir):
    """Build the use_skill Tool, closed over workdir, wrapping skills.read_skill."""
    def run(name):
        return read_skill(workdir, name)
    return Tool(
        name="use_skill",
        spec={"schema": {
            "name": "use_skill",
            "description": "Load a skill's full instructions by name",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Skill name"}},
                "required": ["name"],
            },
        }},
        run=run,
    )


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "List the files here."
    budget_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    workdir = sys.argv[3] if len(sys.argv) > 3 else tempfile.mkdtemp(prefix="sutradhara_day3_")
    print(f"scratch dir: {workdir}")
    print(f"user: {task}")

    tools = {t.name: t for t in core_tools(workdir)}
    skill_tool = _use_skill_tool(workdir)
    tools[skill_tool.name] = skill_tool

    system = BASE_SYSTEM
    skills_text = catalog_prompt(workdir)
    if skills_text:
        system += "\n\n" + skills_text

    def before_turn(msgs):
        before = len(msgs)
        result = compact(provider.DEFAULT_MODEL, msgs, budget_tokens)
        if len(result) < before:
            print(f"[compaction fired: {before} -> {len(result)} messages]")
        return result

    policy = Policy("yolo")
    messages = [{"role": "user", "text": task}]
    answer = run_loop(provider.DEFAULT_MODEL, system, messages, tools, on_event,
                       policy.check, before_turn=before_turn)
    print(f"final answer: {answer}")


if __name__ == "__main__":
    main()
