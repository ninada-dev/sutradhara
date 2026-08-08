"""The ground truth for the two-loop demo.

SEED_DOCUMENT is what the upstream (compaction) loop starts from. FACTS is
the independent checklist used to grade what survives -- it is never seen by
the upstream or downstream loop, and it is not used by Temporal or DBOS in
any way. It exists purely so a script outside both systems can answer the
question neither system asks: is the content still correct?

Checks are substring/keyword based on purpose: a paraphrase that keeps the
identifying detail (the number, the name, the path) should still count as
"survived." Only the loss or corruption of the specific fact should count
against it -- that keeps the test honest to what summarization actually
does (rephrase freely, drop details silently), not a rigid wording match.
"""

SEED_DOCUMENT = """\
Incident Handoff: checkout-api degraded performance, 2026-03-03

On 2026-03-03, the checkout-api service (instance i-0af29cd81b3) began
rejecting connections under normal load. On-call was Priya Nair, who was
paged at 02:14 IST and escalated to Marcus Chen, the engineer who had
deployed the previous release.

Root cause: the payments-gateway service was upgraded to v2.15.0 the day
before. The new connection-pooling logic in v2.15.0 does not release
connections back to the pool under high concurrency, so the pool exhausts
itself once utilization crosses roughly 92%. Because payments-gateway
listens on port 8443 and checkout-api depends on it synchronously for every
checkout request, the exhausted pool cascaded into checkout-api rejecting
requests too.

Marcus rolled payments-gateway back to v2.14.3, the last known-good version,
which resolved the incident. The rollback was applied by hand; the automated
deploy pipeline was not used, because the pipeline currently has no gate
that would have caught this regression.

Estimated revenue impact of the 47-minute outage: $42,000, based on average
checkout throughput during the affected window.

Do NOT re-enable the auto-scaling policy on payments-gateway until the
connection-pool leak in v2.15.0 is actually fixed and verified under load --
auto-scaling would only mask the leak by adding more leaking instances, and
was explicitly disabled for this reason after the incident.

The pool configuration lives at /etc/payments-gateway/pool-config.yaml, and
whoever picks up the fix for v2.15.0 should start by comparing that file's
max_connections setting against what the new pooling logic in v2.15.0
actually respects, since there is reason to believe it silently ignores the
configured limit rather than enforcing it.
"""


def _contains_any(text, *needles):
    lowered = text.lower()
    return any(n.lower() in lowered for n in needles)


FACTS = [
    {
        "id": "on_call_person",
        "description": "On-call contact was Priya Nair",
        "check": lambda text: _contains_any(text, "Priya"),
    },
    {
        "id": "escalation_person",
        "description": "Escalated to Marcus Chen",
        "check": lambda text: _contains_any(text, "Marcus"),
    },
    {
        "id": "service_instance_id",
        "description": "Affected instance was i-0af29cd81b3",
        "check": lambda text: _contains_any(text, "i-0af29cd81b3"),
    },
    {
        "id": "bad_version",
        "description": "Regression introduced in v2.15.0",
        "check": lambda text: _contains_any(text, "2.15.0", "v2.15.0"),
    },
    {
        "id": "rollback_version",
        "description": "Rolled back to v2.14.3",
        "check": lambda text: _contains_any(text, "2.14.3", "v2.14.3"),
    },
    {
        "id": "port_number",
        "description": "payments-gateway listens on port 8443",
        "check": lambda text: _contains_any(text, "8443"),
    },
    {
        "id": "utilization_threshold",
        "description": "Pool exhausts around 92% utilization",
        "check": lambda text: _contains_any(text, "92%", "92 percent"),
    },
    {
        "id": "revenue_impact",
        "description": "Estimated impact was $42,000",
        "check": lambda text: _contains_any(text, "$42,000", "42,000", "42000"),
    },
    {
        "id": "config_path",
        "description": "Pool config is at /etc/payments-gateway/pool-config.yaml",
        "check": lambda text: _contains_any(text, "pool-config.yaml", "/etc/payments-gateway"),
    },
    {
        "id": "no_autoscale_constraint",
        "description": "Explicit instruction: do not re-enable auto-scaling",
        "check": lambda text: _contains_any(text, "auto-scal") and _contains_any(text, "not", "don't", "do not"),
    },
    {
        "id": "manual_rollback",
        "description": "Rollback was manual; deploy pipeline lacks a regression gate",
        "check": lambda text: _contains_any(text, "pipeline") and _contains_any(text, "manual", "by hand", "no gate", "lacks"),
    },
    {
        "id": "incident_date",
        "description": "Incident occurred 2026-03-03",
        "check": lambda text: _contains_any(text, "2026-03-03", "March 3"),
    },
]


def score(text):
    """Return (survived_count, total, [ids that were lost])."""
    lost = [f["id"] for f in FACTS if not f["check"](text)]
    return len(FACTS) - len(lost), len(FACTS), lost
