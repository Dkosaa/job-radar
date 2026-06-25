"""
Arbeitnow — public JSON API, no auth, very friendly.
https://arbeitnow.com/api/job-board-api
"""
import requests
from typing import Any

API_URL = "https://arbeitnow.com/api/job-board-api"
PAGES = 5  # fetch 5 pages × 100 = 500 jobs


def fetch(timeout: int = 20) -> list[dict[str, Any]]:
    """Returns list of normalized jobs across multiple pages."""
    out = []
    for page in range(1, PAGES + 1):
        try:
            r = requests.get(API_URL, timeout=timeout,
                             params={"page": page})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[arbeitnow] page {page} failed: {e}")
            continue
        page_jobs = data.get("data", [])
        if not page_jobs:
            break
        for j in page_jobs:
            loc = j.get("location") or ""
            out.append({
                "id": f"arbeitnow-{j.get('slug')}",
                "source": "arbeitnow",
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": loc,
                "country": _country(loc),
                "remote_ok": j.get("remote", False),
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "tags": j.get("tags", []),
                "salary_eur": None,
                "posted_at": j.get("created_at"),
            })
    return out


def _country(loc: str) -> str:
    l = loc.lower()
    non_de = (
        "united states", "usa", "u.s.", "us-", "new york", "nyc",
        "san francisco", "los angeles", "london", "england",
        "france", "spain", "italy", "netherlands", "amsterdam",
        "switzerland", "zurich", "austria", "vienna", "india", "mumbai",
        "bangalore", "israel", "japan", "singapore", "australia",
        "sydney", "canada", "toronto", "mexico", "brazil", "poland",
    )
    if any(c in l for c in non_de):
        return ""
    if any(c in l for c in [
        "germany", "deutschland", "berlin", "munich", "münchen",
        "hamburg", "frankfurt", "regensburg", "nürnberg", "stuttgart",
        "köln", "cologne", "düsseldorf", "leipzig", "dresden",
        "bavaria", "bayern", "magdeburg", "remote", "deutschland",
    ]):
        return "Germany"
    return ""