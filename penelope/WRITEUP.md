# The two-loop failure demo: the gap is real

**Verdict up front:** the gap is real, and reproduced live on two independent,
real durable-execution systems (Temporal and DBOS, both actually running,
not mocked). Both report unconditional success on every step, across two
separate runs on two separate backends, while a specific safety-critical
fact — the name of the person originally paged for the incident — silently
and completely disappears from the record by the second round of a
six-round summarization loop, and never comes back. Neither system has any
mechanism that could have caught this, by design, not by omission.

No existing tool was found that catches it. If you know of one, that's a
more valuable result than this writeup — say so and I'll test it.

## The claim being tested

Durable-execution frameworks (Temporal, DBOS, and the category they define)
guarantee that a step of work *runs to completion* — it survives process
crashes, it retries on exception, its result is durably checkpointed so a
restart doesn't redo it. They say nothing about whether the *value* a step
produced was any good. If a pipeline of steps can each individually
"succeed" while the information flowing through the pipeline silently rots,
that's a real gap these systems cannot see into, by construction — and
whatever fills that gap (this is apparently what Penelope is for) is not
redundant with what Temporal or DBOS already do.

## Why this exact mechanism, not a contrived one

The degradation mechanism is repeated LLM summarization: an "upstream loop"
that takes a document, summarizes it, then summarizes that summary, six
times over. This is not a toy chosen to make the point easy — it is the
literal shape of a real agent's context-compaction loop (a long-running
agent has to periodically compress its own history to stay under a token
budget, and every implementation of that does exactly this: summarize,
then re-summarize the summary on the next compaction). The summarization
prompt used here is a genuinely well-intentioned one, structurally
identical to what a careful engineer would write:

> Summarize the following incident/engineering document concisely, in your
> own words. Preserve every important technical detail: root causes,
> specific numbers, names, versions, paths, and action items. Be dense and
> factual. Do not simply copy the text verbatim — genuinely summarize and
> compress it.

Nothing about this prompt is sabotaged to force a failure. The failure
emerges from the compounding effect of applying a reasonable operation six
times, which is exactly the real-world scenario (a long agent session,
compacted repeatedly) that motivates the whole exercise.

## Methodology

**Seed document:** a one-page incident handoff doc (`facts.py`) containing
12 explicit, independently checkable facts of different kinds — a name, a
second name, an instance ID, two version numbers, a port, a percentage
threshold, a dollar figure, a file path, a negative constraint ("do NOT
re-enable X"), a causal/procedural fact, and a date. Deliberately not a
bullet list (which an LLM can preserve trivially because it *looks* like a
checklist) — it's prose, the way a real handoff doc reads.

**The two loops:**
1. **Upstream** — 6 rounds of the summarization prompt above, each round
   consuming the previous round's output. Every round calls a real Gemini
   model (`gemini-3.1-flash-lite`) over the network and returns whatever
   text comes back. No round can fail on content; it can only fail on an
   exception (network error, empty API key, etc.), and none of those
   occurred in the runs reported here.
2. **Downstream** — takes the final round's text and writes it as a row
   into a SQLite "memory" table (`pipeline.write_memory`), simulating a
   durable agent-memory store. This step also cannot fail on content —
   writing a syntactically valid but semantically hollowed-out string is
   still a successful write.

**The check that matters lives outside both systems.** `facts.py` is never
seen by either loop. It's a plain Python script, run manually after the
fact, that greps the final stored content for each of the 12 facts'
identifying details (a name, a number, a specific string — matched loosely
enough that a paraphrase that keeps the actual fact still counts as
survived; only the loss of the specific detail counts against it). Neither
Temporal nor DBOS has any equivalent of this step in their guarantee model.

**Both loops were run on two independent real backends**, not simulated:
- A real `temporal server start-dev` instance (embedded SQLite persistence,
  the same server binary used in production, just single-node).
- A real DBOS installation backed by a real local PostgreSQL 16 instance —
  DBOS applied 47 of its own schema migrations to that database on first
  launch, and its workflow status was read directly out of
  `dbos.workflow_status`, not through any SDK convenience layer.

## What each system's guarantee actually is

**Temporal.** A workflow's execution is an event-sourced history (visible
directly via `temporal workflow show`): `ActivityTaskScheduled` →
`ActivityTaskStarted` → `ActivityTaskCompleted`, once per activity
invocation, replayed deterministically from that log if a worker crashes
and reconnects. An activity is retried according to its `RetryPolicy` *if
and only if it raises an exception* (confirmed directly in this repro: a
real misconfiguration — the worker started without its API key — produced
exactly this behavior, retrying with exponential backoff until the
underlying cause was fixed). Once an activity function returns a value
without raising, Temporal marks it `ActivityTaskCompleted`, durably records
whatever was returned, and moves on. There is no step in this model where
Temporal inspects the *returned value* for correctness — doing so would
require Temporal to understand the semantics of every possible workload,
which is explicitly not its job. Success, in Temporal's model, means "the
function returned."

