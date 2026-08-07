# sutradhara

The smallest agent harness that's still real: a full read/write/shell-tool
coding agent, with durable crash-safe sessions, sub-agent delegation, project
memory, and skills — fourteen files, about 900 lines, **zero third-party
dependencies**. Standard library only, Python 3.10+.

*sutradhara* (सूत्रधार, "thread-holder") is the term for the stage
director/narrator in classical Sanskrit theater — the one who holds the
threads that tie a performance together. That's what this package does for
an agent: it holds the threads between the model, its tools, and its memory.

## Setup

```bash
export ODYSSEUS_API_KEY=your-gemini-api-key   # or GEMINI_API_KEY
```

Optionally override the model:

```bash
export SUTRADHARA_MODEL=gemini-3.1-flash-lite
```

## Running it

Three ways to talk to it, all via `python3 -m sutradhara`:

**Interactive** — a REPL scoped to the current directory, `safe` policy by
default (every non-read tool call needs your `[y/N]` approval):

```bash
python3 -m sutradhara -d ./my-project
```

**Headless** — one task, no prompts, `yolo` policy by default (nothing needs
approval, only `security.py`'s deny patterns still block the truly
dangerous stuff):

```bash
python3 -m sutradhara -d ./my-project -p "Add a CHANGELOG.md summarizing recent commits"
```

**Resume** — pick a session back up after a crash, a Ctrl-C, or just closing
the terminal:

```bash
python3 -m sutradhara -d ./my-project --resume
```

Ctrl-D exits an interactive session cleanly. Ctrl-C interrupts whatever's
running — the session log is already safe on disk (every message is
persisted the instant it's produced, not batched) — and `--resume` picks up
exactly where it left off, with any interrupted tool call clearly marked.

## Day-by-day anatomy

| Day | Files | Teaches |
|---|---|---|
| 1 | `provider.py`, `loop.py` | The Gemini wire format and the turn-taking agent loop itself |
| 2 | `tools.py`, `security.py` | Turning functions into model-callable tools, sandboxed to a directory; a policy layer that gates what runs |
| 3 | `context.py`, `memory.py`, `skills.py` | Compacting a long transcript; a per-project memory file folded into the system prompt; on-demand skill loading |
| 4 | `session.py`, `subagent.py`, `harness.py`, `__init__.py` | Durable, crash-repairable sessions; delegating to depth-capped sub-agents; `Harness`, the class that composes everything above |
| 5 | `cli.py`, `fleet.py`, `__main__.py` | The terminal front door; running many `Harness` instances in parallel |

Every file opens with a module docstring naming what it teaches and the
design rule it embodies — that's the intended way to read this codebase,
top to bottom, one file at a time.

## Composing it: adding one extra tool

`Harness` takes `extra_tools`, so bolting on project-specific capability
doesn't touch any of the twelve core files:

```python
from sutradhara import Harness, tool

@tool("Look up the current price of a stock ticker", ticker="Stock ticker symbol")
def get_price(ticker):
    return fetch_price_from_somewhere(ticker)  # your own implementation

harness = Harness(
    workdir="./trading-notes",
    extra_tools={"get_price": get_price},
)
harness.run("What's AAPL trading at, and note it in prices.md")
```

`extra_tools` is merged in after `core_tools`, `remember`, `use_skill`, and
`spawn_agent` — so it can also override any of those by name if a project
needs different behavior for a built-in tool.

## Fleets

`run_fleet` runs many independent `Harness` instances concurrently — one
job's exception never sinks the others:

```python
from sutradhara import Harness, run_fleet

jobs = [
    {"name": "repo-a", "workdir": "./repo-a", "task": "Add type hints to utils.py"},
    {"name": "repo-b", "workdir": "./repo-b", "task": "Add type hints to utils.py"},
]
results = run_fleet(jobs, make_harness=lambda workdir: Harness(workdir=workdir))
for r in results:
    print(r["name"], r["ok"], r["report"])
```
