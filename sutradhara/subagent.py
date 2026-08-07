"""sutradhara: subagent.py.

Teaches delegation: a spawn_agent tool that hands a self-contained task to a
fresh Harness with its own clean context. Design rule: depth is capped so a
sub-agent can never recursively spawn its way into a runaway fan-out.
"""

from .tools import tool


def subagent_tool(make_harness, depth=0, max_depth=2):
    """Build the spawn_agent Tool, closed over a Harness factory and the current depth."""
    @tool(
        "Delegate a self-contained task to a fresh sub-agent with its own clean "
        "context. The child cannot see this conversation — only the task text "
        "you give it. Returns the child's final report.",
        task="The self-contained task to delegate",
    )
    def spawn_agent(task):
        if depth >= max_depth:
            return "ERROR: sub-agent depth limit reached; do this task yourself"
        child = make_harness(depth + 1)
        return child.run(task)

    return spawn_agent
