from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch(session, company: str, cfg: dict) -> list[Job]:
    r = session.get(API.format(token=cfg["token"]), timeout=TIMEOUT)
    r.raise_for_status()

    jobs = []
    for j in r.json():
        cats = j.get("categories") or {}
        locs = list(cats.get("allLocations") or [])
        if cats.get("location"):
            locs.insert(0, cats["location"])
        # Lever exposes an ISO country code; expand US/CA so the location
        # filter's text matching can use it.
        code = j.get("country") or ""
        if code:
            locs.append({"US": "United States", "CA": "Canada"}.get(code, code))

        jobs.append(
            Job(
                company=company,
                title=clean(j.get("text")),
                url=j.get("hostedUrl") or j.get("applyUrl", ""),
                job_id=str(j.get("id", "")),
                location=" | ".join(dict.fromkeys(p for p in locs if p)),
                department=cats.get("team") or cats.get("department") or "",
                posted_at=str(j.get("createdAt", "")),
                raw_text=cats.get("commitment") or "",
            )
        )
    return jobs
