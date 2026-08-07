"""sutradhara: harness.py.

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
        """Run one task to completion, persisting every message the instant it lands.

        Persistence rides on_event, not before_turn: before_turn only fires
        once at the top of each turn, so a message appended mid-turn (an
        assistant's tool_calls, or a tool's result) would stay unwritten
        until the *next* turn's before_turn call — meaning a crash mid-tool
        could lose the whole turn, not just the interrupted call. on_event
        fires the instant each message is appended, so a kill -9 anywhere
        loses at most the just-started tool call, which session.py's
        repair() then reconstructs on resume.
        """
        if self.persist and not self.session_path:
            self.session_path = session.new_session(self.workdir, label=task[:32])

        user_message = {"role": "user", "text": task}
        self.messages.append(user_message)
        self._persist(user_message)

        def before_turn(msgs):
            self.messages = context.compact(self.model, msgs, self.budget_tokens)
            return self.messages

        def on_event(kind, payload):
            if kind == "assistant":
                self._persist({"role": "assistant", "text": payload["text"],
                                "tool_calls": payload["tool_calls"]})
            elif kind == "tool_end":
                call = payload["call"]
                self._persist({"role": "tool", "name": call["name"],
                                "text": str(payload["result"])})
            self.on_event(kind, payload)

        return run_loop(self.model, self.system, self.messages, self.tools,
                         on_event, self.policy.check, max_turns=self.max_turns,
                         before_turn=before_turn)

    def _persist(self, message):
        """Durably append one message to the session file, if persistence is on."""
        if self.session_path:
            session.append(self.session_path, message)
