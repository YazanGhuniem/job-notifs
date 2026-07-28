"""Persistent state: which jobs we've already told the user about.

Committed back to the repo by CI each run, so it survives across runs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 120
# Alert once when a company has failed this many runs in a row, so a broken
# token surfaces instead of the company silently going dark.
FAILURE_ALERT_THRESHOLD = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path):
        self.path = path
        self.seen: dict[str, str] = {}
        self.failures: dict[str, int] = {}
        self.alerted: list[str] = []
        self._load()

    @property
    def is_bootstrap(self) -> bool:
        """True on the very first run — nothing has ever been recorded."""
        return not self.seen

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            # A corrupt state file would otherwise re-notify everything. Treat
            # it as a fresh bootstrap instead of blasting the user.
            return
        self.seen = data.get("seen", {})
        self.failures = data.get("failures", {})
        self.alerted = data.get("alerted", [])

    def has_seen(self, uid: str) -> bool:
        return uid in self.seen

    def mark_seen(self, uid: str) -> None:
        self.seen.setdefault(uid, _now())

    def record_success(self, company: str) -> None:
        self.failures.pop(company, None)
        if company in self.alerted:
            self.alerted.remove(company)

    def record_failure(self, company: str) -> bool:
        """Increment the failure count. Returns True if this warrants an alert."""
        self.failures[company] = self.failures.get(company, 0) + 1
        if (
            self.failures[company] >= FAILURE_ALERT_THRESHOLD
            and company not in self.alerted
        ):
            self.alerted.append(company)
            return True
        return False

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        keep = {}
        for uid, ts in self.seen.items():
            try:
                if datetime.fromisoformat(ts) >= cutoff:
                    keep[uid] = ts
            except ValueError:
                keep[uid] = ts
        self.seen = keep

    def save(self) -> None:
        self._prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _now(),
            "seen": self.seen,
            "failures": self.failures,
            "alerted": self.alerted,
        }
        self.path.write_text(json.dumps(payload, indent=1, sort_keys=True))
