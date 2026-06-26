"""
Job Radar — Central Config
All user-facing knobs live here. Edit this file to tweak behavior without
touching the pipeline.
"""
import os
from pathlib import Path

# Load .env if present (no-op if missing)
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────
#  User profile (Raj Sakhiya)
# ──────────────────────────────────────────────────────────────────────
USER_PROFILE = {
    "name": "Raj Sakhiya",
    "title": "Robotics Process Automation Developer",
    "years_experience": 7,
    "min_salary_eur": 60000,
    "preferred_locations": {
        "regensburg": {"mode": "onsite", "km_radius": 0},
        "near_regensburg": {"mode": "hybrid", "km_radius": 200},
        "rest_of_germany": {"mode": "remote_only"},
    },
    "languages": {"English": "fluent", "German": "B1"},
    "work_visa": True,  # no sponsorship filter
    "availability": "immediate",
    # ATS keyword bank — built from resume, used for matching AND for
    # generating "keywords to add" suggestions on each JD.
    "skills": {
        # core automation
        "rpa": ["UiPath", "Orchestrator", "Blue Prism", "Power Automate",
                "Power BI", "RPA", "Robotic Process Automation"],
        "ai_workflow": ["n8n", "Zapier", "Make", "AI Workflow", "LLM",
                        "Intelligent Automation", "Hyperautomation"],
        "testing": ["Selenium WebDriver", "Postman", "JMeter", "Cypress",
                    "Appium", "API Testing", "RestAssured", "Swagger",
                    "SoapUI", "Regression Testing", "UAT", "SIT"],
        "languages": ["C#", "Python", "Java", "VB.NET", "SQL", "VBA",
                      "VBA Macros"],
        "devops": ["Git", "Docker", "GitHub Actions", "CI/CD"],
        "os": ["Linux", "Windows"],
        "process": ["BPMN", "Lean", "Process Discovery", "PDD", "SDD",
                    "Process Optimization", "Shared Services",
                    "Finance Automation", "HR Automation"],
        "management": ["Agile", "Scrum", "Jira", "Confluence",
                       "Stakeholder Management", "Governance", "GDPR",
                       "Code Review", "Mentoring", "Backlog Prioritization"],
        "certifications": ["UiPath Advanced (UiARD)", "ISTQB Foundation"],
        # target roles — STRICT: only true fit. Raj wants quality over quantity.
        "target_titles": [
            # Tier 1: pure RPA / automation fit
            "RPA Developer", "RPA Engineer", "Senior RPA",
            "UiPath Developer", "Power Automate Developer",
            "Robotic Process Automation Developer",
            "Blue Prism Developer", "Automation Anywhere Developer",
            "Process Automation Engineer", "Workflow Automation Engineer",
            "Test Automation Engineer", "QA Automation Engineer",
            "Intelligent Automation Engineer", "Automation Architect",
            "Automation Lead", "Power Platform Developer",
            # Tier 2: broader automation roles (still a fit)
            "Automation Engineer", "Automation Developer",
            "AI Automation", "Intelligent Automation",
            "Process Automation", "Workflow Automation",
            "Flow Automation", "Test Engineer", "QA Engineer", "SDET",
            # Tier 3: adjacent (only if JD also mentions automation keywords)
            "Product Owner", "Product Manager",
            "Integration Engineer", "DevOps Engineer",
            "Low-Code Developer", "No-Code Developer",
        ],
    },
    # explicit dealbreakers (rejected if matched)
    "dealbreakers": [
        "unpaid", "internship only", "working student only",
        "sponsorship required", "no relocation support",
        "must have C2 German", "must have native German",
    ],
}


