"""Day 4 of sutradhara: harness.py.

Teaches composition: Harness wires provider, loop, tools, security, context,
memory, skills, sessions, and sub-agents into the one resumable object a CLI
or another program actually talks to. Design rule: children spawned by
spawn_agent are ephemeral (persist=False) — a child's session log must never
collide with or hijack the parent's --resume.
"""

import os

from . import context, memory, provider, session, skills
from .loop import run_loop
from .security import Policy
from .subagent import subagent_tool
from .tools import core_tools, tool


def _remember_tool(workdir):
    """Build the remember Tool, closed over workdir, wrapping memory.remember."""
    @tool("Save a durable note about this project for future conversations",
          note="The fact to remember")
    def remember(note):
        return memory.remember(workdir, note)
    return remember


def _use_skill_tool(workdir):
    """Build the use_skill Tool, closed over workdir, wrapping skills.read_skill."""
    @tool("Load a skill's full instructions by name", name="Skill name")
    def use_skill(name):
        return skills.read_skill(workdir, name)
    return use_skill


class Harness:
    """Composes the full week's stack into one resumable, sub-agent-capable agent."""

    def __init__(self, workdir=".", model=None, policy=None, extra_tools=None,
                 system_extra="", on_event=None, budget_tokens=600_000,
                 max_turns=120, session_path=None, enable_subagents=True,
                 persist=True, _depth=0):
        self.workdir = os.path.realpath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.model = model or os.environ.get("SUTRADHARA_MODEL") or provider.DEFAULT_MODEL
        self.policy = policy or Policy("yolo")
        self.on_event = on_event or (lambda kind, payload: None)
        self.budget_tokens = budget_tokens
        self.max_turns = max_turns
        self.persist = persist
        self.session_path = session_path
        self.messages = []

        self.tools = {t.name: t for t in core_tools(self.workdir)}
        self.tools["remember"] = _remember_tool(self.workdir)
        if skills.catalog_prompt(self.workdir):
            self.tools["use_skill"] = _use_skill_tool(self.workdir)
        if enable_subagents:
            def make_child(depth):
                return Harness(workdir=self.workdir, model=self.model, policy=self.policy,
                                enable_subagents=enable_subagents, persist=False, _depth=depth)
            self.tools["spawn_agent"] = subagent_tool(make_child, depth=_depth)
        if extra_tools:
            self.tools.update(extra_tools)

        extra = "\n\n".join(p for p in (skills.catalog_prompt(self.workdir), system_extra) if p)
        self.system = memory.build_system_prompt(self.workdir, extra=extra)

    def resume(self, path=None):
        """Load a prior session's messages (latest by default). Return True if loaded."""
        path = path or session.latest(self.workdir)
        if not path:
            return False
        self.messages = session.load(path)
        self.session_path = path
        return bool(self.messages)

    def run(self, task):
        """Run one task to completion, persisting every new message as it lands."""
        if self.persist and not self.session_path:
            self.session_path = session.new_session(self.workdir, label=task[:32])

        recorded = len(self.messages)
        self.messages.append({"role": "user", "text": task})
        recorded = self._flush(recorded)

        def before_turn(msgs):
            nonlocal recorded
            self.messages = msgs
            recorded = self._flush(recorded)
            self.messages = context.compact(self.model, self.messages, self.budget_tokens)
            recorded = min(recorded, len(self.messages))
            return self.messages

        answer = run_loop(self.model, self.system, self.messages, self.tools,
                           self.on_event, self.policy.check, max_turns=self.max_turns,
                           before_turn=before_turn)

        # before_turn only runs ahead of a model call, so the loop's very last
        # message — this exact shape, on every exit path — needs an explicit
        # flush here; nothing else observes it.
        self.messages.append({"role": "assistant", "text": answer, "tool_calls": []})
        self._flush(recorded)

        return answer

    def _flush(self, recorded):
        """Persist self.messages[recorded:] to the session file; return the new watermark."""
        if self.session_path:
            for msg in self.messages[recorded:]:
                session.append(self.session_path, msg)
        return len(self.messages)
