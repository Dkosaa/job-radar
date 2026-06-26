"""
Apify scraper integration — premium paid source for StepStone, Indeed, LinkedIn.
Apify has pre-built scrapers that handle captcha/proxy for ~$5/month/1000 jobs.
https://apify.com/

Popular actors we can call:
  - valig/indeed-jobs-scraper         (~$0.50 per 1000 results)
  - lukas/linkedin-jobs-scraper       (~$5 per 1000 results)
  - tri_angle/indeed-scraper          (cheaper alternative)
  - valig/stepstone-jobs-scraper      (StepStone content)

Authentication: Bearer token (APIFY_API_TOKEN env var or config.APIFY).
"""
import os
import time
import json
import requests
from typing import Any
from pathlib import Path

from config import DATA as ROOT_DATA, PIPELINE

APIFY_BASE = "https://api.apify.com/v2"
QUOTA_FILE = ROOT_DATA / "apify_quota.json"

# Quota guard — Apify is pay-per-result, we cap our monthly spend
MONTHLY_LIMIT_USD = 5.0  # $5/mo as per Raj's plan
COST_PER_1K_JOBS_USD = 0.50  # for Indeed-class actors


def _load_quota() -> dict:
    if QUOTA_FILE.exists():
        try:
            return json.loads(QUOTA_FILE.read_text())
        except Exception:
            pass
    return {"month": "", "spent_usd": 0.0, "jobs_fetched": 0, "limit": MONTHLY_LIMIT_USD}


def _save_quota(q: dict) -> None:
    QUOTA_FILE.write_text(json.dumps(q, indent=2))


def _can_spend(q: dict, est_jobs: int) -> bool:
    from datetime import datetime
    cur = datetime.now().strftime("%Y-%m")
    if q["month"] != cur:
        q["month"] = cur
        q["spent_usd"] = 0.0
        q["jobs_fetched"] = 0
    est_cost = (est_jobs / 1000.0) * COST_PER_1K_JOBS_USD
    return (q["spent_usd"] + est_cost) <= q["limit"]


def _record_spend(q: dict, jobs_count: int) -> None:
    cost = (jobs_count / 1000.0) * COST_PER_1K_JOBS_USD
    q["spent_usd"] += cost
    q["jobs_fetched"] += jobs_count
    _save_quota(q)


def _get_token() -> str | None:
    """Get Apify token from env or config."""
    from config import APIFY
    token = os.environ.get("APIFY_API_TOKEN", "") or APIFY.get("token", "")
    return token if token else None


# Search queries for the actors — German RPA/automation
SEARCH_QUERIES = [
    "RPA Developer",
    "UiPath Developer",
    "Power Automate",
    "Process Automation Engineer",
    "Test Automation Engineer",
    "Automation Engineer",
    "Workflow Automation",
    "Robotic Process Automation",
    "AI Automation",
    "Product Owner Automation",
]

# Locations (German cities + remote)
LOCATIONS = [
    "Regensburg",
    "München",
    "Munich",
    "Nürnberg",
    "Berlin",
    "Hamburg",
    "Frankfurt",
    "Stuttgart",
    "Köln",
    "Düsseldorf",
    "Germany",
]


def fetch_indeed_via_apify(queries: list[str] = None,
                            locations: list[str] = None,
                            results_per_query: int = 50,
                            timeout: int = 120) -> list[dict[str, Any]]:
    """
    Call Apify's Indeed scraper actor and return normalized jobs.
    Actor: valig/indeed-jobs-scraper (or similar)
    Cost: ~$0.50 per 1000 results
    """
    token = _get_token()
    if not token:
        print("[apify] no APIFY_API_TOKEN configured — skipping")
        return []

    quota = _load_quota()
    queries = queries or SEARCH_QUERIES[:4]  # default: 4 queries to stay under budget
    locations = locations or ["Germany"]
    estimated_jobs = len(queries) * len(locations) * results_per_query

    if not _can_spend(quota, estimated_jobs):
        print(f"[apify] monthly budget exhausted "
              f"(${quota['spent_usd']:.2f}/${quota['limit']}) — skipping")
        return []

    # Apify actor input format for Indeed scraper
    actor_input = {
        "queries": [f"{q} {loc}" for q in queries for loc in locations],
        "maxResults": results_per_query,
        "country": "DE",
        "location": "Germany",
        "language": "en",
        "remote": False,
    }

    # Run actor synchronously (wait for finish)
    run_url = f"{APIFY_BASE}/acts/valig~indeed-jobs-scraper/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}

    print(f"[apify] triggering Indeed actor, ~{estimated_jobs} jobs est...")
    try:
        r = requests.post(run_url, json=actor_input, headers=headers,
                          timeout=timeout)
        if r.status_code == 401:
            print("[apify] 401 — check APIFY_API_TOKEN")
            return []
        r.raise_for_status()
        items = r.json()
    except Exception as e:
        print(f"[apify] Indeed fetch failed: {e}")
        return []

    out = []
    for j in items:
        out.append(_normalize_apify_job(j, source="apify_indeed"))

    _record_spend(quota, len(out))
    print(f"[apify] got {len(out)} Indeed jobs, "
          f"spent ${quota['spent_usd']:.2f}/${quota['limit']} this month")
    return out


