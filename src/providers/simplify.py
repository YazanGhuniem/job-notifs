"""Community-maintained aggregator feed (SimplifyJobs internship lists).

This exists to cover the companies with no reachable job board of their own —
Google, Apple, Meta, Microsoft, Salesforce and friends. Their careers sites are
either client-rendered behind anti-bot measures (Meta), gated behind Apple ID
(Apple's sitemap), or simply gone (Microsoft's old API host). Rather than ship
four brittle scrapers that break silently, we read a feed that a large
community already keeps current.

Restricted to an explicit `only_companies` allowlist so it doesn't add hundreds
of employers you never asked about, and so it never double-reports a company
already covered by a direct provider.
"""

from __future__ import annotations

from ..models import Job
from .base import TIMEOUT, clean


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def fetch(session, company: str, cfg: dict) -> list[Job]:
    feeds = cfg.get("feeds") or []
    allow = {_norm(c) for c in (cfg.get("only_companies") or [])}

    jobs: dict[str, Job] = {}
    reached_any = False

    for url in feeds:
        r = session.get(url, timeout=TIMEOUT)
        # Next season's feed doesn't exist until they create the repo; a 404 is
        # expected there and must not fail the whole provider.
        if r.status_code == 404:
            continue
        r.raise_for_status()
        reached_any = True

        for row in r.json():
            if not row.get("active") or not row.get("is_visible", True):
                continue
            name = row.get("company_name") or ""
            if allow and _norm(name) not in allow:
                continue
            jid = str(row.get("id") or row.get("url") or "")
            if not jid or jid in jobs:
                continue

            jobs[jid] = Job(
                company=name,
                title=clean(row.get("title")),
                url=row.get("url") or "",
                job_id=jid,
                location=" | ".join(row.get("locations") or []),
                department=row.get("category") or "",
                posted_at=str(row.get("date_posted", "")),
                raw_text=" ".join(row.get("terms") or []),
            )

    if not reached_any:
        raise RuntimeError("no aggregator feed reachable")

    return list(jobs.values())
