"""Temporal workflows for the two-loop repro.

UpstreamCompactionWorkflow runs K rounds of summarization, feeding each
round's output into the next -- the "upstream loop." DownstreamMemoryWorkflow
takes upstream's final text and durably persists it -- the "downstream
loop." Both report COMPLETED regardless of what the content says, because
neither activity can fail on content: they can only fail on exceptions,
and nothing in this pipeline raises one.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import compact_activity, write_memory_activity

ACTIVITY_TIMEOUT = timedelta(minutes=2)


@workflow.defn
class UpstreamCompactionWorkflow:
    @workflow.run
    async def run(self, seed_text: str, rounds: int) -> list[str]:
        """Return the text after each round, so the caller can see the whole decay curve."""
        history = [seed_text]
        current = seed_text
        for _ in range(rounds):
            current = await workflow.execute_activity(
                compact_activity, current, start_to_close_timeout=ACTIVITY_TIMEOUT
            )
            history.append(current)
        return history


@workflow.defn
class DownstreamMemoryWorkflow:
    @workflow.run
    async def run(self, db_path: str, run_id: str, round_num: int, content: str) -> dict:
        return await workflow.execute_activity(
            write_memory_activity,
            args=[db_path, run_id, round_num, content],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )
