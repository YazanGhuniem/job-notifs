"""Decide whether a posting is a CS internship in the US.

Four gates, in order: internship → CS allowlist → veto → location.
Every gate is driven by config/filters.yaml so tuning needs no code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Job

# US states + DC + PR, as full names and postal codes.
US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "puerto rico": "PR",
}

US_CITIES = {
    "san francisco", "sf", "new york", "nyc", "seattle", "austin", "boston",
    "cambridge", "chicago", "los angeles", "san jose", "palo alto",
    "mountain view", "sunnyvale", "santa clara", "menlo park", "redmond",
    "bellevue", "denver", "atlanta", "dallas", "houston", "miami", "phoenix",
    "portland", "san diego", "pittsburgh", "philadelphia", "detroit",
    "minneapolis", "salt lake city", "boulder", "raleigh", "durham",
    "arlington", "bethesda", "mclean", "reston", "irvine", "culver city",
    "brooklyn", "oakland", "berkeley", "washington dc", "nashville",
    "columbus", "ann arbor", "madison", "st. louis", "kirkland", "hillsboro",
}

# Substrings that positively identify the US.
US_MARKERS = (
    "united states", "u.s.", "usa", "u.s.a", "remote - us", "remote, us",
    "us-remote", "remote us", "us remote",
)

CANADA_MARKERS = (
    "canada", "toronto", "vancouver", "montreal", "ottawa", "waterloo",
    "calgary", "edmonton", "mississauga", "ontario", "quebec",
    "british columbia", "alberta",
)

# Countries/cities that positively identify a NON-US posting. Used to reject
# when no US marker is present.
NON_US_MARKERS = (
    "united kingdom", "london", "ireland", "dublin", "germany", "berlin",
    "munich", "france", "paris", "netherlands", "amsterdam", "spain",
    "madrid", "barcelona", "italy", "milan", "rome", "switzerland", "zurich",
    "geneva", "sweden", "stockholm", "norway", "oslo", "denmark",
    "copenhagen", "finland", "helsinki", "poland", "warsaw", "krakow",
    "portugal", "lisbon", "belgium", "brussels", "austria", "vienna",
    "czech", "prague", "romania", "bucharest", "greece", "athens",
    "india", "bangalore", "bengaluru", "hyderabad", "mumbai", "delhi",
    "gurgaon", "gurugram", "pune", "chennai", "noida",
    "china", "beijing", "shanghai", "shenzhen", "hong kong", "taiwan",
    "taipei", "japan", "tokyo", "korea", "seoul", "singapore", "malaysia",
    "kuala lumpur", "indonesia", "jakarta", "thailand", "bangkok",
    "vietnam", "philippines", "manila", "australia", "sydney", "melbourne",
    "new zealand", "auckland", "brazil", "sao paulo", "mexico",
    "guadalajara", "mexico city", "argentina", "chile", "colombia",
    "bogota", "costa rica", "israel", "tel aviv", "uae", "dubai",
    "saudi", "riyadh", "egypt", "cairo", "south africa", "nigeria",
    "kenya", "turkey", "istanbul", "ukraine", "kyiv",
)

PHD_RE = re.compile(r"\b(ph\.?d|doctoral|doctorate)\b", re.I)


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns or []]


def _any(pats: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in pats)


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    is_phd: bool = False


class Filters:
    def __init__(self, cfg: dict):
        self.internship = _compile(cfg.get("internship", []))
        self.internship_exclude = _compile(cfg.get("internship_exclude", []))
        self.cs_include = _compile(cfg.get("cs_include", []))
        self.cs_exclude = _compile(cfg.get("cs_exclude", []))
        self.cs_exclude_override = _compile(cfg.get("cs_exclude_override", []))

        loc = cfg.get("location") or {}
        self.loc_mode = loc.get("mode", "us")
        self.loc_fail_open = loc.get("fail_open", True)
        self.exclude_phd = cfg.get("exclude_phd", False)
        self.max_alerts = cfg.get("max_alerts_per_run", 15)

    # -- gate 4 ------------------------------------------------------------
    def location_ok(self, raw: str) -> bool:
        """A named location must show positive evidence of being in the US.

        Fail-open applies only when there's nothing to go on (blank, or a bare
        "Remote"). Anything else that names a place we can't confirm as US is
        rejected — otherwise foreign cities we don't have in NON_US_MARKERS
        (Belgrade, Cluj, Wrocław, ...) sail straight through.
        """
        if self.loc_mode == "anywhere":
            return True

        raw = (raw or "").strip()
        if not raw:
            return self.loc_fail_open

        # Providers join multiple offices with "|" or ";". Evaluate each
        # separately and accept if ANY is in the US — otherwise a posting
        # listing "Warsaw, Poland | New York, NY" gets vetoed by Warsaw.
        segments = [s for s in re.split(r"[|;]", raw) if s.strip()]
        if len(segments) > 1:
            return any(self._segment_ok(s) for s in segments)
        return self._segment_ok(raw)

    def _segment_ok(self, raw: str) -> bool:
        loc = raw.strip().lower()
        if not loc:
            return False

        allow_ca = self.loc_mode == "us_ca"
        has_non_us = any(m in loc for m in NON_US_MARKERS)
        is_canada = any(m in loc for m in CANADA_MARKERS)

        # A posting listing several offices counts if ANY of them is in the US.
        if any(m in loc for m in US_MARKERS):
            return True
        if allow_ca and is_canada:
            return True

        if not has_non_us:
            if any(name in loc for name in US_STATES):
                return True
            if any(c in loc for c in US_CITIES):
                return True
            # Postal codes as standalone tokens: "US, CA, Santa Clara",
            # "Austin, TX". Substring matching would fire on "IN" inside
            # "Bangalore, India", hence the tokenization.
            tokens = set(re.split(r"[,|/()\-\s]+", loc))
            if tokens & {c.lower() for c in US_STATES.values()}:
                return True

        if has_non_us or (is_canada and not allow_ca):
            return False

        # No geography attached at all — can't rule it out, so don't.
        # Workday in particular collapses multi-office reqs to "3 Locations".
        if re.fullmatch(
            r"[\s|,\-]*(remote|anywhere|global|flexible|in-office"
            r"|multiple locations|\d+\s+locations?)[\s|,\-]*",
            loc,
        ):
            return self.loc_fail_open

        # Named a place, but nothing identifies it as US.
        return False

    # -- full evaluation ---------------------------------------------------
    def evaluate(self, job: Job, assume_us: bool = False) -> Verdict:
        title = job.title.lower()
        # Department is included for the CS gate only: "Intern" in a
        # department name shouldn't satisfy gate 1.
        cs_text = f"{title} {job.department.lower()}"

        if not _any(self.internship, title):
            return Verdict(False, "not-an-internship")
        if _any(self.internship_exclude, title):
            return Verdict(False, "internship-role-excluded")

        if not _any(self.cs_include, cs_text):
            return Verdict(False, "no-cs-signal")

        # The veto always applies — generic allow patterns like "engineering
        # intern" would otherwise wave through "Mechanical Engineer Intern".
        # cs_exclude_override immunizes titles that are unambiguously software
        # even with a veto word present ("ML Intern, Silicon Architecture").
        if _any(self.cs_exclude, cs_text) and not _any(
            self.cs_exclude_override, cs_text
        ):
            return Verdict(False, "non-cs-discipline")

        # assume_us: for companies that only hire in the US but write
        # non-geographic locations ("Flexible - Any SpaceX Site").
        if not assume_us and not self.location_ok(job.location):
            return Verdict(False, "location")

        is_phd = bool(PHD_RE.search(job.title))
        if is_phd and self.exclude_phd:
            return Verdict(False, "phd-required")

        return Verdict(True, "match", is_phd)
