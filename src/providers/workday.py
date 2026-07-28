"""Workday tenants (Nvidia, Salesforce, many enterprises).

The only provider needing POST + pagination. Config needs:
    tenant: nvidia
    host:   nvidia.wd5.myworkdayjobs.com
    site:   NVIDIAExternalCareerSite
"""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

PAGE = 20  # Workday caps limit at 20 regardless of what you ask for.
MAX_PAGES = 25


def fetch(session, company: str, cfg: dict) -> list[Job]:
    host, tenant, site = cfg["host"], cfg["tenant"], cfg["site"]
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    # Searching server-side for "intern" keeps us from paging through tens of
    # thousands of unrelated reqs. The real filter still runs locally.
    searches = cfg.get("search") or ["intern", "co-op", "internship"]
    if isinstance(searches, str):
        searches = [searches]

    jobs: dict[str, Job] = {}

    for search in searches:
        offset, total = 0, None
        for _ in range(MAX_PAGES):
            r = session.post(
                api,
                json={
                    "appliedFacets": {},
                    "limit": PAGE,
                    "offset": offset,
                    "searchText": search,
                },
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("jobPostings") or []
            if not batch:
                break
            # Workday only reports `total` on the first page — every later page
            # says 0. Latch it, or pagination stops after page one.
            if total is None:
                total = data.get("total") or 0

            for j in batch:
                path = j.get("externalPath", "")
                jid = (j.get("bulletFields") or [path])[0]
                if jid in jobs:
                    continue
                jobs[jid] = Job(
                    company=company,
                    title=clean(j.get("title")),
                    url=f"https://{host}/en-US/{site}{path}",
                    job_id=jid,
                    location=j.get("locationsText", ""),
                    posted_at=j.get("postedOn", ""),
                )

            offset += PAGE
            if len(batch) < PAGE or offset >= total:
                break

    return list(jobs.values())
