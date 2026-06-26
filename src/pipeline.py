"""
Pipeline orchestrator:
  fetch → normalize → dedupe → match → rank → write digest
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import (
    PIPELINE, SOURCES, USER_PROFILE, SEEN_FILE, DIGESTS_DIR
)
from matcher import score_job


def load_seen() -> dict[str, float]:
    """Returns {job_id: first_seen_timestamp}."""
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            if isinstance(data, list):  # legacy format
                return {jid: 0.0 for jid in data}
            return data
        except Exception:
            return {}
    return {}


def save_seen(seen: dict[str, float]) -> None:
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def dedupe(jobs: list[dict]) -> list[dict]:
    """Drop jobs we've already shown in a previous digest,
    BUT resurface them if they've been unseen for >= seen_resurfacing_days
    AND are still within freshness window."""
    import time as _t
    seen = load_seen()
    now = _t.time()
    resurface_seconds = PIPELINE.get("seen_resurfacing_days", 7) * 86400

    out = []
    new_ids: dict[str, float] = {}
    for j in jobs:
        jid = j["id"]
        url_key = (j.get("url") or "").split("?")[0]
        if jid in seen:
            age = now - seen[jid]
            if age < resurface_seconds:
                continue  # recently seen, skip
            # else: resurfacing — let through
        # also dedupe by url within current batch
        if url_key and url_key in {s.get("url", "").split("?")[0]
                                    for s in out if s.get("url")}:
            continue
        out.append(j)
        new_ids[jid] = now

    # update seen with newest first-seen time (keep oldest)
    for jid, ts in new_ids.items():
        if jid not in seen:  # only set first-seen time
            seen[jid] = ts

    # garbage-collect seen entries older than 60d to bound file size
    cutoff = now - 60 * 86400
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    save_seen(seen)
    return out


def fetch_all() -> list[dict]:
    """Fetch from all enabled sources. Per-source failures don't break the run."""
    from sources import arbeitnow, greenhouse, lever, jobicy, adzuna, remotive

    all_jobs: list[dict] = []
    if SOURCES["arbeitnow"]["enabled"]:
        all_jobs.extend(arbeitnow.fetch(PIPELINE["fetch_timeout_sec"]))
    if SOURCES["greenhouse"]["enabled"]:
        all_jobs.extend(greenhouse.fetch(PIPELINE["fetch_timeout_sec"]))
    if SOURCES["lever"]["enabled"]:
        all_jobs.extend(lever.fetch(PIPELINE["fetch_timeout_sec"]))
    if SOURCES["jobicy"]["enabled"]:
        all_jobs.extend(jobicy.fetch(PIPELINE["fetch_timeout_sec"]))
    if SOURCES["adzuna"]["enabled"]:
        try:
            all_jobs.extend(adzuna.fetch(PIPELINE["fetch_timeout_sec"]))
        except Exception as e:
            print(f"[adzuna] skipped: {e}")
    if SOURCES["remotive"]["enabled"]:
        try:
            all_jobs.extend(remotive.fetch(PIPELINE["fetch_timeout_sec"]))
        except Exception as e:
            print(f"[remotive] skipped: {e}")
    if SOURCES["stepstone"]["enabled"]:
        try:
            from sources.stepstone import fetch as ss_fetch
            all_jobs.extend(ss_fetch())
        except Exception as e:
            print(f"[stepstone] skipped: {e}")
    if SOURCES["indeed_de"]["enabled"]:
        try:
            from sources.indeed_de import fetch as ind_fetch
            all_jobs.extend(ind_fetch())
        except Exception as e:
            print(f"[indeed_de] skipped: {e}")
    return all_jobs


