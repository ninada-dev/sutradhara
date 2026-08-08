"""Drives the two-loop repro against a real Temporal server and dumps its
own view of what happened -- workflow status only, nothing about content.
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from temporalio.client import Client

from facts import SEED_DOCUMENT
from workflows import DownstreamMemoryWorkflow, UpstreamCompactionWorkflow

TASK_QUEUE = "penelope"
ROUNDS = 6
DB_PATH = str(Path(__file__).resolve().parent.parent / "memory_temporal.db")


async def main():
    client = await Client.connect("localhost:7233")
    run_id = uuid.uuid4().hex[:8]

    print(f"=== upstream: {ROUNDS} rounds of compaction (run {run_id}) ===", flush=True)
    upstream_handle = await client.start_workflow(
        UpstreamCompactionWorkflow.run,
        args=[SEED_DOCUMENT, ROUNDS],
        id=f"penelope-upstream-{run_id}",
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
        id=f"penelope-downstream-{run_id}",
        task_queue=TASK_QUEUE,
    )
    write_result = await downstream_handle.result()
    downstream_desc = await downstream_handle.describe()
    print(f"downstream workflow status: {downstream_desc.status.name}", flush=True)
    print(f"downstream activity result: {write_result}", flush=True)

    out_path = Path(__file__).resolve().parent.parent / f"temporal_history_{run_id}.txt"
    with open(out_path, "w") as f:
        for i, text in enumerate(history):
            f.write(f"--- round {i} ({len(text)} chars) ---\n{text}\n\n")
    print(f"\nfull round-by-round text saved to {out_path}", flush=True)
    print(f"run_id={run_id}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
