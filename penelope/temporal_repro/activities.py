"""Temporal activities: thin wrappers around pipeline.py's plain functions.

This is the entire surface Temporal has to judge these steps by: did the
activity return, or did it raise? It never sees the string that came back,
only that a string came back.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from temporalio import activity

from pipeline import compact_once, write_memory


@activity.defn
async def compact_activity(text: str) -> str:
    return compact_once(text)


@activity.defn
async def write_memory_activity(db_path: str, run_id: str, round_num: int, content: str) -> dict:
    return write_memory(db_path, run_id, round_num, content)
