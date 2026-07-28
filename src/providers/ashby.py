from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def fetch(session, company: str, cfg: dict) -> list[Job]:
    r = session.get(API.format(token=cfg["token"]), timeout=TIMEOUT)
    r.raise_for_status()

    jobs = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue

        locs = [j.get("location") or ""]
        locs += [s.get("location", "") for s in (j.get("secondaryLocations") or [])]
        # Ashby gives a structured country — far more reliable than parsing the
        # free-text location, so append it to the string the filter sees.
        addr = (j.get("address") or {}).get("postalAddress") or {}
        country = addr.get("addressCountry", "")
        if country:
            locs.append(country)
        if j.get("isRemote"):
            locs.append("Remote")

        jobs.append(
            Job(
                company=company,
                title=clean(j.get("title")),
                url=j.get("jobUrl") or j.get("applyUrl", ""),
                job_id=str(j.get("id", "")),
                location=" | ".join(dict.fromkeys(p for p in locs if p)),
                department=j.get("department") or j.get("team") or "",
                posted_at=j.get("publishedAt", ""),
            )
        )
    return jobs
