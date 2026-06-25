"""
ATS-style matcher.
Takes a normalized job dict and Raj's profile, returns a score + reasons.
"""
import re
from typing import Any

from config import USER_PROFILE


# ──── text utilities ─────────────────────────────────────────────────
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _has(text: str, kw: str) -> bool:
    """Word-boundary match for short keywords, substring for multi-word."""
    if " " in kw or kw.lower() in {"c#", "c++", ".net"}:
        return kw.lower() in text
    return bool(re.search(rf"\b{re.escape(kw.lower())}\b", text))


def _count(text: str, kw: str) -> int:
    if " " in kw or kw.lower() in {"c#", "c++", ".net"}:
        return text.count(kw.lower())
    return len(re.findall(rf"\b{re.escape(kw.lower())}\b", text))


# ──── location rule ──────────────────────────────────────────────────
REGENSBURG_DISTANCE = {
    # rough km from Regensburg — used to decide onsite/hybrid/remote rule
    "regensburg": 0, "nürnberg": 105, "munich": 120, "münchen": 120,
    "augsburg": 175, "ingolstadt": 65, "passau": 145, "landshut": 70,
    "straubing": 40, "amberg": 85, "weiden": 110, "bamberg": 165,
    "erlangen": 115, "fürth": 105, "rosenheim": 200, "freising": 100,
    "berlin": 480, "hamburg": 660, "frankfurt": 320, "köln": 540,
    "düsseldorf": 560, "stuttgart": 290, "leipzig": 330, "dresden": 360,
    "bremen": 640, "hannover": 510, "essen": 560, "dortmund": 560,
    "bonn": 530, "mannheim": 330, "karlsruhe": 360, "freiburg": 420,
    "heidelberg": 310, "mainz": 340, "wiesbaden": 350, "kassel": 380,
    "saarbrücken": 470, "rostock": 720, "kiel": 730, "lübeck": 690,
    "magdeburg": 460, "potsdam": 470, "cottbus": 510, "erfurt": 320,
    "schwerin": 660, "bremerhaven": 680, "oldenburg": 650, "osnabrück": 580,
    "münster": 590, "paderborn": 510, "bielefeld": 550, "detmold": 530,
    "göttingen": 410, "braunschweig": 510, "wolfsburg": 510, "salzgitter": 500,
    "hildesheim": 500, "trier": 540, "koblenz": 470, "giessen": 380,
    "fulda": 340, "marburg": 400, "siegen": 470, "limburg": 410,
    "darmstadt": 320, "offenbach": 320, "hanau": 340, "aschaffenburg": 320,
    "würzburg": 230, "schweinfurt": 200, "coburg": 200, "hof": 230,
    "ansbach": 140, "schwandorf": 50, "cham": 60, "regen": 70,
    "grafenau": 110, "degendorf": 60, "pfarrkirchen": 90, "rottalmünster": 100,
    "waldkirchen": 130, "freystadt": 50, "neumarkt": 60, "parsberg": 40,
    "hemau": 30, "Kelheim": 25, "riedenburg": 35,
}


def location_rule(job: dict) -> tuple[int, str]:
    """
    Returns (score_delta, reason).
    - onsite in Regensburg           → +15
    - hybrid within 200km            → +10
    - remote from anywhere in DE     → +5
    - onsite outside 200km           → -25
    - non-Germany                    → -100 (effectively reject)
    """
    loc = (job.get("location") or "").lower()
    remote = job.get("remote_ok") or "remote" in loc or "homeoffice" in loc
    country = (job.get("country") or "Germany").lower()

    # non-Germany → hard reject
    if country and country not in {"germany", "de", "deutschland", ""}:
        # allow "remote in Germany" only
        if "germany" not in loc and "deutschland" not in loc:
            return -100, f"outside Germany ({country})"

    # detect any German city mentioned
    matched_city = None
    matched_km = None
    for city, km in REGENSBURG_DISTANCE.items():
        if city in loc:
            matched_city, matched_km = city, km
            break

    if remote:
        return 8, "remote (anywhere in DE)"
    if matched_city == "regensburg":
        return 15, "onsite Regensburg"
    if matched_km is not None and matched_km <= 200:
        return 10, f"hybrid ({matched_city}, ~{matched_km}km from Regensburg)"
    if matched_km is not None:
        return -25, f"onsite {matched_city} ({matched_km}km) — too far"
    # city not in our list but country is DE → assume remote/elsewhere
    if country in {"germany", "de", "deutschland"}:
        return 3, "Germany (city unknown — likely remote OK)"
    return 0, "location unclear"


