"""
Remotive.io — public remote job board API, no auth.
https://remotive.com/api-documentation
"""
import requests
from typing import Any

API_URL = "https://remotive.com/api/remote-jobs"

# Categories relevant to Raj's profile
CATEGORIES = [
    "software-dev",      # broad
    "data",              # data engineering / analytics
    "product",           # product owner / manager
    "qa",                # QA / test automation
    "devops",            # devops / SRE
]


def fetch(timeout: int = 20) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for cat in CATEGORIES:
        try:
            r = requests.get(API_URL, params={"category": cat, "limit": 50},
                             timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[remotive:{cat}] {e}")
            continue

        for j in data.get("jobs", []):
            jid = j.get("id")
            if not jid or jid in seen:
                continue
            seen.add(jid)
            out.append({
                "id": f"remotive-{jid}",
                "source": "remotive",
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "") or "Remote",
                "country": "Remote",
                "remote_ok": True,
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "tags": [j.get("category", ""), j.get("job_type", "")],
                "salary_eur": _parse_salary_eur(j.get("salary", "") or ""),
                "posted_at": j.get("publication_date", ""),
            })
    return out


def _parse_salary_eur(text: str) -> int | None:
    if not text:
        return None
    import re
    # Remotive uses formats like "$80,000 - $100,000"
    nums = re.findall(r"(\d[\d,]*)", text.replace(",", ""))
    vals = []
    for n in nums:
        try:
            v = int(n)
            if 5000 < v < 500000:
                vals.append(v)
        except Exception:
            pass
    if not vals:
        return None
    if "$" in text or "USD" in text:
        return int(min(vals) * 0.92)  # USD → EUR rough
    return int(min(vals))


if __name__ == "__main__":
    jobs = fetch()
    print(f"got {len(jobs)} jobs")
    for j in jobs[:5]:
        print(f"  {j['title'][:50]} @ {j.get('company','')[:20]}")