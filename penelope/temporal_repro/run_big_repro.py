"""Large-scale (~200-fact) version of run_repro.py, against the same live
Temporal server/worker. Logs exactly what happens at every round: which
specific facts newly vanished (or, if it happens, reappeared) compared to
the round before, not just a cumulative count.
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from temporalio.client import Client

from big_facts import FACTS, SEED_DOCUMENT, score
from workflows import DownstreamMemoryWorkflow, UpstreamCompactionWorkflow

TASK_QUEUE = "penelope"
ROUNDS = 10
DB_PATH = str(Path(__file__).resolve().parent.parent / "memory_temporal_big.db")


async def main():
    client = await Client.connect("localhost:7233")
    run_id = uuid.uuid4().hex[:8]

    print(f"=== upstream: {ROUNDS} rounds over {len(FACTS)} facts (run {run_id}) ===", flush=True)
    upstream_handle = await client.start_workflow(
        UpstreamCompactionWorkflow.run,
        args=[SEED_DOCUMENT, ROUNDS],
        id=f"penelope-big-upstream-{run_id}",
        task_queue=TASK_QUEUE,
    )
    history = await upstream_handle.result()
    upstream_desc = await upstream_handle.describe()
    print(f"upstream workflow status: {upstream_desc.status.name}", flush=True)

    final_text = history[-1]

    print(f"\n=== downstream: writing final round to durable memory ===", flush=True)
    downstream_handle = await client.start_workflow(
        DownstreamMemoryWorkflow.run,
        args=[DB_PATH, run_id, ROUNDS, final_text],
        id=f"penelope-big-downstream-{run_id}",
        task_queue=TASK_QUEUE,
    )
    write_result = await downstream_handle.result()
    downstream_desc = await downstream_handle.describe()
    print(f"downstream workflow status: {downstream_desc.status.name}", flush=True)
    print(f"downstream activity result: {write_result}", flush=True)

    print(f"\n=== per-round detail ===", flush=True)
    prev_lost = set()
    log_lines = []
    for i, text in enumerate(history):
        s, t, lost = score(text)
        lost_set = set(lost)
        newly_lost = sorted(lost_set - prev_lost)
        newly_regained = sorted(prev_lost - lost_set)
        pct = 100 * s / t
        line = f"round {i:2d}: {s:3d}/{t} survived ({pct:5.1f}%)  chars={len(text):5d}"
        if newly_lost:
            line += f"  NEWLY LOST ({len(newly_lost)}): {newly_lost}"
        if newly_regained:
            line += f"  REGAINED ({len(newly_regained)}): {newly_regained}"
        print(line, flush=True)
        log_lines.append(line)
        prev_lost = lost_set

    out_path = Path(__file__).resolve().parent.parent / f"big_temporal_history_{run_id}.txt"
    with open(out_path, "w") as f:
        for i, text in enumerate(history):
            f.write(f"--- round {i} ({len(text)} chars) ---\n{text}\n\n")

    log_path = Path(__file__).resolve().parent.parent / f"big_temporal_roundlog_{run_id}.txt"
    with open(log_path, "w") as f:
        f.write("\n".join(log_lines) + "\n")

    print(f"\nfull round-by-round text saved to {out_path}", flush=True)
    print(f"per-round log saved to {log_path}", flush=True)
    print(f"run_id={run_id}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
