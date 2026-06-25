"""
Greenhouse public job board API.
https://developers.greenhouse.io/job-board.html
Each company has /jobs?content=true and ?location=...
"""
import requests
from typing import Any

from config import COMPANY_BOARDS, PIPELINE


def _fetch_company(slug: str, timeout: int) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = requests.get(
            url,
            params={"content": "true"},
            timeout=timeout,
            headers={"User-Agent": PIPELINE["user_agent"]},
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[greenhouse:{slug}] {e}")
        return []

    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        # content=true gives full HTML body — strip tags lightly
        body = re.sub(r"<[^>]+>", " ", j.get("content") or "")
        body = re.sub(r"\s+", " ", body).strip()
        out.append({
            "id": f"greenhouse-{slug}-{j.get('id')}",
            "source": "greenhouse",
            "company": slug.title(),
            "title": j.get("title", ""),
            "location": loc,
            "country": _country(loc),
            "remote_ok": "remote" in loc.lower(),
            "url": j.get("absolute_url", ""),
            "description": body[:8000],
            "tags": [],
            "salary_eur": None,
            "posted_at": j.get("updated_at"),
        })
    return out


def _country(loc: str) -> str:
    l = loc.lower()
    non_de = (
        "united states", "usa", "u.s.", " us,", " us)", "new york",
        "nyc", "san francisco", "los angeles", "boston", "seattle",
        "chicago", "austin", "denver", "atlanta", "miami", "washington",
        "united kingdom", " uk,", " uk)", "london", "england",
        "france", "spain", "italy", "netherlands", "amsterdam",
        "switzerland", "zurich", "austria", "vienna",
        "india", "mumbai", "bangalore", "bengaluru", "israel",
        "japan", "tokyo", "singapore", "australia", "sydney",
        "canada", "toronto", "vancouver", "mexico", "brazil",
        "madrid", "barcelona", "milan", "rome", "paris",
        "warsaw", "krakow", "tel aviv",
    )
    if any(c in l for c in non_de):
        return ""
    if any(c in l for c in [
        "germany", "deutschland", "berlin", "munich", "münchen",
        "hamburg", "frankfurt", "regensburg", "nürnberg", "stuttgart",
        "köln", "cologne", "düsseldorf", "leipzig", "dresden",
        "bavaria", "bayern", "magdeburg",
    ]):
        return "Germany"
    if "remote" in l:
        return "Remote"
    return ""


def fetch(timeout: int = 20) -> list[dict[str, Any]]:
    out = []
    for slug in COMPANY_BOARDS["greenhouse"]:
        out.extend(_fetch_company(slug, timeout))
    return out


# local re import to avoid extra at top
import re