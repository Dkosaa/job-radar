"""
Strict keyword filter for Raj's job search.
Used as a hard gate — if JD doesn't contain required keywords, job is dropped.

This runs AFTER scraping (agent-side) to enforce Raj's exact requirements.
For Apify, we also pass these keywords INTO the actor input so we don't
waste API credits on jobs that won't pass.
"""
import re
from typing import Any

# ──── Required keywords (must appear in title OR description) ────────
# Tier 1 — these MUST appear (any one of them). All jobs must have at
# least ONE of these terms in the JD.
REQUIRED_KEYWORDS = {
    # RPA platforms
    "uipath",
    "blue prism",
    "blueprism",
    "power automate",
    "power platform",
    "automation anywhere",
    # Concepts
    "rpa",
    "robotic process automation",
    "robotic",
    "process automation",
    "workflow automation",
    "intelligent automation",
    "hyperautomation",
    # Tools you have
    "orchestrator",
    "power bi",
    "powerbi",
    "ocr",
}

# ──── Excluded keywords (job DROPPED if ANY of these appear) ────────
EXCLUDED_KEYWORDS = {
    # Pure dev / wrong direction
    "ios developer", "android developer",
    "sales", "marketing", "business development",
    "data scientist", "machine learning researcher",
    # Junior-only
    "intern", "praktikum", "werkstudent", "working student",
    "trainee", "junior position",
    # Wrong location / visa
    "us-based only", "uk only", "sponsorship required",
    # Non-tech
    "waiter", "driver", "warehouse",
}

# ──── At least N of these "must mention" keywords must be present ────
# Per Raj's spec: OCR, PowerBI, Orchestrator, RPA, UiPath, BluePrism
# We require at least 3 of these (or 2 of the platforms specifically).
KEYWORDS_TO_COUNT = [
    "uipath",
    "blue prism",
    "power automate",
    "rpa",
    "robotic process automation",
    "orchestrator",
    "power bi",
    "powerbi",
    "ocr",
    "process automation",
    "workflow automation",
    "automation anywhere",
]


def _has(text: str, kw: str) -> bool:
    """Word-boundary match for short keywords, substring for multi-word."""
    if " " in kw or kw.lower() in {"c#", "c++", ".net"}:
        return kw.lower() in text
    return bool(re.search(rf"\b{re.escape(kw.lower())}\b", text))


def strict_filter(job: dict, min_keyword_hits: int = 2) -> tuple[bool, list[str]]:
    """
    Returns (passes, reasons_if_failed).

    A job PASSES if:
      1. JD contains at least one REQUIRED_KEYWORD
      2. JD does NOT contain any EXCLUDED_KEYWORD
      3. JD contains at least min_keyword_hits of KEYWORDS_TO_COUNT

    A job FAILS otherwise, with reasons returned.
    """
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    text = title + " " + desc

    # Rule 1: at least one required keyword
    required_hits = [kw for kw in REQUIRED_KEYWORDS if _has(text, kw)]
    if not required_hits:
        return False, ["no required keyword (RPA / UiPath / BluePrism / Power Automate)"]

    # Rule 2: no excluded keywords
    excluded_hits = [kw for kw in EXCLUDED_KEYWORDS if _has(text, kw)]
    if excluded_hits:
        return False, [f"excluded keyword: {kw}" for kw in excluded_hits]

    # Rule 3: at least N keyword matches
    count_hits = [kw for kw in KEYWORDS_TO_COUNT if _has(text, kw)]
    if len(count_hits) < min_keyword_hits:
        return False, [f"only {len(count_hits)}/{min_keyword_hits} key tech terms"]

    return True, count_hits


def apply_strict_filter(jobs: list[dict],
                         min_keyword_hits: int = 1) -> tuple[list[dict], list[dict]]:
    """
    Apply strict filter to a list of jobs.
    Returns (passed_jobs, rejected_jobs_with_reasons).

    Default min_keyword_hits=1 (any one tech term) — tuneable via PIPELINE.
    Set to 2+ if you want stricter matches.
    """
    passed, rejected = [], []
    for j in jobs:
        ok, reasons = strict_filter(j, min_keyword_hits=min_keyword_hits)
        if ok:
            j["strict_keyword_hits"] = reasons
            passed.append(j)
        else:
            j["strict_reject_reasons"] = reasons
            rejected.append(j)
    return passed, rejected


# ──── Apify actor input builder ─────────────────────────────────────
def build_apify_actor_input(queries: list[str] | None = None,
                             locations: list[str] | None = None,
                             max_results: int = 50) -> dict:
    """
    Build Apify actor input that encodes Raj's strict requirements.

    Strategy: combine ALL required keywords into queries so the actor
    only returns jobs likely to pass our strict filter.

    The actor input format varies by actor — this builds input for the
    common Indeed-style scrapers.
    """
    queries = queries or [
        "UiPath",
        "Blue Prism",
        "Power Automate",
        "RPA",
        "Orchestrator",
        "Power BI OCR",
        "Process Automation",
    ]
    locations = locations or ["Germany", "Remote Germany"]
    max_results = min(max_results, 50)  # cap per query

    return {
        "queries": [f"{q} {loc}" for q in queries for loc in locations],
        "maxResults": max_results,
        "country": "DE",
        "location": "Germany",
        "language": "en",
        "remote": False,
        "includeKeywords": list(REQUIRED_KEYWORDS),  # actor pre-filter
        "excludeKeywords": list(EXCLUDED_KEYWORDS),  # actor pre-filter
        "maxAgeDays": 30,
    }


if __name__ == "__main__":
    # Quick test
    test_jobs = [
        {
            "title": "Senior UiPath RPA Developer",
            "description": "Looking for UiPath, Orchestrator, Power BI, OCR expert. BluePrism a plus. RPA automation work."
        },
        {
            "title": "Marketing Manager",
            "description": "Sales and marketing role"
        },
        {
            "title": "Junior Developer",
            "description": "Looking for a junior RPA developer"
        },
        {
            "title": "Process Automation Engineer",
            "description": "Power Automate and OCR work, RPA focus"
        },
    ]
    passed, rejected = apply_strict_filter(test_jobs)
    print(f"Passed: {len(passed)}")
    for j in passed:
        print(f"  ✓ {j['title']} — matched: {j.get('strict_keyword_hits')}")
    print(f"\nRejected: {len(rejected)}")
    for j in rejected:
        print(f"  ✗ {j['title']} — {j.get('strict_reject_reasons')}")