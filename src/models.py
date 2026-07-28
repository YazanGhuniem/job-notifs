"""Normalized job representation shared by every ATS provider."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Job:
    company: str
    title: str
    url: str
    job_id: str
    location: str = ""
    department: str = ""
    posted_at: str = ""
    # Extra text (description snippet, team, etc.) used only for filtering,
    # never shown in notifications.
    raw_text: str = field(default="", repr=False)

    @property
    def uid(self) -> str:
        """Stable identity for dedupe.

        Keyed on the ATS job id rather than the title so that a company
        rewording a posting doesn't re-notify.
        """
        return hashlib.sha1(
            f"{self.company.lower()}|{self.job_id}".encode()
        ).hexdigest()[:16]

    @property
    def haystack(self) -> str:
        return f"{self.title} {self.department} {self.raw_text}".lower()
