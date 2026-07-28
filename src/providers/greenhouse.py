from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch(session, company: str, cfg: dict) -> list[Job]:
    # No ?content=true: the full HTML body of every posting is megabytes per
    # company and title/department is enough to filter on.
    r = session.get(API.format(token=cfg["token"]), timeout=TIMEOUT)
    r.raise_for_status()

    jobs = []
    for j in r.json().get("jobs", []):
        offices = j.get("offices") or []
        # offices[].location carries the country ("Sydney, New South Wales,
        # Australia"); location.name often doesn't.
        loc_parts = [o.get("location") or o.get("name") or "" for o in offices]
        loc = " | ".join(p for p in loc_parts if p)
        if not loc:
            loc = (j.get("location") or {}).get("name", "")

        depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []))

        jobs.append(
            Job(
                company=company,
                title=clean(j.get("title")),
                url=j.get("absolute_url", ""),
                job_id=str(j.get("id", "")),
                location=loc,
                department=depts,
                posted_at=j.get("first_published") or j.get("updated_at") or "",
            )
        )
    return jobs