**DBOS.** Structurally the same guarantee, different mechanism: workflow
and step executions are recorded in a Postgres-backed operation log
(`dbos.workflow_status`, `dbos.operation_outputs`), so a crashed process can
resume a workflow without re-running already-completed steps (this is what
`@DBOS.step(retries_allowed=True)` is protecting: idempotent replay against
that log, not output validation). A step is retried up to `max_attempts`
*on exception*. Once a step returns, its result is persisted to Postgres
and the workflow status is written as `SUCCESS`. Again: nothing in this
model reads the returned string and asks whether it's still correct.

Both frameworks are, in this specific sense, doing exactly what they say
they do, and doing it correctly. That's the point — this isn't a bug in
either system. It's a category of failure their guarantee model was never
designed to address, and can't be, without becoming a fundamentally
different (and far more invasive, workload-aware) kind of system.

## Results

Fact-survival count per round, independently scored by `facts.py`,
identical on both backends:

| Round | Temporal (facts survived / 12) | DBOS (facts survived / 12) | Chars (Temporal / DBOS) |
|---|---|---|---|
| 0 (seed) | 12/12 | 12/12 | 1780 / 1780 |
| 1 | 10/12 | 10/12 | 1116 / 1169 |
| 2 | 9/12 | 9/12 | 919 / 942 |
| 3 | 9/12 | 9/12 | 892 / 902 |
| 4 | 9/12 | 9/12 | 875 / 819 |
| 5 | 9/12 | 9/12 | 841 / 839 |
| 6 (final, written to memory) | 9/12 | 9/12 | 857 / 789 |

**Both systems' own status reporting, for the exact same runs:**

```
$ temporal workflow describe --workflow-id penelope-upstream-ca7e0d1c
status: WORKFLOW_EXECUTION_STATUS_COMPLETED
historyLength: 41        # 6 rounds x (Scheduled/Started/Completed + task events), zero retries, zero failures

$ psql -d penelope -c "SELECT workflow_uuid, status, name FROM dbos.workflow_status ..."
 a6bc9fab-...  | SUCCESS | downstream_memory_workflow
 bbc02528-...  | SUCCESS | upstream_compaction_workflow
```

**The clean, unambiguous finding:** `on_call_person` (the fact that Priya
Nair was the original on-call contact, paged at 02:14 IST) is present in
round 0, absent from round 1 onward, on *both* backends, in *both*
independent runs. By the version of the document that gets written into
durable memory, the only human named anywhere in it is Marcus (who did the
rollback) — the person who first responded to the incident has been
silently erased from the institutional record, and both Temporal and DBOS
recorded that write as an unqualified success.

