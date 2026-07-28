"""Microsoft careers API.

NOTE: this endpoint could not be reached from the machine this was built on
(connection reset, almost certainly local egress filtering rather than a bad
URL). The shape below matches Microsoft's public search API. If it turns out
to be wrong in CI you'll get a "microsoft has failed N runs" Telegram alert
rather than silence.
"""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
PAGE = 20
MAX_PAGES = 15


def fetch(session, company: str, cfg: dict) -> list[Job]:
    jobs = []
    for page in range(1, MAX_PAGES + 1):
        r = session.get(
            API,
            params={
                "q": cfg.get("search", "intern"),
                "l": "en_us",
                "pg": page,
                "pgSz": PAGE,
                "o": "Recent",
                "flt": "true",
            },
            headers={"Referer": "https://jobs.careers.microsoft.com/"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        result = (r.json().get("operationResult") or {}).get("result") or {}
        batch = result.get("jobs") or []
        if not batch:
            break

        for j in batch:
            props = j.get("properties") or {}
            locs = props.get("locations") or []
            if props.get("primaryLocation"):
                locs = [props["primaryLocation"], *locs]
            jid = str(j.get("jobId", ""))
            jobs.append(
                Job(
                    company=company,
                    title=clean(j.get("title")),
                    url=f"https://jobs.careers.microsoft.com/global/en/job/{jid}",
                    job_id=jid,
                    location=" | ".join(dict.fromkeys(p for p in locs if p)),
                    department=props.get("profession") or props.get("discipline") or "",
                    posted_at=j.get("postingDate", ""),
                )
            )

        if page * PAGE >= result.get("totalJobs", 0):
            break
    return jobs
