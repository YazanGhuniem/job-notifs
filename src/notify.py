"""Telegram delivery."""

from __future__ import annotations

import html
import os
import time

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMIT = 4096


class Telegram:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> bool:
        if not self.configured:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set "
                "(see README step 1-2)."
            )
        r = requests.post(
            API.format(token=self.token),
            json={
                "chat_id": self.chat_id,
                "text": text[:LIMIT],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=25,
        )
        if r.status_code == 429:
            # Telegram tells us exactly how long to wait.
            wait = r.json().get("parameters", {}).get("retry_after", 5)
            time.sleep(wait + 1)
            return self.send(text)
        if not r.ok:
            print(f"  ! telegram {r.status_code}: {r.text[:200]}")
            return False
        return True


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def format_job(job, is_phd: bool = False) -> str:
    tag = " <b>[PhD]</b>" if is_phd else ""
    lines = [
        f"🚨 <b>{_esc(job.company)}</b>{tag}",
        f"<b>{_esc(job.title)}</b>",
    ]
    if job.location:
        loc = job.location if len(job.location) <= 90 else job.location[:87] + "…"
        lines.append(f"📍 {_esc(loc)}")
    if job.department:
        lines.append(f"🏷 {_esc(job.department)}")
    lines.append(f'\n<a href="{_esc(job.url)}">Apply →</a>')
    return "\n".join(lines)


def send_matches(tg: Telegram, matches: list[tuple], max_alerts: int) -> int:
    """matches: list of (Job, Verdict). Returns number of messages sent."""
    sent = 0
    for job, verdict in matches[:max_alerts]:
        if tg.send(format_job(job, verdict.is_phd)):
            sent += 1
        time.sleep(0.6)  # stay under Telegram's ~20 msg/min per-chat cap

    overflow = len(matches) - max_alerts
    if overflow > 0:
        extra = matches[max_alerts:]
        by_company: dict[str, int] = {}
        for job, _ in extra:
            by_company[job.company] = by_company.get(job.company, 0) + 1
        summary = ", ".join(f"{c} ({n})" for c, n in sorted(by_company.items()))
        tg.send(
            f"➕ <b>and {overflow} more new internships</b>\n{_esc(summary)}\n\n"
            "<i>Capped to avoid flooding — they're marked seen, so check the "
            "boards directly if you want them.</i>"
        )
        sent += 1
    return sent
