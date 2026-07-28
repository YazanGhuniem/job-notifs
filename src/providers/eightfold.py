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
    query = cfg.get("search", "intern")

    jobs, start = [], 0
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
            jobs.append(
                Job(
                    company=company,
                    title=clean(j.get("name") or j.get("posting_name")),
                    url=j.get("canonicalPositionUrl", ""),
                    job_id=str(j.get("ats_job_id") or j.get("id", "")),
                    location=" | ".join(p for p in locs if p),
                    department=j.get("department") or j.get("business_unit") or "",
                    posted_at=str(j.get("t_create", "")),
                )
            )

        start += PAGE
        if start >= data.get("count", 0):
            break
    return jobs
