"""A larger-scale version of facts.py: ~200 independently checkable facts
across ~16 incident reports, concatenated into one document, so the
degradation curve has real resolution instead of +/-8.3% per fact (n=12).

Generated programmatically from templates so the seed document and its
fact checklist are always in sync -- but each incident still varies its
phrasing (several sentence templates per field, chosen deterministically
per incident) so the document isn't a mechanical, trivially-preservable
checklist. It's still real prose an LLM has to actually parse to compress.
"""

import random

_R = random.Random(20260308)  # fixed seed: reproducible generation

_FIRST = ["Priya", "Marcus", "Elena", "Devon", "Aisha", "Tomas", "Ingrid", "Rahul",
          "Naomi", "Felix", "Sana", "Owen", "Yuki", "Carlos", "Freya", "Amir",
          "Lena", "Kwame", "Mira", "Bjorn", "Zara", "Nikolai", "Chidi", "Ines",
          "Soren", "Amara", "Dmitri", "Fatima", "Leif", "Priyanka", "Hassan", "Elin"]
_LAST = ["Nair", "Chen", "Rossi", "Okafor", "Larsen", "Petrov", "Silva", "Kaur",
         "Bergman", "Diallo", "Kimura", "Novak", "Haddad", "Lindgren", "Adeyemi", "Volkov"]

_SERVICES = ["checkout-api", "payments-gateway", "inventory-sync", "auth-broker",
             "search-index", "recommendation-engine", "notification-hub", "billing-service",
             "session-store", "media-transcoder", "shipping-calc", "fraud-scorer",
             "catalog-api", "cart-service", "loyalty-engine", "order-router"]

_CAUSES = ["connection-pool exhaustion", "an unbounded retry loop", "a memory leak in the cache layer",
           "disk space exhaustion on the write path", "a thundering-herd on cold start",
           "a missing index causing full table scans", "a deadlock under high concurrency",
           "a misconfigured circuit breaker staying permanently open"]

_OPEN_TEMPLATES = [
    "On {date}, the {service} service (instance {iid}) began {symptom}. On-call was "
    "{oncall}, paged at {time} {tz}, who escalated to {escalate}, the engineer who had "
    "shipped the previous release.",
    "{date}: {service} (instance {iid}) started {symptom}. {oncall} was on call and got "
    "paged at {time} {tz}; the incident was escalated to {escalate} shortly after.",
    "A {service} incident began on {date} (instance {iid}): {symptom}. {oncall} received "
    "the page at {time} {tz} and brought in {escalate} to help diagnose it.",
]

_CAUSE_TEMPLATES = [
    "Root cause was {cause} in version {bad_version}, which pushed pool/resource "
    "utilization past roughly {pct}% before things cascaded. {service} listens on port "
    "{port}, and downstream callers depend on it synchronously.",
    "The regression traced back to {cause}, introduced in {bad_version}; utilization "
    "crossed about {pct}% before the service degraded. {service} runs on port {port} and "
    "is a synchronous dependency for several other services.",
    "Investigation found {cause} as the root cause, present since {bad_version} shipped. "
    "The failure threshold was around {pct}% utilization. {service} is reachable on port "
    "{port}.",
]

_RESOLUTION_TEMPLATES = [
    "{escalate} rolled {service} back to {good_version}, the last known-good version, "
    "which resolved the incident. The rollback was applied by hand; the deploy pipeline "
    "was not used, since it currently has no gate that would have caught this regression.",
    "The fix was a manual rollback of {service} to {good_version}, performed by "
    "{escalate} directly rather than through the deploy pipeline -- there is currently no "
    "automated gate in that pipeline that would have flagged the regression beforehand.",
    "{escalate} manually reverted {service} to {good_version} outside the normal deploy "
    "pipeline, which resolved things; the pipeline still lacks any gate that would catch "
    "this class of regression automatically.",
]

_IMPACT_TEMPLATES = [
    "Estimated revenue impact of the outage was ${impact}, based on throughput during the "
    "affected window.",
    "The outage is estimated to have cost approximately ${impact} in lost revenue.",
    "Revenue impact was estimated at ${impact} for the duration of the incident.",
]

_CONSTRAINT_TEMPLATES = [
    "Do NOT re-enable auto-scaling on {service} until the underlying issue is fixed and "
    "verified under load -- auto-scaling would only mask the problem by adding more "
    "affected instances, and was explicitly disabled for this reason.",
    "Auto-scaling on {service} must stay off until this is properly fixed and load-tested "
    "-- turning it back on would just paper over the problem with more bad instances, "
    "which is exactly why it was disabled.",
    "{service}'s auto-scaling policy should remain disabled until the fix is verified "
    "under load; re-enabling it would only hide the underlying issue behind additional "
    "instances, which is why it was turned off in the first place.",
]

_PATH_TEMPLATES = [
    "The relevant configuration lives at {path}, and whoever picks up the permanent fix "
    "should check that file's settings against what {bad_version} actually respects, since "
    "there's reason to believe it silently ignores some of them.",
    "Configuration for this service is at {path}; the permanent fix should start by "
    "comparing that file against what {bad_version} actually enforces, which may not match "
    "what's configured.",
]


