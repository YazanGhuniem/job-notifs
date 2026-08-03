"""Filter regression tests.

These lock in the tricky cases found while tuning against ~16k real postings.
Run: python -m tests.test_filters   (or: pytest tests/)
"""

from pathlib import Path

import yaml

from src.filters import Filters
from src.models import Job

ROOT = Path(__file__).resolve().parent.parent
F = Filters(yaml.safe_load((ROOT / "config" / "filters.yaml").read_text()))


def job(title, location="San Francisco, CA", department=""):
    return Job(company="Test", title=title, url="", job_id="1",
               location=location, department=department)


# (title, should_match, why)
TITLES = [
    # --- should match -----------------------------------------------------
    ("Software Engineer Intern", True, "the basic case"),
    ("Software Development Engineer Internship - Fall 2026 (US)", True, ""),
    ("Machine Learning Intern/Co-op (Fall, 2026)", True, ""),
    ("AI/ML Scientist Intern, AIMS AI Foundations (PhD)", True, ""),
    ("Data Science Intern", True, ""),
    ("Backend Engineering Intern", True, ""),
    ("Firmware Intern [Fall 2026]", True, "embedded software counts"),
    ("Research Internship (Fall, 2026)", True, "AI-lab research internship"),
    ("Video Algorithms Intern, Video Coding", True, ""),
    ("Forward Deployed Software Engineer, Internship", True, ""),
    ("Security Engineer Intern", True, ""),
    ("Site Reliability Engineering Co-op", True, ""),
    ("iOS Engineer Intern", True, ""),
    ("Fall 2026 Software Engineering Internship/Co-op", True, ""),
    ("ML Intern, Silicon Architecture", True, "override beats the silicon veto"),
    ("Software Engineer Intern, Supply Chain", True, "override beats veto"),

    # Enterprise/bank naming — these employers rarely put "software" in a
    # title, so the CS gate has to recognize IT / rotational-program wording.
    ("Information Technology Leadership Program Intern", True, ""),
    ("2027 IT Intern - Cincinnati", True, ""),
    ("Technology Development Program Intern", True, ""),
    ("2027 Technology Co-Op", True, ""),
    ("Information Security Intern", True, ""),
    ("Enterprise Data Intern", True, ""),

    # --- should NOT match -------------------------------------------------
    # ...but the bank patterns must not drag in the finance side of a bank.
    ("2027 Financial Audit Intern", False, "audit is out of scope"),
    ("2027 IT Audit Intern", False, "audit, despite the 'IT'"),
    ("Risk Internship Program - May 2027", False, ""),
    ("Investment Banking Summer Analyst", False, ""),
    ("Wealth Management Intern", False, ""),
    ("Internal Tools Engineer", False, "word-boundary trap: 'Intern'al"),
    ("International Payments Analyst", False, "word-boundary trap"),
    ("2027 Mechanical Engineer Intern", False, "generic match + veto"),
    ("2027 Electrical Engineer Intern", False, ""),
    ("Naval Architect Co-op - Winter 2027", False, ""),
    ("Technical Support Engineer Intern", False, "support, not dev"),
    ("Marketing Intern", False, ""),
    ("Sales Project Manager Intern (AI Innovation)", False, "AI in a sales role"),
    ("Product Management Intern (Summer 2027)", False, "PM is out of scope"),
    ("Recruiting Coordinator, Intern Program", False, ""),
    ("Intern Program Manager", False, "runs the program, isn't in it"),
    ("Apprentice Weld Support Technician", False, ""),
    ("Governance, Risk, and Compliance Intern", False, ""),
    ("UX Research Intern", False, "research, but not CS research"),
    ("Software Engineer II", False, "not an internship"),
    ("People Operations Apprentice", False, ""),
]

LOCATIONS = [
    ("San Francisco, CA", True),
    ("US, CA, Santa Clara", True),
    ("Los Gatos,California,United States of America", True),
    ("Seattle, Washington, USA", True),
    ("Austin, TX", True),
    ("Washington, D.C.", True),
    ("New York, NY (HQ) | San Francisco, CA | USA | Remote", True),
    ("Warsaw, Poland | New York, NY", True, ),
    ("San Francisco, CA; New York, NY", True),
    ("", True, ),
    ("Remote", True),
    ("3 Locations", True),
    ("Multiple Locations", True),
    ("Belgrade | Serbia", False),
    ("Bangalore, India", False),
    ("London, United Kingdom", False),
    ("Toronto, Ontario, Canada", False),
    ("Sydney, Australia", False),
    ("Zurich, Switzerland", False),
    ("Tel Aviv", False),
    ("Cluj-Napoca", False),
    ("Dublin, Ireland | London", False),
]


def test_titles():
    failures = []
    for title, expected, why in TITLES:
        got = F.evaluate(job(title)).ok
        if got != expected:
            failures.append(f"  {title!r}: expected {expected}, got {got}"
                            f"{'  <- ' + why if why else ''}")
    assert not failures, "title filter:\n" + "\n".join(failures)


def test_locations():
    failures = []
    for loc, expected in LOCATIONS:
        got = F.location_ok(loc)
        if got != expected:
            failures.append(f"  {loc!r}: expected {expected}, got {got}")
    assert not failures, "location filter:\n" + "\n".join(failures)


def test_assume_us_bypasses_location():
    j = job("Software Engineer Intern", location="Flexible - Any SpaceX Site")
    assert not F.evaluate(j).ok
    assert F.evaluate(j, assume_us=True).ok


def test_uid_is_stable_across_title_edits():
    a = Job(company="X", title="SWE Intern", url="", job_id="99")
    b = Job(company="X", title="SWE Intern (Summer 2027)", url="", job_id="99")
    assert a.uid == b.uid


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {name}\n{e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
