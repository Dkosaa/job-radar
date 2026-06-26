"""
ATS-style matcher — rebuilt to be HONEST about fit.

Two key fixes vs the old version:
1. ATS keyword suggestions now correctly point to skills the JD wants
   that you DON'T already have — not skills you have that the JD doesn't mention.
2. Score baseline removed; only strong matches get high scores.
"""
import re
from typing import Any

from config import USER_PROFILE
from resume import (
    get_tier1_skills, get_tier2_skills, get_tier3_skills,
    get_negative_signals, get_target_roles,
)


# ──── text utilities ─────────────────────────────────────────────────
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _has(text: str, kw: str) -> bool:
    """Word-boundary match for short keywords, substring for multi-word."""
    if " " in kw or kw.lower() in {"c#", "c++", ".net"}:
        return kw.lower() in text
    return bool(re.search(rf"\b{re.escape(kw.lower())}\b", text))


# ──── ALL known skills/tools (used for keyword extraction) ───────────
# This is what an ATS scanner looks for in a JD. If your resume mentions
# these, you get screened IN. If the JD asks for them and you don't have
# them, you get screened OUT.
KNOWN_TECH = {
    # RPA / Automation platforms
    "uipath", "blue prism", "automation anywhere", "power automate",
    "power platform", "power apps", "power bi", "power fx",
    "workfusion", "kofax", "nice", "automationedge",
    "rpa", "robotic process automation", "intelligent automation",
    "hyperautomation", "process automation", "workflow automation",
    "robotic", "bot", "attended bot", "unattended bot",
    "orchestrator", "orchestration",
    # AI / ML workflow
    "n8n", "zapier", "make", "ifttt", "airflow", "prefect", "dagster",
    "llm", "rag", "langchain", "llamaindex", "openai", "anthropic",
    "claude", "gpt", "chatgpt", "copilot", "prompt engineering",
    "machine learning", "deep learning", "nlp", "computer vision",
    "mlops", "ai workflow", "agentic",
    # Testing tools
    "selenium", "selenium webdriver", "cypress", "playwright",
    "jmeter", "postman", "restassured", "swagger", "soapui",
    "appium", "katalon", "testcomplete", "ranorex", "tosca",
    "cucumber", "specflow", "robot framework", "testng", "junit",
    "pytest", "mocha", "jest", "xunit",
    "api testing", "rest api", "graphql", "grpc",
    "regression testing", "smoke testing", "uat", "sit",
    "test automation", "qa automation", "sdet",
    # Programming languages
    "python", "java", "javascript", "typescript", "c#", ".net",
    "c++", "go", "rust", "ruby", "php", "scala", "kotlin", "swift",
    "vb.net", "vba", "sql", "pl/sql", "t-sql",
    # Frameworks
    "react", "vue", "angular", "svelte", "next.js", "nuxt",
    "django", "flask", "fastapi", "spring", "spring boot",
    "express", "node.js", "nodejs",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google cloud",
    "kubernetes", "k8s", "docker", "terraform", "ansible",
    "jenkins", "github actions", "gitlab ci", "circleci", "argo",
    "ci/cd", "devops", "sre", "tdd", "bdd",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "kafka",
    "elasticsearch", "dynamodb", "snowflake", "bigquery",
    # ERPs / enterprise
    "sap", "sap fiori", "salesforce", "servicenow", "workday",
    "oracle", "netsuite",
    # Process / management
    "bpmn", "uml", "lean", "six sigma", "agile", "scrum",
    "kanban", "safe", "itil", "pmp", "prince2",
    "process mining", "celonis", "signavio",
    "jira", "confluence", "azure devops",
    "pdds", "sdds", "process design",
    # Soft / role
    "stakeholder management", "governance", "compliance",
    "gdpr", "sox", "audit", "code review", "mentoring",
    "product owner", "product manager", "scrum master",
    # Languages
    "english", "german", "deutsch", "b1", "b2", "c1", "c2",
}


# Raj's profile — what he ALREADY has (used to filter out "add to resume")
# Built dynamically from resume data + config
RAJ_HAS = set()
for cat in ["rpa", "ai_workflow", "testing", "languages", "devops",
            "process", "management", "certifications"]:
    RAJ_HAS.update(k.lower() for k in USER_PROFILE["skills"][cat])
# Add explicit tools/keywords from his resume
RAJ_HAS.update({
    "uipath", "orchestrator", "blue prism", "power automate", "power bi",
    "n8n", "zapier", "make", "selenium webdriver", "postman", "jmeter",
    "cypress", "restassured", "swagger", "soapui", "appium",
    "python", "java", "c#", "vb.net", "sql", "vba",
    "git", "docker", "github actions", "linux", "windows",
    "jira", "confluence", "bpmn", "lean", "scrum",
    "rpa", "robotic process automation", "process automation",
    "workflow automation", "intelligent automation",
    "shared services", "finance", "hr", "operations",
    "english", "german", "b1",
    "uipath advanced", "istqb",
    "hp alm", "swagger ui", "vb.net", "vba macros",
    "test automation frameworks", "regression testing",
    "functional testing", "integration testing", "system testing",
    "uat", "smoke testing", "sanity testing",
    "test cases", "test plans", "traceability matrix", "defect reports",
    "api testing", "rest api",
})


