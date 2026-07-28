# Internship Notifier

Telegram alerts the moment one of ~50 companies posts a CS internship in the US.

Polls each company's job board directly through its applicant-tracking system's
public JSON API — no scraping, nothing to break when someone restyles a careers
page. Runs on GitHub Actions every 30 minutes, so it works with your laptop shut.

Currently watching **53 boards / ~16,000 live postings**, of which ~70 match.

---

## Setup (about 5 minutes)

### 1. Make a Telegram bot

Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the prompts →
copy the token (looks like `8123456789:AAH...`).

### 2. Get your chat ID

**Send your new bot a message first** — any text. Bots can't open a conversation
with you, so nothing works until you do. Then visit:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Copy `result[0].message.chat.id` — a number like `123456789`.

### 3. Try it locally

```bash
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="8123456789:AAH..."
export TELEGRAM_CHAT_ID="123456789"

python -m src.main --test-notify     # should ping your phone
python -m src.main --dry-run         # see what it finds, sends nothing
```

### 4. Put it on GitHub

```bash
git init && git add . && git commit -m "internship notifier"
git branch -M main
git remote add origin https://github.com/<you>/job-notifs.git
git push -u origin main
```

Then **Settings → Secrets and variables → Actions → New repository secret**, and
add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

> **Make the repo public.** Actions minutes are unlimited on public repos; on a
> private one this eats roughly your entire free 2000 min/month. No secrets are
> committed — they live in Actions secrets, not the code.

Kick off the first run from **Actions → check-internships → Run workflow**. You'll
get one "notifier is live" message establishing a baseline, and after that only
genuinely new postings.

---

## Commands

```bash
python -m src.main                        # normal run
python -m src.main --dry-run              # fetch + filter, send nothing
python -m src.main --dry-run --show-rejected   # see near-misses and why they failed
python -m src.main --company anthropic    # test one board
python -m src.main --test-notify          # check Telegram wiring
python -m src.main --bootstrap            # re-baseline without alerting

python -m tests.test_filters              # filter regression tests
python tools/discover.py "Company Name"   # find a company's ATS
```

---

## Adding a company

```bash
$ python tools/discover.py Rippling Datadog
✓ Datadog: greenhouse/Datadog  n=418
✗ Rippling: no public ATS found

# --- paste into config/companies.yaml ---
  datadog:
    name: Datadog
    ats: greenhouse
    token: Datadog
```

Paste the block into [config/companies.yaml](config/companies.yaml). That's it.

If it comes back "no public ATS found", that company uses a custom or
JS-only careers site and needs a purpose-built scraper.

---

## Tuning what counts as interesting

Everything lives in [config/filters.yaml](config/filters.yaml) — no code changes.
Four gates run in order:

1. **`internship`** — is it an internship at all? Uses `\bintern\b` word
   boundaries, because a bare substring match flags "**Intern**al Tools Engineer".
2. **`cs_include`** — is it computer-science relevant? SWE, AI/ML, data, infra,
   security, mobile, systems.
3. **`cs_exclude`** — veto list. Mechanical, electrical, marketing, sales,
   recruiting, PM, support, and so on. Always applied, because generic patterns
   like "engineering intern" also match "Mechanical Engineer Intern".
4. **`cs_exclude_override`** — beats the veto. `Software Engineer Intern, Supply
   Chain` should survive the `supply chain` veto; `ML Intern, Silicon
   Architecture` should survive `silicon`.

Then a **location** gate (US only). A named location must show positive evidence
of being in the US; only blank, `Remote`, or `3 Locations` fail open. Multi-office
postings match if *any* office is in the US.

Useful knobs at the bottom of the file:

| Setting | Default | Does |
|---|---|---|
| `location.mode` | `us` | `us` · `us_ca` · `anywhere` |
| `exclude_phd` | `false` | Drop PhD-only roles. Off — they're tagged `[PhD]` instead |
| `max_alerts_per_run` | `15` | Rest roll up into one "…and N more" message |

**After any edit, run `python -m tests.test_filters`** — it locks in ~35 tricky
cases found while tuning against 16k real postings.

---

## How it works

```
config/companies.yaml ─→ providers/*.py ─→ filters.py ─→ state.py ─→ notify.py
   53 boards              normalize to Job   4 gates      dedupe     Telegram
```

- **`src/providers/`** — one module per ATS. All 53 boards fetch concurrently
  (8 threads, ~12s total). Every call is isolated: one dead board can't abort
  the run.
- **`src/state.py`** — `state/seen.json`, keyed on a hash of company + ATS job
  ID so re-worded titles don't re-notify. Pruned after 120 days. Committed back
  to the repo by CI each run.
- **Bootstrap** — on an empty state file it marks everything seen and sends one
  summary instead of 68 notifications.
- **Health alerts** — if a board fails 5 runs in a row you get one message
  naming it, so a moved endpoint surfaces instead of going quietly silent.

### Supported ATS types

`greenhouse` · `ashby` · `lever` · `workday` · `smartrecruiters` · `eightfold`
· `amazon` · `uber` · `microsoft`

---

## Known gaps

**Not covered — no public JSON board:** Google, Apple, Meta, Salesforce,
Atlassian, Zoom, eBay, Etsy, Yelp, HashiCorp, Grammarly, Retool, Rippling,
Hugging Face, Mistral.

Apple has an API that responds, but it rejects every documented search and
filter form — you can only pull all ~6000 reqs, too heavy to poll every 30
minutes. The others run custom or JS-only sites. Each would need its own
scraper.

**Microsoft is unverified.** The endpoint was unreachable from the machine this
was built on (TLS hostname mismatch, most likely local network interception
rather than a wrong URL). It's enabled — if it's actually broken you'll get a
health alert naming it rather than silence.

**Timing.** GitHub's scheduled runs are best-effort and can lag 5–15 minutes
under load. Change the cron in
[.github/workflows/check.yml](.github/workflows/check.yml) if you want tighter.
