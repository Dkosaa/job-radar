"""
Lever public job board API.
https://hire.lever.co/developer/documentation
"""
import re
import requests
from typing import Any

from config import COMPANY_BOARDS, PIPELINE


def _fetch_company(slug: str, timeout: int) -> list[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        r = requests.get(
            url,
            params={"mode": "json"},
            timeout=timeout,
            headers={"User-Agent": PIPELINE["user_agent"]},
        )
        if r.status_code in (404, 403):
            return []
        r.raise_for_status()
    except Exception as e:
        print(f"[lever:{slug}] {e}")
        return []

    out = []
    for j in r.json():
        loc = (j.get("categories") or {}).get("location", "") or ""
        cats = (j.get("categories") or {}).get("all", []) or []
        # Lever gives plain-text description under "description" or "additional"
        body = j.get("descriptionPlain", "") or ""
        body = re.sub(r"\s+", " ", body).strip()
        out.append({
            "id": f"lever-{slug}-{j.get('id')}",
            "source": "lever",
            "company": slug.title(),
            "title": j.get("text", ""),
            "location": loc,
            "country": _country(loc),
            "remote_ok": "remote" in loc.lower(),
            "url": j.get("hostedUrl", ""),
            "description": body[:8000],
            "tags": cats,
            "salary_eur": None,
            "posted_at": None,
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
    for slug in COMPANY_BOARDS["lever"]:
        out.extend(_fetch_company(slug, timeout))
    return out