# ──── location rule ──────────────────────────────────────────────────
REGENSBURG_DISTANCE = {
    "regensburg": 0, "nürnberg": 105, "munich": 120, "münchen": 120,
    "augsburg": 175, "ingolstadt": 65, "passau": 145, "landshut": 70,
    "straubing": 40, "amberg": 85, "weiden": 110, "bamberg": 165,
    "erlangen": 115, "fürth": 105, "rosenheim": 200, "freising": 100,
    "berlin": 480, "hamburg": 660, "frankfurt": 320, "köln": 540,
    "düsseldorf": 560, "stuttgart": 290, "leipzig": 330, "dresden": 360,
    "bremen": 640, "hannover": 510, "essen": 560, "dortmund": 560,
    "bonn": 530, "mannheim": 330, "karlsruhe": 360, "freiburg": 420,
    "heidelberg": 310, "mainz": 340, "wiesbaden": 350, "kassel": 380,
    "würzburg": 230, "schwandorf": 50, "cham": 60, "kelheim": 25,
}


def location_rule(job: dict) -> tuple[int, str]:
    """
    Raj's location rule (strict):
      - onsite Regensburg              → +20
      - hybrid within 200km of Regens. → +15
      - remote anywhere in DE          → +8
      - onsite > 200km in DE           → -50 (effectively reject)
      - outside Germany                → -100 (reject)
    """
    loc = (job.get("location") or "").lower()
    remote = bool(job.get("remote_ok")) or "remote" in loc \
             or "homeoffice" in loc or "deutschlandweit" in loc
    country = (job.get("country") or "").lower()

    # Non-Germany hard reject (unless remote-only Germany-eligible)
    if country and country not in {"germany", "de", "deutschland", "remote"}:
        if "germany" not in loc and "deutschland" not in loc:
            return -100, f"outside Germany ({country})"

    matched_city = None
    matched_km = None
    for city, km in REGENSBURG_DISTANCE.items():
        if city in loc:
            matched_city, matched_km = city, km
            break

    if remote:
        return 12, "remote (DE-eligible)"
    if matched_city == "regensburg":
        return 20, "onsite Regensburg"
    if matched_km is not None and matched_km <= 200:
        return 15, f"hybrid ({matched_city}, ~{matched_km}km from Regensburg)"
    if matched_km is not None:
        return -50, f"onsite {matched_city} ({matched_km}km) — too far"
    if country in {"germany", "de", "deutschland"}:
        return 5, "Germany (city unknown)"
    return 0, "location unclear"


# ──── dealbreakers ───────────────────────────────────────────────────
def dealbreaker_penalties(text: str) -> tuple[int, list[str]]:
    pen, hits = 0, []
    # User-set dealbreakers (e.g., sponsorship, C2 German)
    for d in USER_PROFILE["dealbreakers"]:
        if d.lower() in text:
            pen -= 50
            hits.append(d)
    # Negative signals from resume (wrong-domain skills)
    for neg in get_negative_signals():
        if _has(text, neg):
            pen -= 15
            hits.append(f"wrong-domain: {neg}")
    return pen, hits


# ──── salary check ───────────────────────────────────────────────────
def salary_check(job: dict) -> tuple[int, str]:
    sal = job.get("salary_eur")
    if sal is None:
        return 0, "salary not listed"
    if sal >= USER_PROFILE["min_salary_eur"]:
        return 8, f"€{sal:,} ≥ €{USER_PROFILE['min_salary_eur']:,}"
    gap = (USER_PROFILE["min_salary_eur"] - sal) / 1000
    return -int(gap / 2), f"€{sal:,} below €{USER_PROFILE['min_salary_eur']:,}"