def _mkperson(used):
    while True:
        name = f"{_R.choice(_FIRST)} {_R.choice(_LAST)}"
        if name not in used:
            used.add(name)
            return name


def _gen_incident(i, used_names):
    oncall = _mkperson(used_names)
    escalate = _mkperson(used_names)
    service = _SERVICES[i % len(_SERVICES)]
    cause = _R.choice(_CAUSES)
    iid = f"i-{_R.randrange(0x10000000, 0xffffffff):08x}"
    bad_version = f"v{_R.randint(2,4)}.{_R.randint(0,20)}.{_R.randint(0,9)}"
    good_version = f"v{_R.randint(2,4)}.{_R.randint(0,20)}.{_R.randint(0,9)}"
    port = _R.choice([8443, 8080, 9443, 6379, 5432, 8888, 9200, 7000, 8001, 9090])
    pct = _R.choice([85, 88, 90, 92, 94, 95, 97])
    impact = f"{_R.randint(8, 95)},{_R.randint(0,9)}00"
    path = f"/etc/{service}/config.yaml"
    day = _R.randint(1, 27)
    month = _R.randint(1, 12)
    date = f"2026-{month:02d}-{day:02d}"
    time = f"{_R.randint(0,23):02d}:{_R.randint(0,59):02d}"
    tz = _R.choice(["IST", "UTC", "PST", "CET"])
    symptom = _R.choice(["rejecting connections under normal load", "returning elevated 5xx rates",
                          "timing out on a large fraction of requests", "silently dropping writes"])

    text = " ".join([
        _R.choice(_OPEN_TEMPLATES).format(date=date, service=service, iid=iid, symptom=symptom,
                                           oncall=oncall, time=time, tz=tz, escalate=escalate),
        _R.choice(_CAUSE_TEMPLATES).format(cause=cause, bad_version=bad_version, pct=pct,
                                            service=service, port=port),
        _R.choice(_RESOLUTION_TEMPLATES).format(escalate=escalate, service=service,
                                                  good_version=good_version),
        _R.choice(_IMPACT_TEMPLATES).format(impact=impact),
        _R.choice(_CONSTRAINT_TEMPLATES).format(service=service),
        _R.choice(_PATH_TEMPLATES).format(path=path, bad_version=bad_version),
    ])

    facts = [
        {"id": f"i{i}_oncall", "description": f"Incident {i}: on-call was {oncall}",
         "check": lambda t, v=oncall.split()[0]: v in t},
        {"id": f"i{i}_escalate", "description": f"Incident {i}: escalated to {escalate}",
         "check": lambda t, v=escalate.split()[0]: v in t},
        {"id": f"i{i}_instance", "description": f"Incident {i}: instance {iid}",
         "check": lambda t, v=iid: v in t},
        {"id": f"i{i}_bad_version", "description": f"Incident {i}: bad version {bad_version}",
         "check": lambda t, v=bad_version: v in t},
        {"id": f"i{i}_good_version", "description": f"Incident {i}: rollback version {good_version}",
         "check": lambda t, v=good_version: v in t},
        {"id": f"i{i}_port", "description": f"Incident {i}: port {port}",
         "check": lambda t, v=str(port): v in t},
        {"id": f"i{i}_pct", "description": f"Incident {i}: threshold {pct}%",
         "check": lambda t, v=f"{pct}%": v in t},
        {"id": f"i{i}_impact", "description": f"Incident {i}: impact ${impact}",
         "check": lambda t, v=impact: v in t},
        {"id": f"i{i}_path", "description": f"Incident {i}: config path {path}",
         "check": lambda t, v=path: v in t},
        {"id": f"i{i}_autoscale", "description": f"Incident {i}: auto-scale constraint on {service}",
         "check": lambda t, v=service: (v in t) and ("auto-scal" in t.lower())},
        {"id": f"i{i}_manual", "description": f"Incident {i}: rollback was manual, pipeline lacks gate",
         "check": lambda t: ("pipeline" in t.lower()) and
                  any(k in t.lower() for k in ["manual", "by hand", "no gate", "lacks", "n't use"])},
        {"id": f"i{i}_date", "description": f"Incident {i}: date {date}",
         "check": lambda t, v=date: v in t},
        {"id": f"i{i}_cause", "description": f"Incident {i}: root cause was {cause}",
         "check": lambda t, v=cause.split()[0].lower(): v in t.lower()},
    ]
    return text, facts


def _build(n_incidents=16):
    used_names = set()
    texts, all_facts = [], []
    for i in range(1, n_incidents + 1):
        text, facts = _gen_incident(i, used_names)
        texts.append(f"Incident {i}:\n{text}")
        all_facts.extend(facts)
    return "\n\n".join(texts), all_facts


SEED_DOCUMENT, FACTS = _build()


def score(text):
    lost = [f["id"] for f in FACTS if not f["check"](text)]
    return len(FACTS) - len(lost), len(FACTS), lost


if __name__ == "__main__":
    print(f"generated {len(FACTS)} facts across document of {len(SEED_DOCUMENT)} chars "
          f"(~{len(SEED_DOCUMENT.split())} words)")
    s, t, lost = score(SEED_DOCUMENT)
    print(f"self-check: {s}/{t} survive in the seed itself (should be {t}/{t})")
    if lost:
        print("unexpected misses:", lost)
