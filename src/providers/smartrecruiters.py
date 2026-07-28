from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean

API = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
PAGE = 100
MAX_PAGES = 20


def fetch(session, company: str, cfg: dict) -> list[Job]:
    url = API.format(token=cfg["token"])
    jobs, offset = [], 0

    for _ in range(MAX_PAGES):
        r = session.get(url, params={"limit": PAGE, "offset": offset}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        batch = data.get("content") or []
        if not batch:
            break

        for j in batch:
            loc = j.get("location") or {}
            parts = [
                loc.get("fullLocation") or "",
                loc.get("city") or "",
                loc.get("region") or "",
                (loc.get("country") or "").upper(),
            ]
            if loc.get("remote"):
                parts.append("Remote")

            jobs.append(
                Job(
                    company=company,
                    title=clean(j.get("name")),
                    url=f"https://jobs.smartrecruiters.com/{cfg['token']}/{j.get('id')}",
                    job_id=str(j.get("id", "")),
                    location=" | ".join(dict.fromkeys(p for p in parts if p)),
                    department=(j.get("department") or {}).get("label", ""),
                    posted_at=j.get("releasedDate", ""),
                    raw_text=(j.get("typeOfEmployment") or {}).get("label", ""),
                )
            )

        offset += PAGE
        if offset >= data.get("totalFound", 0):
            break
    return jobs
