#!/usr/bin/env python3
"""Find which ATS a company uses, and its token.

    python tools/discover.py Rippling
    python tools/discover.py "Hugging Face" Anduril Retool

Probes Greenhouse / Lever / Ashby / SmartRecruiters with common slug variants
and prints a ready-to-paste companies.yaml block for whatever answers.
"""

from __future__ import annotations

import concurrent.futures as cf
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from src.providers.base import make_session  # noqa: E402

PROBES = {
    "greenhouse": (
        "https://boards-api.greenhouse.io/v1/boards/{t}/jobs",
        lambda d: len(d.get("jobs", [])) if isinstance(d, dict) else 0,
    ),
    "lever": (
        "https://api.lever.co/v0/postings/{t}?mode=json",
        lambda d: len(d) if isinstance(d, list) else 0,
    ),
    "ashby": (
        "https://api.ashbyhq.com/posting-api/job-board/{t}",
        lambda d: len(d.get("jobs", [])) if isinstance(d, dict) else 0,
    ),
    "smartrecruiters": (
        "https://api.smartrecruiters.com/v1/companies/{t}/postings?limit=1",
        lambda d: d.get("totalFound", 0) if isinstance(d, dict) else 0,
    ),
}


def slugs(name: str) -> list[str]:
    base = name.strip()
    low = re.sub(r"[^a-z0-9]+", "", base.lower())
    hyph = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    cands = [
        low, hyph, base, base.lower(),
        f"{low}inc", f"{low}ai", f"{low}hq", f"{low}usa", f"{low}labs",
        f"{low}technologies", f"{low}tech", f"{low}careers",
        f"{hyph}-inc", f"{low}1",
    ]
    return list(dict.fromkeys(c for c in cands if c))


def probe(session, ats: str, token: str):
    url, counter = PROBES[ats]
    try:
        r = session.get(url.format(t=token), timeout=12)
        if r.status_code != 200:
            return None
        n = counter(r.json())
        return (ats, token, n) if n and n > 0 else None
    except Exception:
        return None


def discover(session, name: str):
    tasks = [(ats, t) for t in slugs(name) for ats in PROBES]
    hits = []
    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(probe, session, a, t): (a, t) for a, t in tasks}
        for fut in cf.as_completed(futures):
            res = fut.result()
            if res:
                hits.append(res)
    # Most postings wins — the real board, not a same-named shell account.
    return sorted(hits, key=lambda x: -x[2])


def main() -> int:
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        return 1

    session = make_session()
    resolved, unresolved = [], []

    for name in names:
        hits = discover(session, name)
        if not hits:
            unresolved.append(name)
            print(f"✗ {name}: no public ATS found", file=sys.stderr)
            continue
        ats, token, n = hits[0]
        resolved.append((name, ats, token, n))
        others = "".join(f"  (also: {a}/{t} n={c})" for a, t, c in hits[1:3])
        print(f"✓ {name}: {ats}/{token}  n={n}{others}", file=sys.stderr)

    if resolved:
        print("\n# --- paste into config/companies.yaml ---")
        for name, ats, token, _ in resolved:
            key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            print(f"  {key}:")
            print(f"    name: {name}")
            print(f"    ats: {ats}")
            print(f"    token: {token}")

    if unresolved:
        print("\n# unresolved — likely Workday/iCIMS/Eightfold or a custom board:")
        for name in unresolved:
            print(f"#   {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