# ──────────────────────────────────────────────────────────────────────
#  Pipeline behavior
# ──────────────────────────────────────────────────────────────────────
PIPELINE = {
    "freshness_hours": 24,       # default window
    "top_n": 10,                 # jobs per digest
    "min_score": 30,             # loose to allow realistic market matches
    "max_age_days": 7,           # last week max
    "seen_resurfacing_days": 3,  # resurface same job after 3 days if still fresh
    "fetch_timeout_sec": 20,
    # Strict keyword filter (RPA/UiPath/BluePrism/Power Automate must appear
    # in JD). Apify source applies this automatically. Set to True to also
    # apply it to free sources (Arbeitnow/Greenhouse/etc).
    "strict_filter_all": False,
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


# ──────────────────────────────────────────────────────────────────────
#  Job sources
# ──────────────────────────────────────────────────────────────────────
# Apify (paid scraper API) — defined here so SOURCES can reference it
APIFY = {
    "enabled": bool(os.environ.get("APIFY_API_TOKEN", "")),
    "token": os.environ.get("APIFY_API_TOKEN", ""),
    "monthly_budget_usd": 5.0,
}

SOURCES = {
    "arbeitnow": {"enabled": True, "label": "Arbeitnow"},
    "greenhouse": {"enabled": True, "label": "Greenhouse (DE tech)"},
    "lever":      {"enabled": True, "label": "Lever"},
    "jobicy":    {"enabled": True, "label": "Jobicy (remote, EU-friendly)"},
    "adzuna":     {"enabled": True, "label": "Adzuna DE (StepStone/Indeed aggregator, 250/month)"},
    "remotive":   {"enabled": True, "label": "Remotive (tech remote jobs)"},
    # Apify is conditional — only enabled if APIFY_API_TOKEN is set in env
    "apify_indeed":   {"enabled": APIFY.get("enabled", False),
                       "label": "Apify Indeed scraper ($5/mo budget)"},
    "apify_stepstone":{"enabled": APIFY.get("enabled", False),
                       "label": "Apify StepStone scraper ($5/mo budget)"},
    # The following are blocked / require direct access:
    "stepstone":  {"enabled": False, "label": "StepStone direct (Cloudflare captcha)"},
    "indeed_de":  {"enabled": False, "label": "Indeed DE direct (Cloudflare captcha)"},
    "xing":       {"enabled": False, "label": "XING (JS-rendered, login required)"},
    "kimeta":     {"enabled": False, "label": "Kimeta (JS-rendered)"},
    "honeypot":   {"enabled": False, "label": "Honeypot (premium partner only)"},
    "linkedin":   {"enabled": False, "label": "LinkedIn (anti-bot, or via Apify $5/mo)"},
    "glassdoor":  {"enabled": False, "label": "Glassdoor (anti-bot)"},
}

# Greenhouse + Lever: German tech companies that post publicly
COMPANY_BOARDS = {
    "greenhouse": [
        # === German RPA / automation hirers ===
        "schneiderelectric", "altengmbh", "alten",  # Schneider, Alten — big RPA consultancies in DE
        # === Major DE tech companies (verified active Greenhouse boards) ===
        "n26",          # 38 DE jobs — Berlin mobile bank
        "celonis",      # 37 DE — Munich, process mining leader
        "sumup",        # 85 DE — payments, lots of automation roles
        "traderepublic",# 1 DE — Berlin fintech
        "raisin",       # 33 DE — Berlin fintech
        "doctolib",     # 61 DE — telehealth
        "contentful",   # 7 DE — Berlin/DEN content platform
        "flaconi",     # 13 DE — Berlin beauty e-com
        "wolt",        # 74 DE — Berlin delivery
        "hellofresh",  # 77 DE — Berlin food delivery
        "personio",    # 25+ DE — Munich HR SaaS
        "omio",        # Berlin travel
        "sennder",     # Berlin freight
        "taxfix",      # Berlin tax SaaS
        "babbel",      # Berlin language learning
        "kayak",       # Berlin travel
        "kaiahealth",  # Munich digital health
        "deliveryhero",# Berlin food delivery
        "wirecard",    # DE payments (legacy)
        # === Mid-size / startup ===
        "aleph", "younited", "scalablecapital",
        "jimdo", "wefox", "adjust", "tandem",
        "weclapp", "solaris", "remazing",
        "transfergo", "qonto", "revolut",
        # === Internationals with DE presence ===
        "adyen",       # payments, 200+ jobs incl DE
        "catawiki",    # Berlin/NL collector marketplace
        "bitpanda",    # Vienna crypto, 50+ jobs
        "kayak",
        # === Duplicates kept for redundancy ===
        "zelando",
    ],
    "lever": [
        "justwatch",   # Berlin streaming guide
        "aleph",       # 100+ jobs
    ],
}

ADZUNA = {
    "app_id": os.environ.get("ADZUNA_APP_ID", "56bf71a8"),
    "app_key": os.environ.get("ADZUNA_APP_KEY",
                              "b6ef9b5ba4412279de0ebd6e935755a6"),
}


# ──────────────────────────────────────────────────────────────────────
#  Delivery
# ──────────────────────────────────────────────────────────────────────
DELIVERY = {
    "telegram": {
        "enabled": True,
        "token": os.environ.get(
            "TELEGRAM_BOT_TOKEN",
            "8905888529:AAF_3UFShFmyb67bS4zdo-0J3aSUA-UNwL8",
        ),
        "chat_id": os.environ.get(
            "TELEGRAM_CHAT_ID",
            "5598447111",
        ),
    },
    "dashboard": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": int(os.environ.get("PORT", "8000")),
        "password": os.environ.get(
            "DASHBOARD_PASSWORD",
            "Raj271123",
        ),
    },
    "schedule": {
        "daily_hour_cet": 7,
        "daily_minute_cet": 0,
    },
}


# ──────────────────────────────────────────────────────────────────────
#  Paths
# ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
SEEN_FILE = DATA / "seen_jobs.json"      # dedupe across days
DIGESTS_DIR = DATA / "digests"           # one JSON per day
DIGESTS_DIR.mkdir(exist_ok=True)