# ──── core scoring (rewritten, honest) ──────────────────────────────
def _title_score(text: str) -> tuple[int, list[str]]:
    """Tiered title scoring using Raj's resume target roles.
    Tier 1 = strong fit (12 pts), tier 2 = medium (6 pts), tier 3 = adjacent (3 pts)."""
    target_roles = [r.lower() for r in get_target_roles()]

    # Classify each target role by strength of fit
    tier1_roles = [
        "rpa developer", "rpa engineer", "senior rpa",
        "uipath developer", "power automate developer",
        "test automation engineer", "qa automation engineer",
        "process automation engineer", "workflow automation engineer",
        "automation architect", "automation lead",
        "intelligent automation engineer",
        "robotic process automation developer",
        "blue prism developer", "automation anywhere developer",
        "sdet", "quality engineer",
    ]
    tier2_roles = [
        "automation engineer", "automation developer",
        "ai automation", "process automation", "workflow automation",
        "flow automation", "power platform developer",
        "test engineer", "qa engineer",
        "integration engineer", "low-code developer",
    ]
    tier3_roles = [
        "product owner", "product manager", "workflow manager",
        "process manager", "transformation lead",
        "digital transformation", "business automation",
        "devops engineer", "no-code developer",
    ]

    matched, score = [], 0
    for kw in tier1_roles:
        if _has(text, kw):
            matched.append(kw); score += 12
    for kw in tier2_roles:
        if _has(text, kw):
            matched.append(kw); score += 6
    for kw in tier3_roles:
        if _has(text, kw):
            matched.append(kw); score += 3
    return min(score, 30), sorted(set(matched))


def _skill_score(text: str) -> tuple[int, list[str]]:
    """Skill scoring using resume tiered keywords.
    Tier 1 (core identity): +4 each
    Tier 2 (domain):       +2 each
    Tier 3 (soft signals): +1 each
    Capped at 35."""
    t1 = {s.lower() for s in get_tier1_skills()}
    t2 = {s.lower() for s in get_tier2_skills()}
    t3 = {s.lower() for s in get_tier3_skills()}

    matched = []
    score = 0
    # Tier 1 — strong signals
    for kw in t1:
        if _has(text, kw):
            matched.append(kw); score += 4
    # Tier 2 — domain skills
    for kw in t2:
        if _has(text, kw):
            matched.append(kw); score += 2
    # Tier 3 — soft signals (less weight)
    for kw in t3:
        if _has(text, kw):
            matched.append(kw); score += 1
    return min(score, 35), matched


def _language_score(text: str) -> tuple[int, str]:
    if "english" in text and ("german" in text or "deutsch" in text):
        return 5, "EN + DE OK"
    if "english" in text:
        return 4, "English OK"
    if "german" in text or "deutsch" in text:
        if "c1" in text or "c2" in text or "native" in text \
                or "verhandlungssicher" in text:
            return -25, "requires C1+/fluent German"
        return 2, "German mentioned"
    return 0, "language not specified"


def _cert_score(text: str) -> tuple[int, list[str]]:
    certs = USER_PROFILE["skills"]["certifications"]
    matched = [c for c in certs if _has(text, c)]
    return min(len(matched) * 4, 8), matched


# ──── ATS keyword extraction (FIXED) ─────────────────────────────────
def _extract_ats_keywords(text: str, top_n: int = 8) -> list[str]:
    """
    Returns skills the JD wants that Raj does NOT already have.

    This is what should go in a "Add to your resume" suggestion:
    if the JD mentions a tool Raj doesn't know, he should consider
    adding a related cert/skill to his resume OR upskilling.

    Filter logic:
      1. Find all KNOWN_TECH keywords in the JD
      2. Drop ones Raj already has (so we don't suggest UiPath to a UiPath dev)
      3. Rank by frequency in JD (more mentioned = more important)
    """
    found_counts: dict[str, int] = {}
    for kw in KNOWN_TECH:
        if _has(text, kw):
            # count frequency
            if " " in kw:
                count = text.count(kw)
            else:
                count = len(re.findall(rf"\b{re.escape(kw)}\b", text))
            if count > 0:
                found_counts[kw] = count

    # Filter out what Raj already has
    new_for_raj = {kw: cnt for kw, cnt in found_counts.items()
                   if kw not in RAJ_HAS}
    # Sort by frequency (most-mentioned first)
    ranked = sorted(new_for_raj.items(), key=lambda x: -x[1])
    return [kw for kw, _ in ranked[:top_n]]


# ──── main scorer ────────────────────────────────────────────────────
def score_job(job: dict) -> dict:
    """
    Returns score, reasons, matched skills/titles, ats_keywords_to_add.

    Scoring (max ~100):
      - Title match: up to 30
      - Skill match: up to 35
      - Cert: up to 8
      - Language: -25..+5
      - Location: -100..+20
      - Salary: -15..+8
      - Dealbreakers: -50 each
    NO baseline. Honest scoring.
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

    total = (title_score + skill_score + lang_score
             + cert_score + loc_score + sal_score + pen)
    total = max(0, min(100, total))

    # ATS keywords = skills the JD wants that Raj DOESN'T have
    ats_keywords = _extract_ats_keywords(text, top_n=8)

    reasons = [
        f"+{title_score} title ({', '.join(titles) or 'none'})",
        f"+{skill_score} skills ({len(skills)} matched)",
        f"{lang_score:+} {lang_msg}",
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