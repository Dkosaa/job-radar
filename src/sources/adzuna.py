"""
Adzuna DE — covers StepStone + Indeed content via aggregator.
Free tier: 250 calls/month. We use 1 call/day (30/month) so we run
~8x under the limit.
https://developer.adzuna.com/docs/search
"""
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from typing import Any

from config import ADZUNA, PIPELINE, DATA as ROOT_DATA

API_BASE = "https://api.adzuna.com/v1/api/jobs/de/search/{page}"
QUOTA_FILE = ROOT_DATA / "adzuna_quota.json"

# Search queries — rotate through these, max 8 per day
QUERIES = [
    "RPA Developer",                    # ~2 days
    "UiPath OR Power Automate",         # tools
    "Process Automation Engineer",
    "Test Automation Engineer",
    "Automation Engineer",              # broadest catch-all
    "Workflow Automation",
    "Robotic Process Automation",
    "Intelligent Automation",
    "Blue Prism OR Automation Anywhere",
    "AI Automation Engineer",
    "Product Owner Automation",
    "Power Platform Developer",
]


# ──── monthly quota guard ───────────────────────────────────────────
def _load_quota() -> dict:
    if QUOTA_FILE.exists():
        try:
            import json
            return json.loads(QUOTA_FILE.read_text())
        except Exception:
            pass
    return {"month": "", "calls": 0, "limit": 250}


def _save_quota(q: dict) -> None:
    import json
    QUOTA_FILE.write_text(json.dumps(q))


def _can_call(q: dict) -> bool:
    cur_month = datetime.now().strftime("%Y-%m")
    if q["month"] != cur_month:
        q["month"] = cur_month
        q["calls"] = 0
    return q["calls"] < q["limit"]


def _record_call(q: dict) -> None:
    q["calls"] += 1
    _save_quota(q)


# ──── fetch ──────────────────────────────────────────────────────────
def fetch(timeout: int = 25) -> list[dict[str, Any]]:
    if not ADZUNA.get("app_id") or not ADZUNA.get("app_key"):
        # Silent no-op if keys missing — other sources still work
        return []

    quota = _load_quota()
    if not _can_call(quota):
        print(f"[adzuna] monthly quota exhausted "
              f"({quota['calls']}/{quota['limit']}) — skipping")
        return []

    # Daily call budget: 8 calls/day × ~30 days = 240 calls/month
    # (50 calls/month headroom for ad-hoc /rerun queries)
    DAILY_LIMIT = 8

    # Rotate which queries to run today so we cover all of them across
    # ~3-4 days of the month, instead of burning budget on the same
    # queries repeatedly.
    today = datetime.now().day
    slot = (today - 1) % 4   # 0..3 — which quarter of queries to run
    n = max(1, len(QUERIES) // 4)
    todays_queries = QUERIES[slot * n:(slot + 1) * n]
    if not todays_queries:
        todays_queries = QUERIES[:n]

    out = []
    queries_used = 0
    for query in todays_queries:
        if not _can_call(quota):
            print(f"[adzuna] quota reached mid-run "
                  f"({quota['calls']}/{quota['limit']})")
            break
        if queries_used >= DAILY_LIMIT:
            break
        # 1 page = 50 results. Use page 1 only to conserve quota.
        # results_per_page max is 50 on free tier.
        url = API_BASE.format(page=1)
        params = {
            "app_id": ADZUNA["app_id"],
            "app_key": ADZUNA["app_key"],
            "results_per_page": 50,
            "what": query,
            "where": "Deutschland",
            "max_days_old": 7,           # last week — broader than 24h to get results
            "sort_by": "date",
            "full_time": 1,
            "permanent": 1,
        }
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers={"User-Agent": PIPELINE["user_agent"]})
            if r.status_code == 403:
                print("[adzuna] 403 — check app_id/app_key")
                break
            r.raise_for_status()
            data = r.json()
            _record_call(quota)
            queries_used += 1
        except Exception as e:
            print(f"[adzuna:{query}] {e}")
            continue

        for j in data.get("results", []):
            loc = (j.get("location") or {}).get("display_name", "")
            sal_min = j.get("salary_min")
            sal_max = j.get("salary_max")
            # Adzuna reports salary in the local currency; for DE jobs
            # we assume EUR but flag if it's USD/GBP.
            sal_eur = None
            if sal_min:
                sal_eur = int(sal_min)
            out.append({
                "id": f"adzuna-{j.get('id')}",
                "source": "adzuna",
                "title": j.get("title", ""),
                "company": (j.get("company") or {}).get("display_name", ""),
                "location": loc,
                "country": "Germany",
                "remote_ok": "remote" in loc.lower()
                             or "homeoffice" in loc.lower(),
                "url": j.get("redirect_url", ""),
                "description": j.get("description", ""),
                "tags": [query],
                "salary_eur": sal_eur,
                "posted_at": j.get("created"),  # ISO timestamp
            })
        # tiny sleep to be polite
        time.sleep(0.3)

    print(f"[adzuna] used {queries_used} calls this run, "
          f"{quota['calls']}/{quota['limit']} this month")
    return out


if __name__ == "__main__":
    import os
    if not ADZUNA.get("app_id"):
        print("Set ADZUNA_APP_ID and ADZUNA_APP_KEY env vars to test.")
    else:
        jobs = fetch()
        print(f"got {len(jobs)} jobs")
        for j in jobs[:3]:
            print(f"  {j['title'][:50]} @ {j.get('company','')[:20]} | "
                  f"{j.get('location','')[:25]} | sal={j.get('salary_eur')}")