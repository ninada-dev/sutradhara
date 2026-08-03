"""Day 1 of sutradhara: loop.py.

Teaches the agent loop itself: call the model, run any tool calls it asked
for, feed results back, repeat. Design rule: a tool raising an exception is
data, not a crash — the loop's job is to keep going and report the failure
back to the model like any other tool result.
"""


def run_loop(model, system, messages, tools, on_event, before_tool,
             max_turns=80, before_turn=None):
    """Drive the assistant/tool exchange until the model stops calling tools.

    tools maps name -> Tool (.spec, .run(**kwargs)). before_tool(call) returns
    None to allow a call or a reason string to block it. before_turn, when
    given, is called with the message list before each model call and its
    return value replaces the list in place (unused today; day 3 plugs
    context compaction in here).
    """
    from . import provider

    specs = [t.spec for t in tools.values()]
    for _ in range(max_turns):
        if before_turn is not None:
            messages = before_turn(messages)
        reply = provider.complete(model, system, messages, specs)
        messages.append({
            "role": "assistant",
            "text": reply["text"],
            "tool_calls": reply["tool_calls"],
        })
        on_event("assistant", reply)

        if not reply["tool_calls"]:
            return reply["text"]

        for call in reply["tool_calls"]:
            result = _run_tool(call, tools, before_tool, on_event)
            messages.append({"role": "tool", "name": call["name"], "text": str(result)})

    messages.append({"role": "user", "text": "Turn limit reached; wrap up now."})
    reply = provider.complete(model, system, messages, [])
    messages.append({"role": "assistant", "text": reply["text"], "tool_calls": []})
    return reply["text"]


def _run_tool(call, tools, before_tool, on_event):
    """Execute one tool call, turning unknown tools and exceptions into result text."""
    on_event("tool_start", call)
    block_reason = before_tool(call)
    if block_reason is not None:
        result = f"BLOCKED: {block_reason}"
    elif call["name"] not in tools:
        result = f"ERROR: unknown tool {call['name']}"
    else:
        try:
            result = tools[call["name"]].run(**call["args"])
        except Exception as exc:
            result = f"ERROR: {type(exc).__name__}: {exc}"
    on_event("tool_end", {"call": call, "result": result})
    return result