# ──── dealbreakers ───────────────────────────────────────────────────
def dealbreaker_penalties(text: str) -> tuple[int, list[str]]:
    pen, hits = 0, []
    for d in USER_PROFILE["dealbreakers"]:
        if d.lower() in text:
            pen -= 50
            hits.append(d)
    return pen, hits


# ──── salary check ───────────────────────────────────────────────────
def salary_check(job: dict) -> tuple[int, str]:
    sal = job.get("salary_eur")
    if sal is None:
        return 0, "salary not listed"
    if sal >= USER_PROFILE["min_salary_eur"]:
        return 5, f"€{sal:,} ≥ €{USER_PROFILE['min_salary_eur']:,}"
    return -15, f"€{sal:,} below €{USER_PROFILE['min_salary_eur']:,}"


# ──── core scoring ───────────────────────────────────────────────────
def _skill_score(text: str) -> tuple[int, list[str]]:
    """+2 per matched skill keyword, capped at 40."""
    skills = USER_PROFILE["skills"]
    all_kw = []
    for cat in ["rpa", "ai_workflow", "testing", "languages", "devops",
                "process", "management"]:
        all_kw.extend(skills[cat])
    matched = sorted({kw for kw in all_kw if _has(text, kw)})
    score = min(len(matched) * 2, 40)
    return score, matched


def _title_score(text: str) -> tuple[int, list[str]]:
    titles = USER_PROFILE["skills"]["target_titles"]
    # Tier 1: exact fit (RPA / UiPath / Test Automation / etc.) → 12 each
    tier1 = [
        "RPA Developer", "RPA Engineer", "Senior RPA",
        "UiPath Developer", "Power Automate Developer",
        "Test Automation Engineer", "QA Automation Engineer",
        "Process Automation Engineer", "Workflow Automation Engineer",
    ]
    # Tier 2: broader automation roles → 6 each
    tier2 = [
        "Automation Engineer", "Automation Developer",
        "AI Automation", "Intelligent Automation",
        "Process Automation", "Workflow Automation",
        "Flow Automation", "Power Platform Developer",
        "Automation Lead", "Automation Architect",
        "Test Engineer", "QA Engineer", "SDET",
        "Integration Engineer", "Low-Code Developer",
    ]
    # Tier 3: adjacent → 3 each
    tier3 = [
        "Product Owner", "Product Manager", "Workflow Manager",
        "Process Manager", "Transformation Lead",
        "Digital Transformation", "Business Automation",
        "DevOps Engineer", "No-Code Developer",
    ]
    matched = []
    score = 0
    for kw in tier1:
        if _has(text, kw):
            matched.append(kw)
            score += 12
    for kw in tier2:
        if _has(text, kw):
            matched.append(kw)
            score += 6
    for kw in tier3:
        if _has(text, kw):
            matched.append(kw)
            score += 3
    return min(score, 30), sorted(set(matched))


def _language_score(text: str) -> tuple[int, str]:
    if "english" in text and ("german" in text or "deutsch" in text):
        return 3, "EN + DE OK"
    if "english" in text:
        return 2, "English OK"
    if "german" in text or "deutsch" in text:
        if "c1" in text or "c2" in text or "native" in text or "fluent" in text:
            return -10, "requires C1+ German"
        return 1, "German mentioned"
    return 0, "language not specified"


def _cert_score(text: str) -> tuple[int, list[str]]:
    certs = USER_PROFILE["skills"]["certifications"]
    matched = [c for c in certs if _has(text, c)]
    return min(len(matched) * 3, 6), matched


