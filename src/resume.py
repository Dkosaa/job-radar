"""
Resume loader — pulls structured keywords from data/resume_keywords.json
and provides them to the matcher.
"""
import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "data"
RESUME_KEYWORDS = DATA / "resume_keywords.json"


_cached: dict | None = None


def load_resume() -> dict:
    """Load Raj's resume keyword bank from JSON."""
    global _cached
    if _cached is not None:
        return _cached
    if RESUME_KEYWORDS.exists():
        try:
            _cached = json.loads(RESUME_KEYWORDS.read_text())
        except Exception as e:
            print(f"[resume] failed to parse: {e}")
            _cached = {}
    else:
        _cached = {}
    return _cached


def get_tier1_skills() -> list[str]:
    """Highest-priority skills — strong match signal."""
    r = load_resume()
    return r.get("tier1_core_identity", {}).get("skills", [])


def get_tier2_skills() -> list[str]:
    """Domain expertise — medium signal."""
    r = load_resume()
    return r.get("tier2_domain_expertise", {}).get("skills", [])


def get_tier3_skills() -> list[str]:
    """Soft skills / role markers."""
    r = load_resume()
    return r.get("tier3_soft_signals", {}).get("skills", [])


def get_negative_signals() -> list[str]:
    """Skills that should DISQUALIFY a job."""
    r = load_resume()
    return r.get("negative_signals", {}).get("skills", [])


def get_target_roles() -> list[str]:
    """Target role titles to match against."""
    r = load_resume()
    return r.get("target_role_keywords", [])


def get_resume_summary() -> dict:
    """Summary stats for /today header / dashboard."""
    r = load_resume()
    return {
        "title": r.get("title", "Unknown"),
        "years": r.get("experience_years", 0),
        "tier1_count": len(get_tier1_skills()),
        "tier2_count": len(get_tier2_skills()),
        "tier3_count": len(get_tier3_skills()),
        "negative_count": len(get_negative_signals()),
        "target_roles_count": len(get_target_roles()),
    }


if __name__ == "__main__":
    s = get_resume_summary()
    print("Resume summary:")
    for k, v in s.items():
        print(f"  {k}: {v}")