def _age_hours(job: dict) -> int | None:
    raw = job.get("_age_hours")
    if raw is not None:
        return int(raw)
    posted = job.get("posted_at")
    if posted is None:
        return None
    try:
        if isinstance(posted, (int, float)):
            dt = datetime.fromtimestamp(posted, tz=timezone.utc)
        else:
            # ISO-ish string (Adzuna uses "2026-06-24T12:34:56Z")
            s = str(posted).strip()
            # Handle "Thu, 25 Jun 2026 09:00:00 GMT" etc
            for fmt in ("%Y-%m-%dT%H:%M:%SZ",
                        "%a, %d %b %Y %H:%M:%S %Z",
                        "%a, %d %b %Y %H:%M:%S GMT",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(s, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            else:
                # last resort: fromisoformat
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - dt).total_seconds() // 3600)
    except Exception:
        return None


def filter_jobs(jobs: list[dict], hours: int | None = None,
                strict_freshness: bool = True) -> list[dict]:
    """
    Filter by DE / freshness / minimum viability.
    strict_freshness=True: drop jobs with unknown age (most APIs don't expose
        reliable timestamps, so defaulting to 'unknown = fresh' caused 697h-old
        jobs in the digest).
    strict_freshness=False: keep unknown-age jobs (used for /global / historical).
    """
    if hours is None:
        hours = PIPELINE["freshness_hours"]

    out = []
    for j in jobs:
        # Country filter: must be Germany-tagged OR contain DE city
        loc = (j.get("location") or "").lower()
        country = (j.get("country") or "").lower()
        title = (j.get("title") or "").lower()
        text = loc + " " + country + " " + title

        # Hard-exclude non-DE roles. Be aggressive because Greenhouse often
        # has US/UK/international roles that mention Germany in a
        # different context. We want STRICT DE focus.
        NON_DE_MARKERS = [
            "united states", "usa", " u.s.", "us only", "us-based",
            "us-", ", us", " us)", "(us)",
            "united kingdom", ", uk", "(uk)", " uk)", "london", "manchester",
            "france", "paris", "lyon", "spain", "madrid", "barcelona",
            "italy", "milan", "rome", "poland", "warsaw", "krakow",
            "netherlands", "amsterdam", "rotterdam",
            "switzerland", "zurich", "geneva", "bern",
            "austria", "vienna", "wien",
            "india", "mumbai", "bangalore", "bengaluru", "delhi", "hyderabad",
            "israel", "tel aviv", "japan", "tokyo", "singapore",
            "australia", "sydney", "melbourne", "canada", "toronto", "vancouver",
            "mexico", "brazil", "sao paulo", "argentina", "chile",
            "south korea", "seoul", "china", "shanghai", "beijing",
            "new york", "nyc", "san francisco", "los angeles", "chicago",
            "boston", "seattle", "austin", "denver", "atlanta", "miami",
            "washington dc", "washington, dc",
            "derby", "england",
        ]
        if any(m in text for m in NON_DE_MARKERS):
            # but allow ONLY if an explicit German city/country is also present
            de_explicit = any(g in text for g in [
                "germany", "deutschland", "berlin", "munich", "münchen",
                "hamburg", "frankfurt", "regensburg", "nürnberg", "stuttgart",
                "köln", "cologne", "düsseldorf", "leipzig", "dresden",
                "magdeburg", "munster", "rostock",
            ])
            if not de_explicit:
                continue

        is_de = (
            country in {"germany", "de", "deutschland"}
            or any(c in text for c in [
                "germany", "deutschland", "berlin", "munich", "münchen",
                "hamburg", "frankfurt", "regensburg", "nürnberg",
                "stuttgart", "köln", "cologne", "düsseldorf", "leipzig",
                "dresden", "magdeburg", "bavaria", "bayern",
                "nrw", "nordrhein", "hessen", "baden-württemberg",
                "bremen", "hannover", "dortmund", "essen", "bonn",
                "mannheim", "karlsruhe", "freiburg", "heidelberg",
                "mainz", "wiesbaden", "kassel", "rostock", "kiel",
                "paderborn", "bielefeld", "oldenburg", "osnabrück",
                "trier", "koblenz", "würzburg", "schweinfurt",
                "ansbach", "schwandorf", "cham", "kelheim", "hemau",
                "neumarkt", "parsberg", "remote", "homeoffice",
            ])
        )
        if not is_de:
            continue

        # Freshness — strict mode drops unknown-age jobs
        age = _age_hours(j)
        if age is None:
            if strict_freshness:
                # Adzuna + Greenhouse usually have no timestamp; we let those
                # through because their content is fresh by API design.
                # Arbeitnow always has unix timestamp, so it gets dropped if missing.
                if j.get("source") in ("arbeitnow",):
                    continue
                # others: assume recent (let through) but flag
                j["_age_estimated"] = True
            # if not strict, let through
        else:
            if age > max(hours, PIPELINE["max_age_days"] * 24):
                continue

        # Must contain at least one automation / testing / process keyword
        all_kw = []
        for cat in ["rpa", "ai_workflow", "testing", "languages", "devops",
                    "process", "management"]:
            all_kw.extend(USER_PROFILE["skills"][cat])
        title_desc = (j.get("title", "") + " " + j.get("description", "")
                      + " " + " ".join(j.get("tags") or []))
        if not any(kw.lower() in title_desc.lower() for kw in all_kw):
            # even if no kw, allow if title itself looks target-ish
            if not any(t.lower() in title_desc.lower()
                       for t in USER_PROFILE["skills"]["target_titles"]):
                continue

        out.append(j)
    return out


def rank_jobs(jobs: list[dict]) -> list[dict]:
    """Score + sort + attach match metadata.
    Sort priority:
      1. Higher score first
      2. Known-recent first (unknown-age jobs sink to bottom)
      3. Among known-age, newer first
    """
    scored = []
    for j in jobs:
        age = _age_hours(j)
        m = score_job(j)
        scored.append({**j, **m, "_age_hours": age})
    scored.sort(key=lambda x: (
        -x["score"],                           # higher score first
        0 if x.get("_age_hours") is not None else 1,  # known-age first
        x.get("_age_hours") if x.get("_age_hours") is not None else 9999,
    ))
    return scored


def run(hours: int | None = None,
        top_n: int | None = None,
        global_search: bool = False) -> dict:
    """
    Main entry. Returns digest dict + writes to data/digests/<date>.json
    """
    hours = hours or PIPELINE["freshness_hours"]
    top_n = top_n or PIPELINE["top_n"]

    print(f"[pipeline] starting scan (window={hours}h, top_n={top_n}, "
          f"global={global_search})")
    raw = fetch_all()
    print(f"[pipeline] fetched {len(raw)} jobs across sources")

    if not global_search:
        filtered = filter_jobs(raw, hours=hours, strict_freshness=True)
    else:
        filtered = raw  # skip DE filter
    print(f"[pipeline] after filter: {len(filtered)}")

    fresh = dedupe(filtered)
    print(f"[pipeline] after dedupe (already-seen removed): {len(fresh)}")

    ranked = rank_jobs(fresh)
    top = [j for j in ranked if j["score"] >= PIPELINE["min_score"]][:top_n]
    print(f"[pipeline] top {len(top)} (score >= {PIPELINE['min_score']}):")

    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "global_search": global_search,
        "counts": {
            "fetched": len(raw),
            "filtered": len(filtered),
            "fresh": len(fresh),
            "delivered": len(top),
        },
        "jobs": top,
    }

    # write digest file (one per day)
    fname = DIGESTS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    fname.write_text(json.dumps(digest, indent=2, ensure_ascii=False))
    # also write "latest"
    (DIGESTS_DIR / "latest.json").write_text(
        json.dumps(digest, indent=2, ensure_ascii=False)
    )
    print(f"[pipeline] digest written → {fname.name}")
    return digest


if __name__ == "__main__":
    run()