def score_job(job: dict) -> dict:
    """
    Returns:
      {score: 0–100, reasons: [str], matched_skills: [...],
       matched_titles: [...], missing_keywords: [...],
       ats_keywords_to_add: [...]}
    """
    text = _norm(" ".join([
        job.get("title", ""),
        job.get("description", ""),
        job.get("location", ""),
        " ".join(job.get("tags") or []),
    ]))

    title_score, titles = _title_score(text)
    skill_score, skills = _skill_score(text)
    lang_score, lang_msg = _language_score(text)
    cert_score, certs = _cert_score(text)
    loc_score, loc_msg = location_rule(job)
    sal_score, sal_msg = salary_check(job)
    pen, deal_hits = dealbreaker_penalties(text)

    total = (
        title_score + skill_score + lang_score
        + cert_score + loc_score + sal_score + pen
    )
    total = max(0, min(100, total + 30))  # baseline 30 to avoid negatives

    # ── ATS keyword suggestions ──────────────────────────────────────
    # All keywords Raj's profile has that the JD doesn't mention.
    all_profile_kw = []
    for cat in ["rpa", "ai_workflow", "testing", "languages", "devops",
                "process", "management", "certifications"]:
        all_profile_kw.extend(USER_PROFILE["skills"][cat])
    # also JD keywords that aren't in Raj's profile (to add to resume)
    jd_keywords = _extract_jd_keywords(text)
    missing_from_jd = [k for k in all_profile_kw if not _has(text, k)][:8]
    jd_needs = [k for k in jd_keywords if not _has(text, k.lower())][:8]
    # combine: prefer "Raj has but JD lacks" + "JD wants but Raj doesn't have"
    ats_keywords = (missing_from_jd + jd_needs)[:10]

    reasons = [
        f"+{title_score} title match ({', '.join(titles) or 'none'})",
        f"+{skill_score} skills ({len(skills)} matched)",
        f"+{lang_score} {lang_msg}",
        f"+{cert_score} certs ({', '.join(certs) or 'none'})",
        f"{loc_score:+} location — {loc_msg}",
        f"{sal_score:+} salary — {sal_msg}",
    ]
    if deal_hits:
        reasons.append(f"{pen:+} dealbreaker: {', '.join(deal_hits)}")

    return {
        "score": total,
        "reasons": reasons,
        "matched_skills": skills,
        "matched_titles": titles,
        "matched_certs": certs,
        "ats_keywords_to_add": ats_keywords,
    }


# ──── JD keyword extraction ──────────────────────────────────────────
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "can", "could", "may", "might", "must", "shall",
    "you", "your", "we", "our", "us", "they", "their", "them", "i", "me",
    "my", "this", "that", "these", "those", "it", "its", "if", "then",
    "than", "so", "such", "not", "no", "yes", "any", "all", "some",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "experience", "work", "working", "team", "teams", "company",
    "role", "position", "candidate", "requirements", "required",
    "responsibilities", "qualifications", "skills", "knowledge",
    "plus", "strong", "good", "great", "excellent", "familiar",
    "understanding", "ability", "able", "etc", "e.g", "i.e",
    "years", "year", "month", "months", "day", "days", "ago",
    "germany", "german", "english", "remote", "hybrid", "onsite",
    "full", "part", "time", "times", "job", "jobs",
    "using", "used", "use", "like", "also", "well", "within",
}


def _extract_jd_keywords(text: str, top_n: int = 30) -> list[str]:
    """Pull likely skill / tool / concept keywords from a JD."""
    # normalize
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,}", text)
    # bigrams for things like "machine learning"
    bigrams = []
    toks = [t for t in raw_tokens]
    for i in range(len(toks) - 1):
        if (toks[i].lower() not in _STOPWORDS
                and toks[i + 1].lower() not in _STOPWORDS):
            bigrams.append(f"{toks[i]} {toks[i+1]}")
    # known tech / tool whitelist (curated)
    whitelist = {
        "python", "java", "javascript", "typescript", "c#", ".net", "c++",
        "go", "rust", "ruby", "php", "scala", "kotlin", "swift",
        "react", "vue", "angular", "svelte", "next.js", "nuxt",
        "node", "node.js", "django", "flask", "fastapi", "spring",
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "jenkins", "github actions", "gitlab", "circleci", "argo",
        "postgresql", "mysql", "mongodb", "redis", "kafka", "elasticsearch",
        "graphql", "rest", "grpc", "soap", "kafka", "rabbitmq",
        "uipath", "blue prism", "automation anywhere", "power automate",
        "power platform", "power bi", "power apps", "power fx",
        "selenium", "cypress", "playwright", "jmeter", "postman",
        "restassured", "swagger", "appium", "jira", "confluence",
        "n8n", "zapier", "make", "airflow", "prefect", "dagster",
        "llm", "rag", "langchain", "llamaindex", "openai", "anthropic",
        "machine learning", "deep learning", "nlp", "computer vision",
        "agile", "scrum", "kanban", "safe", "itil", "bpmn",
        "sap", "salesforce", "servicenow", "workday", "oracle",
        "ci/cd", "devops", "mlops", "sre", "tdd", "bdd",
        "api", "apis", "sdk", "etl", "elt", "sql", "nosql",
        "german", "english", "b1", "b2", "c1",
        "finance", "hr", "operations", "procurement", "logistics",
        "shared services", "bpo", "shared service", "rpa",
        "robotic process automation", "process automation",
        "workflow automation", "intelligent automation",
        "hyperautomation", "process mining", "celonis",
    }
    found = []
    seen = set()
    for w in (raw_tokens + bigrams):
        wl = w.lower()
        if wl in whitelist and wl not in seen:
            seen.add(wl)
            found.append(w)
        if len(found) >= top_n:
            break
    return found