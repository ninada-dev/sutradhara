"""DBOS side of the two-loop repro: same pipeline.py functions, wrapped as
DBOS steps/workflows instead of Temporal activities/workflows, against a
real local Postgres instance. Whatever DBOS reports as this workflow's
status is DBOS's entire opinion of what happened -- like Temporal, it has
no visibility into the string a step returned, only whether it raised.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dbos import DBOS, DBOSConfig

from pipeline import compact_once, write_memory

DB_URL = "postgresql://sujeetjog@localhost:5433/penelope"
MEMORY_DB_PATH = str(Path(__file__).resolve().parent.parent / "memory_dbos.db")
ROUNDS = 6

config: DBOSConfig = {
    "name": "penelope-dbos",
    "system_database_url": DB_URL,
}
DBOS(config=config)


@DBOS.step(retries_allowed=True, max_attempts=3)
def compact_step(text: str) -> str:
    return compact_once(text)


@DBOS.step(retries_allowed=True, max_attempts=3)
def write_memory_step(db_path: str, run_id: str, round_num: int, content: str) -> dict:
    return write_memory(db_path, run_id, round_num, content)


@DBOS.workflow()
def upstream_compaction_workflow(seed_text: str, rounds: int) -> list[str]:
    history = [seed_text]
    current = seed_text
    for _ in range(rounds):
        current = compact_step(current)
        history.append(current)
    return history


@DBOS.workflow()
def downstream_memory_workflow(db_path: str, run_id: str, round_num: int, content: str) -> dict:
    return write_memory_step(db_path, run_id, round_num, content)


def main():
    DBOS.launch()

    run_id = uuid.uuid4().hex[:8]
    from facts import SEED_DOCUMENT

    print(f"=== upstream: {ROUNDS} rounds of compaction (run {run_id}) ===", flush=True)
    upstream_wf_id = f"penelope-dbos-upstream-{run_id}"
    history = upstream_compaction_workflow(SEED_DOCUMENT, ROUNDS)
    # DBOSConfig doesn't let us pass workflow_id directly to a plain call in
    # this SDK version, so ask DBOS for the status of whichever workflow ID
    # it assigned by listing recent workflows instead of forcing one.
    recent = DBOS.list_workflows(limit=5)
    upstream_status = next(
        (w.status for w in recent if w.name == "upstream_compaction_workflow"), "UNKNOWN"
    )
    print(f"upstream workflow status: {upstream_status}", flush=True)

    final_text = history[-1]

    print(f"\n=== downstream: writing final round to durable memory ===", flush=True)
    write_result = downstream_memory_workflow(MEMORY_DB_PATH, run_id, ROUNDS, final_text)
    recent = DBOS.list_workflows(limit=5)
    downstream_status = next(
        (w.status for w in recent if w.name == "downstream_memory_workflow"), "UNKNOWN"
    )
    print(f"downstream workflow status: {downstream_status}", flush=True)
    print(f"downstream step result: {write_result}", flush=True)

    out_path = Path(__file__).resolve().parent.parent / f"dbos_history_{run_id}.txt"
    with open(out_path, "w") as f:
        for i, text in enumerate(history):
            f.write(f"--- round {i} ({len(text)} chars) ---\n{text}\n\n")
    print(f"\nfull round-by-round text saved to {out_path}", flush=True)
    print(f"run_id={run_id}", flush=True)


if __name__ == "__main__":
    main()