**A second, more interesting finding, found on inspection rather than by
the mechanical checker:** the `no_autoscale_constraint` fact (the original
document's explicit "do NOT re-enable auto-scaling until the leak is fixed
— auto-scaling would only mask it") is flagged lost by the keyword checker
in every degraded round, but reading the actual final text shows the
*directive survives* ("Disable auto-scaling until a fix is verified") —
what's actually happening is subtler and arguably worse: **the stated
*reason* for the directive silently drifted.** The DBOS run's final text
gives the reason as "to ensure leak metrics remain visible" — a plausible,
fluent, but different rationale than the original ("would mask the leak by
adding more leaking instances"). The action survived; the causal
justification for the action was quietly replaced with something else that
sounds equally authoritative. No keyword-presence check catches this,
because the words are all still there — this is corruption, not deletion,
and it's the harder version of the problem: a downstream consumer (human
or agent) reading only the final memory has no signal that the *reasoning*
it's relying on isn't the original reasoning at all.

`manual_rollback` (the fact that the rollback was applied by hand because
the deploy pipeline currently has no regression gate) was genuinely lost in
both runs — replaced by a forward-looking "implement CI/CD gates"
recommendation that doesn't restate why that gap currently exists.

## Honesty about the method

- The fact checker (`facts.py`) is a blunt, substring-based instrument by
  design — lenient enough that a paraphrase which keeps the actual detail
  still counts as survived. It is not perfect, as the `no_autoscale_constraint`
  case shows: the mechanical count says "lost" where a human reading says
  "the action survived, the reasoning didn't." I'm reporting that
  discrepancy rather than tuning the checker after the fact to make the
  numbers cleaner — the `on_call_person` result alone, which has zero
  ambiguity, is sufficient to support the claim.
- Six rounds and 12 facts is a small, singular run, not a statistical
  study. The value of this repro is that it's real (real models, real
  Temporal, real Postgres-backed DBOS) and reproducible (`git clone`, two
  commands), not that it's a large-sample result. Anyone doubting the
  finding can rerun `temporal_repro/run_repro.py` or `dbos_repro/app.py`
  directly.
- I did not find a tool that catches this. I looked for one honestly (that
  was the actual instruction) rather than only looking hard enough to
  confirm the hypothesis — but I did not exhaustively survey the
  observability/eval tooling ecosystem (e.g. LLM-specific eval harnesses
  bolted onto an orchestrator) before writing this up. If you already know
  of something in that category, it's worth checking against this exact
  repro before concluding the gap is unfilled.

## What this means for Penelope

The load-bearing assumption holds, on two independent real systems, with a
result clean enough that a single unambiguous fact (a person's name) is
sufficient evidence on its own, without needing the more ambiguous
secondary findings. Temporal and DBOS are correct and complete on their own
terms — step completion and idempotent replay — and neither one, by design,
has a mechanism that could have caught either the outright loss of
`on_call_person` or the silent rationale-substitution on the auto-scaling
directive. Whatever Penelope is meant to add on top of durable execution —
output-quality tracking across chained steps, not just step-completion
tracking — is not redundant with what these systems already do.

## Reproducing this

```
penelope/
  facts.py              # seed document + independent fact checker (ground truth)
  gemini.py              # standalone Gemini client (not shared with sutradhara)
  pipeline.py            # the actual compact/write-memory logic, framework-agnostic
  temporal_repro/
    activities.py workflows.py worker.py run_repro.py
  dbos_repro/
    app.py
```

```bash
export ODYSSEUS_API_KEY=...          # or GEMINI_API_KEY
cd penelope && python3 -m venv .venv && source .venv/bin/activate
pip install temporalio dbos psycopg2-binary

# Temporal
temporal server start-dev &
(cd temporal_repro && python3 worker.py &)
cd temporal_repro && python3 run_repro.py

# DBOS (needs a local Postgres; see app.py's DB_URL)
cd dbos_repro && python3 app.py

# Independent check, either backend:
python3 -c "
import sqlite3
from facts import score
conn = sqlite3.connect('memory_temporal.db')  # or memory_dbos.db
content = conn.execute('SELECT content FROM memory ORDER BY round DESC LIMIT 1').fetchone()[0]
survived, total, lost = score(content)
print(f'{survived}/{total} facts survived; lost: {lost}')
"
```