def fetch_stepstone_via_apify(queries: list[str] = None,
                               locations: list[str] = None,
                               results_per_query: int = 50,
                               timeout: int = 120) -> list[dict[str, Any]]:
    """
    Call Apify's StepStone scraper actor.
    Actor: valig/stepstone-jobs-scraper (or similar)
    """
    token = _get_token()
    if not token:
        return []
    quota = _load_quota()
    queries = queries or SEARCH_QUERIES[:4]
    locations = locations or ["Germany"]
    estimated_jobs = len(queries) * len(locations) * results_per_query
    if not _can_spend(quota, estimated_jobs):
        print(f"[apify] budget exhausted — skipping StepStone")
        return []

    actor_input = {
        "queries": [f"{q} {loc}" for q in queries for loc in locations],
        "maxResults": results_per_query,
        "country": "DE",
        "language": "en",
    }
    run_url = f"{APIFY_BASE}/acts/valig~stepstone-jobs-scraper/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    print(f"[apify] triggering StepStone actor, ~{estimated_jobs} jobs est...")
    try:
        r = requests.post(run_url, json=actor_input, headers=headers,
                          timeout=timeout)
        if r.status_code in (401, 404):
            print(f"[apify] StepStone actor {r.status_code} — check actor ID")
            return []
        r.raise_for_status()
        items = r.json()
    except Exception as e:
        print(f"[apify] StepStone fetch failed: {e}")
        return []

    out = [_normalize_apify_job(j, source="apify_stepstone") for j in items]
    _record_spend(quota, len(out))
    print(f"[apify] got {len(out)} StepStone jobs, "
          f"spent ${quota['spent_usd']:.2f}/${quota['limit']} this month")
    return out


def _normalize_apify_job(j: dict, source: str = "apify") -> dict:
    """Convert an Apify actor's job dict into our standard format."""
    title = (j.get("title") or j.get("positionName") or "").strip()
    company = (j.get("companyName") or j.get("company") or "").strip()
    loc = (j.get("location") or j.get("jobLocation") or "").strip()
    desc = (j.get("description") or j.get("descriptionHTML") or
            j.get("descriptionText") or "")
    if isinstance(desc, str) and "<" in desc:
        # strip HTML
        import re
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
    url = (j.get("link") or j.get("jobUrl") or j.get("url") or "").strip()
    sal_min = j.get("salaryMin") or j.get("salary_min")
    sal_max = j.get("salaryMax") or j.get("salary_max")
    sal_eur = None
    if isinstance(sal_min, (int, float)):
        sal_eur = int(sal_min)
    posted = j.get("postedAt") or j.get("publicationDate") or j.get("date")

    # Stable ID
    base = url or f"{title}|{company}|{loc}"
    jid = f"apify-{source}-{hash(base) & 0xfffffff}"

    return {
        "id": jid,
        "source": source,
        "title": title,
        "company": company,
        "location": loc,
        "country": "Germany",
        "remote_ok": any(k in loc.lower() for k in
                         ["remote", "homeoffice", "deutschlandweit"]),
        "url": url,
        "description": desc[:8000],
        "tags": [],
        "salary_eur": sal_eur,
        "posted_at": posted,
    }


def fetch(timeout: int = 25) -> list[dict[str, Any]]:
    """Entry point for pipeline. Combines all Apify actors."""
    out = []
    out.extend(fetch_indeed_via_apify(timeout=timeout))
    out.extend(fetch_stepstone_via_apify(timeout=timeout))
    return out


if __name__ == "__main__":
    if not _get_token():
        print("Set APIFY_API_TOKEN environment variable first.")
        print("Free $5 credit at https://apify.com/")
    else:
        jobs = fetch()
        print(f"\nTotal: {len(jobs)} jobs")
        for j in jobs[:5]:
            print(f"  {j['title'][:50]} @ {j.get('company','')[:20]}")
        print(f"\nQuota: ${_load_quota()['spent_usd']:.2f} / "
              f"${_load_quota()['limit']}")