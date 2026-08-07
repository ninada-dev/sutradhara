"""Day 5 of sutradhara: fleet.py.

Teaches parallel composition: running many independent Harness instances at
once, e.g. one per repository or one per subtask. Design rule: one job's
exception never sinks the fleet — it becomes a result like any other, so the
caller always gets exactly one report per job, in the order the jobs came in.
"""

from concurrent.futures import ThreadPoolExecutor


def run_fleet(jobs, make_harness, max_workers=4):
    """Run each job's task on its own Harness concurrently.

    jobs is a list of {"name", "workdir", "task"}. make_harness(workdir)
    builds the Harness for that job — callers control policy, model, and
    tools this way. Returns one {"name", "ok", "report"} dict per job, in
    the same order the jobs were given, regardless of which finished first.
    """
    def run_one(job):
        try:
            harness = make_harness(job["workdir"])
            report = harness.run(job["task"])
            return {"name": job["name"], "ok": True, "report": report}
        except Exception as exc:
            return {"name": job["name"], "ok": False,
                    "report": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(run_one, jobs))
