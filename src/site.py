"""Generate the static page published to GitHub Pages.

Writes docs/jobs.json (data) and docs/index.html (viewer). The workflow commits
both every run, so the page tracks the notifier automatically.

Posted dates arrive in five different shapes across the providers — ISO
strings, epoch seconds, epoch milliseconds, "December 3, 2025", and Workday's
useless "Posted 30+ Days Ago" — so everything is normalised to YYYY-MM-DD here,
falling back to the date we first saw the job when the provider gives us
nothing usable.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august september "
        "october november december".split()
    )
}

_TEXT_DATE = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})")


def parse_date(raw: str) -> str:
    """Best-effort normalise a provider date to YYYY-MM-DD. '' if unknown."""
    if not raw:
        return ""
    raw = str(raw).strip()

    if raw.isdigit():
        n = int(raw)
        # Epoch milliseconds vs seconds.
        if n > 10_000_000_000:
            n //= 1000
        try:
            return datetime.fromtimestamp(n, timezone.utc).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return ""

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        pass

    m = _TEXT_DATE.search(raw)
    if m and m.group(1).lower() in MONTHS:
        try:
            return datetime(
                int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))
            ).strftime("%Y-%m-%d")
        except ValueError:
            return ""

    # e.g. Workday's "Posted 30+ Days Ago" — no date recoverable.
    return ""


def build(matches: list[tuple], state, out_dir: Path) -> int:
    """matches: list of (Job, Verdict). Returns number of jobs written."""
    rows = []
    for job, verdict in matches:
        first_seen = (state.seen.get(job.uid) or "")[:10]
        rows.append(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "posted": parse_date(job.posted_at) or first_seen,
                "found": first_seen,
                "phd": verdict.is_phd,
            }
        )

    # Newest first; jobs with no date sink to the bottom rather than the top.
    rows.sort(key=lambda r: (r["posted"] or "0000-00-00", r["company"]), reverse=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "count": len(rows),
        "jobs": rows,
    }
    (out_dir / "jobs.json").write_text(json.dumps(payload, indent=1))
    (out_dir / "index.html").write_text(PAGE)
    (out_dir / ".nojekyll").write_text("")
    return len(rows)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internships</title>
<style>
  :root {
    --bg:#fff; --fg:#111; --muted:#666; --line:#e5e5e5;
    --accent:#0b5fff; --chip:#f4f4f5;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0e0e10; --fg:#f2f2f3; --muted:#9a9aa2; --line:#26262b;
            --accent:#7aa2ff; --chip:#1a1a1f; }
  }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px 16px 64px; background:var(--bg); color:var(--fg);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:900px; margin:0 auto; }
  h1 { font-size:22px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:18px; }
  input { width:100%; padding:10px 12px; font-size:15px; margin-bottom:16px;
          background:var(--bg); color:var(--fg);
          border:1px solid var(--line); border-radius:8px; }
  input:focus { outline:2px solid var(--accent); outline-offset:-1px; }
  ul { list-style:none; margin:0; padding:0; }
  li { padding:12px 0; border-bottom:1px solid var(--line); display:flex;
       gap:12px; align-items:baseline; }
  .date { color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums;
          white-space:nowrap; min-width:74px; }
  .main { flex:1; min-width:0; }
  a { color:var(--accent); text-decoration:none; font-weight:500; }
  a:hover { text-decoration:underline; }
  .meta { color:var(--muted); font-size:13px; margin-top:2px; }
  .co { color:var(--fg); font-weight:600; }
  .phd { font-size:11px; background:var(--chip); color:var(--muted);
         padding:1px 6px; border-radius:99px; margin-left:6px; }
  .empty { color:var(--muted); padding:32px 0; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Open CS internships</h1>
  <div class="sub" id="sub">Loading…</div>
  <input id="q" type="search" placeholder="Filter by company, title, or location…"
         autocomplete="off">
  <ul id="list"></ul>
  <div class="empty" id="empty" hidden>Nothing matches that filter.</div>
</div>
<script>
let JOBS = [];
const esc = s => (s||"").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function render(filter) {
  const f = (filter||"").toLowerCase().trim();
  const rows = f ? JOBS.filter(j =>
    (j.title+" "+j.company+" "+j.location).toLowerCase().includes(f)) : JOBS;
  document.getElementById("empty").hidden = rows.length > 0;
  document.getElementById("list").innerHTML = rows.map(j => `
    <li>
      <span class="date">${esc(j.posted || "—")}</span>
      <span class="main">
        <a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
        ${j.phd ? '<span class="phd">PhD</span>' : ""}
        <div class="meta"><span class="co">${esc(j.company)}</span>
          ${j.location ? " · " + esc(j.location) : ""}</div>
      </span>
    </li>`).join("");
}

fetch("jobs.json?" + Date.now())
  .then(r => r.json())
  .then(d => {
    JOBS = d.jobs;
    document.getElementById("sub").textContent =
      `${d.count} roles · updated ${d.updated}`;
    render("");
  })
  .catch(() => { document.getElementById("sub").textContent =
    "Could not load jobs.json"; });

document.getElementById("q").addEventListener("input", e => render(e.target.value));
</script>
</body>
</html>
"""
