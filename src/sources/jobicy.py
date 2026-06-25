"""
Jobicy — public remote-job API, no auth.
https://jobicy.com/api/v2/remote-jobs
We tag-filter for automation / testing / engineering roles that
could fit Raj's profile (including remote roles open to DE residents).
"""
import requests
import time
from typing import Any

API_URL = "https://jobicy.com/api/v2/remote-jobs"

# Jobicy's own taxonomy uses these tag slugs
TAGS = [
    "automation", "devops", "engineering", "python",
    "javascript", "java", "backend", "data", "product",
    "ops", "qa-automation", "sre", "fullstack", "machine-learning",
]


def fetch(timeout: int = 20) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for tag in TAGS:
        try:
            r = requests.get(API_URL, params={"count": 50, "tag": tag},
                             timeout=timeout)
            if r.status_code == 429:
                time.sleep(2)
                r = requests.get(API_URL, params={"count": 50, "tag": tag},
                                 timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[jobicy:{tag}] {e}")
            time.sleep(1)
            continue
        time.sleep(0.6)  # be polite to Jobicy

        for j in data.get("jobs", []):
            jid = j.get("id")
            if not jid or jid in seen:
                continue
            seen.add(jid)
            geo = j.get("jobGeo", "") or ""
            # remote roles → mark DE-eligible since Raj is OK with remote-from-DE
            out.append({
                "id": f"jobicy-{jid}",
                "source": "jobicy",
                "title": j.get("jobTitle", ""),
                "company": j.get("companyName", ""),
                "location": f"Remote ({geo})",
                "country": "Germany" if geo.lower() in {
                    "germany", "deutschland", ""
                } else "Remote",
                "remote_ok": True,
                "url": j.get("url", ""),
                "description": j.get("jobExcerpt", "") or j.get("jobDescription", ""),
                "tags": (j.get("jobIndustry", []) or []) + (j.get("jobType", []) or []),
                "salary_eur": _parse_min_salary_eur(
                    j.get("jobSalary", "") or ""
                ),
                "posted_at": j.get("pubDate", ""),
            })
    return out


def _parse_min_salary_eur(text: str) -> int | None:
    if not text:
        return None
    import re
    # Jobicy uses formats like "$50,000 - $80,000" or "EUR 60K"
    nums = re.findall(r"(\d+(?:[\.,]\d+)?)(?:[Kk]|\s*000)?", text)
    vals = []
    for n in nums:
        try:
            v = float(n.replace(",", "."))
            if v < 1000:
                v *= 1000  # 60 → 60K
            vals.append(v)
        except Exception:
            pass
    if not vals:
        return None
    # assume USD if $ or unknown → rough conversion to EUR
    if "$" in text or "USD" in text:
        return int(min(vals) * 0.92)
    return int(min(vals))


if __name__ == "__main__":
    jobs = fetch()
    print(f"got {len(jobs)} jobs")
    for j in jobs[:5]:
        print(f"  {j['title'][:50]} @ {j.get('company','')[:20]} | sal={j.get('salary_eur')}")