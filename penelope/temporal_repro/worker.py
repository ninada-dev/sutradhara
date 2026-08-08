"""Starts a Temporal worker on task queue "penelope" for both workflows."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import compact_activity, write_memory_activity
from workflows import DownstreamMemoryWorkflow, UpstreamCompactionWorkflow

TASK_QUEUE = "penelope"


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[UpstreamCompactionWorkflow, DownstreamMemoryWorkflow],
        activities=[compact_activity, write_memory_activity],
    )
    print("worker started on task queue 'penelope'", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
