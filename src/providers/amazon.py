"""Amazon (also covers AWS, Amazon Robotics, Audible, Twitch subsidiaries).

Custom endpoint, no ATS. Server-side query is narrowed to intern-ish terms
because the full board is >30k reqs.
"""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://www.amazon.jobs/en/search.json"
PAGE = 100
MAX_PAGES = 18
# Amazon's search tokenizer is odd: "internship" returns ~1500 US hits while
# "intern" returns ~36. Query several terms and union the results.
QUERIES = ("internship", "intern", "co-op")


def fetch(session, company: str, cfg: dict) -> list[Job]:
    seen: dict[str, Job] = {}

    for query in QUERIES:
        offset = 0
        for _ in range(MAX_PAGES):
            r = session.get(
                API,
                params={
                    "base_query": query,
                    "result_limit": PAGE,
                    "offset": offset,
                    # This is the param that actually filters to the US;
                    # `country=USA` silently narrows results to ~36.
                    "normalized_country_code[]": "USA",
                    "sort": "recent",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("jobs") or []
            if not batch:
                break

            for j in batch:
                jid = str(j.get("id_icims") or j.get("id") or "")
                if not jid or jid in seen:
                    continue
                seen[jid] = Job(
                    company=company,
                    title=clean(j.get("title")),
                    url="https://www.amazon.jobs" + (j.get("job_path") or ""),
                    job_id=jid,
                    location=j.get("normalized_location")
                    or j.get("location")
                    or j.get("country_code", ""),
                    department=j.get("job_category") or j.get("job_family") or "",
                    posted_at=j.get("posted_date", ""),
                )

            offset += PAGE
            if offset >= data.get("hits", 0):
                break

    return list(seen.values())
