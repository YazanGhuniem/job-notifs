"""Google Careers.

Google exposes no public JSON API (the old careers.google.com/api/v3 is gone
and returns 404), but its results page is server-side rendered, so the listing
is parseable straight out of the HTML.

Markup notes — the CSS classes are obfuscated and WILL change eventually, but
these three anchors have been stable and are what we key on:
  - `<li class="lLd3Je">`                      one job card
  - `aria-label="Learn more about <title>"`    the title
  - `<span class="r0wTof...">`                 each office location

If Google reskins and this breaks, the run reports 0 postings for google and
you get a health alert after 5 runs rather than silence.
"""

from __future__ import annotations

import html
import re

from ..models import Job
from .base import TIMEOUT

BASE = "https://www.google.com/about/careers/applications/jobs/results"

# Google's own INTERN tag is narrow, so query a few phrasings too and union
# the results. Volume is small (tens of rows), so this stays cheap.
QUERIES = ("intern", "internship", "co-op", "student researcher", "apprentice")
MAX_PAGES = 6

# The "Learn more" anchor carries the href AND the title, which makes it a much
# better hook than the card container (whose class differs between the
# employment_type and q= result pages, and is sometimes only in the CSS).
ANCHOR_RE = re.compile(
    r'href="(jobs/results/(\d+)[^"]*)"[^>]*aria-label="Learn more about ([^"]+)"'
)
LOC_RE = re.compile(r'<span class="r0wTof[^"]*">([^<]+)</span>')
MORE_RE = re.compile(r"of (\d+) rows")


def _cards(page_html: str) -> list[Job]:
    """Locations render before their anchor, so each card's offices are the
    r0wTof spans sitting between the previous anchor and this one."""
    jobs, cursor = [], 0
    for m in ANCHOR_RE.finditer(page_html):
        locs = [
            html.unescape(x).lstrip("; ").strip()
            for x in LOC_RE.findall(page_html[cursor:m.start()])
        ]
        cursor = m.end()
        path = m.group(1).split("?")[0]
        jobs.append(
            Job(
                company="Google",
                title=html.unescape(m.group(3)).strip(),
                url=f"https://www.google.com/about/careers/applications/{path}",
                job_id=m.group(2),
                location=" | ".join(dict.fromkeys(locs)),
            )
        )
    return jobs


def fetch(session, company: str, cfg: dict) -> list[Job]:
    seen: dict[str, Job] = {}

    # The shared session sends Accept: application/json; this endpoint is HTML.
    headers = {"Accept": "text/html,application/xhtml+xml,*/*"}

    def crawl(params: dict) -> None:
        for page in range(1, MAX_PAGES + 1):
            r = session.get(BASE, params={**params, "page": page},
                            headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            found = _cards(r.text)
            for j in found:
                seen.setdefault(j.job_id, j)
            total = MORE_RE.search(r.text)
            if not found or (total and page * 20 >= int(total.group(1))):
                break

    crawl({"employment_type": "INTERN"})
    for q in QUERIES:
        crawl({"q": q})

    for j in seen.values():
        j.company = company
    return list(seen.values())
