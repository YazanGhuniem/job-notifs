"""Internship notifier — fetch, filter, alert.

    python -m src.main --dry-run                    # no messages sent
    python -m src.main --dry-run --show-rejected    # filter tuning
    python -m src.main --company anthropic
    python -m src.main --test-notify
    python -m src.main                              # real run
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
from pathlib import Path

import yaml

from .filters import Filters
from .models import Job
from .notify import Telegram, send_matches
from .providers import REGISTRY
from .providers.base import make_session
from .state import State

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "config" / "companies.yaml"
FILTERS = ROOT / "config" / "filters.yaml"
STATE = ROOT / "state" / "seen.json"
WORKERS = 8


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def fetch_company(session, name: str, cfg: dict) -> tuple[str, list[Job], str]:
    """Returns (name, jobs, error). Never raises — one dead board must not
    take down the whole run."""
    try:
        provider = REGISTRY.get(cfg.get("ats", ""))
        if provider is None:
            return name, [], f"unknown ats '{cfg.get('ats')}'"
        return name, provider(session, cfg.get("name", name), cfg), ""
    except Exception as e:  # noqa: BLE001 - deliberate catch-all
        return name, [], f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="internship-notifier")
    ap.add_argument("--dry-run", action="store_true", help="don't send or save")
    ap.add_argument("--show-rejected", action="store_true",
                    help="print near-miss internships and why they failed")
    ap.add_argument("--company", help="only check this company key")
    ap.add_argument("--test-notify", action="store_true",
                    help="send a test Telegram message and exit")
    ap.add_argument("--bootstrap", action="store_true",
                    help="force: mark everything seen without alerting")
    args = ap.parse_args()

    tg = Telegram()

    if args.test_notify:
        tg.send("✅ <b>Internship notifier</b>\nTelegram is wired up correctly.")
        print("sent")
        return 0

    companies = load_yaml(COMPANIES).get("companies", {})
    companies = {k: v for k, v in companies.items() if v.get("enabled", True)}
    if args.company:
        if args.company not in companies:
            print(f"unknown company '{args.company}'. known: "
                  f"{', '.join(sorted(companies))}")
            return 1
        companies = {args.company: companies[args.company]}

    filters = Filters(load_yaml(FILTERS))
    state = State(STATE)
    bootstrap = args.bootstrap or state.is_bootstrap

    session = make_session()
    all_jobs: list[Job] = []
    errors: list[tuple[str, str]] = []

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [
            pool.submit(fetch_company, session, name, cfg)
            for name, cfg in companies.items()
        ]
        for fut in cf.as_completed(futures):
            name, jobs, err = fut.result()
            if err:
                errors.append((name, err))
                print(f"  ✗ {name}: {err}", file=sys.stderr)
            else:
                all_jobs.extend(jobs)
                print(f"  ✓ {name}: {len(jobs)} postings")

    print(f"\nfetched {len(all_jobs)} postings from "
          f"{len(companies) - len(errors)}/{len(companies)} companies")

    # Display name -> whether the company only hires in the US.
    us_only = {
        cfg.get("name", key): cfg.get("assume_us", False)
        for key, cfg in companies.items()
    }

    matches, rejected = [], []
    for job in all_jobs:
        v = filters.evaluate(job, assume_us=us_only.get(job.company, False))
        if v.ok:
            matches.append((job, v))
        elif args.show_rejected and v.reason != "not-an-internship":
            rejected.append((job, v))

    print(f"{len(matches)} match the CS/US internship filter")

    if args.show_rejected:
        print(f"\n--- rejected internships ({len(rejected)}) ---")
        for job, v in sorted(rejected, key=lambda x: x[1].reason):
            print(f"  [{v.reason:24}] {job.company:14} {job.title[:70]}"
                  f"  ({job.location[:40]})")

    new = [(j, v) for j, v in matches if not state.has_seen(j.uid)]
    new.sort(key=lambda x: (x[0].company, x[0].title))
    print(f"{len(new)} are new since last run")

    if args.dry_run:
        print("\n--- would notify ---")
        for job, v in new:
            phd = " [PhD]" if v.is_phd else ""
            print(f"  {job.company:14} {job.title[:72]}{phd}")
            print(f"  {'':14} {job.location[:60]}  {job.url}")
        print("\n(dry run — nothing sent, state not saved)")
        return 0

    if bootstrap:
        for job, _ in matches:
            state.mark_seen(job.uid)
        tg.send(
            "🤖 <b>Internship notifier is live.</b>\n"
            f"Watching <b>{len(companies)}</b> companies · "
            f"<b>{len(matches)}</b> open CS internships in the US right now.\n\n"
            "<i>These are your baseline — you'll only be pinged about postings "
            "that go up from here.</i>"
        )
        state.save()
        print("bootstrapped: baseline recorded, no per-job alerts sent")
        return 0

    sent = send_matches(tg, new, filters.max_alerts)
    for job, _ in new:
        state.mark_seen(job.uid)
    print(f"sent {sent} messages")

    # Health tracking: alert once when a board has been broken for a while.
    ok_names = {c for c in companies} - {n for n, _ in errors}
    for name in ok_names:
        state.record_success(name)
    for name, err in errors:
        if state.record_failure(name):
            tg.send(
                f"⚠️ <b>{name}</b> has failed {state.failures[name]} runs in a row.\n"
                f"<code>{err[:200]}</code>\n\n"
                "<i>Its job board endpoint probably moved. "
                "Run tools/discover.py to find the new one.</i>"
            )

    state.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
