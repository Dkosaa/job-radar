"""
User preferences + filter logic.
Persists to /workspace/job-radar/data/preferences.json so changes survive
across restarts and are shared between dashboard and Telegram bot.
"""
import json
from pathlib import Path
from typing import Any

from config import DATA

PREFS_FILE = DATA / "preferences.json"
DEFAULT_PREFS = {
    "min_salary": 60000,
    "remote_only": False,
    "location": "any",        # any | regensburg | munich | berlin | ...
    "role_keywords": [],      # extra role keywords to filter on
    "exclude_keywords": [],   # words in title/desc that disqualify
    "min_score": 40,
    "sources": ["arbeitnow", "greenhouse", "jobicy", "adzuna"],
}


def load_prefs() -> dict:
    if PREFS_FILE.exists():
        try:
            return {**DEFAULT_PREFS, **json.loads(PREFS_FILE.read_text())}
        except Exception:
            return DEFAULT_PREFS.copy()
    return DEFAULT_PREFS.copy()


def save_prefs(prefs: dict) -> None:
    PREFS_FILE.write_text(json.dumps(prefs, indent=2))


def apply_filters(jobs: list[dict], prefs: dict | None = None) -> list[dict]:
    """Apply user-set filters to a list of scored jobs."""
    if prefs is None:
        prefs = load_prefs()
    out = []
    for j in jobs:
        title = (j.get("title") or "").lower()
        desc = (j.get("description") or "").lower()
        loc = (j.get("location") or "").lower()
        text = title + " " + desc

        # Salary filter
        sal = j.get("salary_eur")
        if sal is not None and sal < prefs["min_salary"]:
            continue

        # Remote-only filter
        if prefs["remote_only"]:
            if not j.get("remote_ok") and "remote" not in loc \
               and "homeoffice" not in loc:
                continue

        # Location filter
        if prefs["location"] != "any":
            loc_filter = prefs["location"].lower()
            if loc_filter not in loc and not j.get("remote_ok"):
                continue

        # Role keywords (any match passes)
        if prefs["role_keywords"]:
            kw_list = [k.lower() for k in prefs["role_keywords"]]
            if not any(k in text for k in kw_list):
                continue

        # Exclude keywords (any match blocks)
        if prefs["exclude_keywords"]:
            ex_list = [k.lower() for k in prefs["exclude_keywords"]]
            if any(k in text for k in ex_list):
                continue

        # Min score filter
        if j.get("score", 0) < prefs["min_score"]:
            continue

        out.append(j)
    return out


def parse_filter_command(arg: str) -> tuple[str, Any] | None:
    """
    Parse 'role=uipath' or 'salary=70' into (key, value).
    Returns None if invalid.
    """
    if "=" not in arg:
        return None
    key, val = arg.split("=", 1)
    key = key.strip().lower()
    val = val.strip()
    if key in {"role", "keyword"}:
        return ("role_keywords_append", val)
    if key in {"exclude", "x"}:
        return ("exclude_keywords_append", val)
    if key in {"salary", "min_salary"}:
        try:
            return ("min_salary", int(val) * 1000)
        except ValueError:
            return None
    if key == "remote":
        return ("remote_only", val.lower() in {"1", "true", "yes", "on"})
    if key == "location":
        return ("location", val.lower())
    if key == "min_score":
        try:
            return ("min_score", int(val))
        except ValueError:
            return None
    return None