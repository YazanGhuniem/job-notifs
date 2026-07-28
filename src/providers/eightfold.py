"""Eightfold AI job boards (Netflix, and a growing number of enterprises).

Config:
    host:   explore.jobs.netflix.net
    domain: netflix.com
"""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

PAGE = 100
MAX_PAGES = 10


def fetch(session, company: str, cfg: dict) -> list[Job]:
    host, domain = cfg["host"], cfg["domain"]
    api = f"https://{host}/api/apply/v2/jobs"
    # Several phrasings, so a title saying only "Co-Op" isn't missed by the
    # server-side search before our own filter ever sees it.
    queries = cfg.get("search") or ["intern", "co-op", "internship"]
    if isinstance(queries, str):
        queries = [queries]

    jobs: dict[str, Job] = {}

    for query in queries:
        start = 0
        for _ in range(MAX_PAGES):
            r = session.get(
                api,
                params={
                    "domain": domain,
                    "query": query,
                    "start": start,
                    "num": PAGE,
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("positions") or []
            if not batch:
                break

            for j in batch:
                locs = j.get("locations") or [j.get("location", "")]
                jid = str(j.get("ats_job_id") or j.get("id", ""))
                if jid in jobs:
                    continue
                jobs[jid] = Job(
                    company=company,
                    title=clean(j.get("name") or j.get("posting_name")),
                    url=j.get("canonicalPositionUrl", ""),
                    job_id=jid,
                    location=" | ".join(p for p in locs if p),
                    department=j.get("department") or j.get("business_unit") or "",
                    posted_at=str(j.get("t_create", "")),
                )

            start += PAGE
            if start >= data.get("count", 0):
                break

    return list(jobs.values())
