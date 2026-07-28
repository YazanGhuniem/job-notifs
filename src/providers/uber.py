"""Uber's custom careers API."""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"
PAGE = 100
MAX_PAGES = 10


def _loc_str(loc: dict) -> str:
    if not loc:
        return ""
    parts = [loc.get("city"), loc.get("region"), loc.get("countryName")]
    return ", ".join(p for p in parts if p)


def fetch(session, company: str, cfg: dict) -> list[Job]:
    queries = cfg.get("search") or ["intern", "co-op", "internship"]
    if isinstance(queries, str):
        queries = [queries]

    jobs: dict[str, Job] = {}

    for query in queries:
        page = 0
        for _ in range(MAX_PAGES):
            r = session.post(
                API,
                json={"params": {"query": query}, "page": page, "limit": PAGE},
                # Uber rejects the request without this header, value unchecked.
                headers={"Content-Type": "application/json", "x-csrf-token": "x"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json().get("data") or {}
            batch = data.get("results") or []
            if not batch:
                break

            for j in batch:
                locs = [_loc_str(loc) for loc in (j.get("allLocations") or [])]
                if not locs:
                    locs = [_loc_str(j.get("location") or {})]
                jid = str(j.get("id", ""))
                if jid in jobs:
                    continue
                jobs[jid] = Job(
                    company=company,
                    title=clean(j.get("title")),
                    url=f"https://www.uber.com/global/en/careers/list/{jid}/",
                    job_id=jid,
                    location=" | ".join(p for p in locs if p),
                    department=j.get("department") or j.get("team") or "",
                    posted_at=j.get("creationDate", ""),
                )

            page += 1
            if len(batch) < PAGE:
                break

    return list(jobs.values())
