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
    "title": "Automation & Digital Transformation Specialist",
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
        # target roles
        "target_titles": [
            # Exact matches (highest weight)
            "RPA Developer", "RPA Engineer", "Senior RPA",
            "UiPath Developer", "Power Automate Developer",
            "Test Automation Engineer", "QA Automation Engineer",
            "Process Automation Engineer", "Workflow Automation Engineer",
            # Broad automation roles (medium weight)
            "Automation Engineer", "Automation Developer",
            "AI Automation", "Intelligent Automation",
            "Process Automation", "Workflow Automation",
            "Flow Automation", "Power Platform Developer",
            "Automation Lead", "Automation Architect",
            "Test Engineer", "QA Engineer", "SDET",
            # Adjacent roles (lower weight but still match)
            "Product Owner", "Product Manager", "Workflow Manager",
            "Process Manager", "Transformation Lead",
            "Digital Transformation", "Business Automation",
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
    "min_score": 35,             # tight but not absurd
    "max_age_days": 7,           # last week max (was 14, too lenient)
    "seen_resurfacing_days": 5,  # show same job again after 5d if still fresh
    "fetch_timeout_sec": 20,
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# ──────────────────────────────────────────────────────────────────────
#  Job sources
#  Add/remove freely — each entry is a callable in src/sources/*.py
# ──────────────────────────────────────────────────────────────────────
SOURCES = {
    "arbeitnow": {"enabled": True, "label": "Arbeitnow"},
    "stepstone": {"enabled": False, "label": "StepStone (captcha-blocked, needs proxy)"},
    "indeed_de": {"enabled": False, "label": "Indeed DE (captcha-blocked, needs proxy)"},
    "greenhouse": {"enabled": True, "label": "Greenhouse (DE tech)"},
    "lever":      {"enabled": True, "label": "Lever"},
    "jobicy":    {"enabled": True, "label": "Jobicy (remote, EU-friendly)"},
    "adzuna":     {"enabled": True, "label": "Adzuna DE (StepStone/Indeed aggregator, 250/month)"},
    "honeypot":   {"enabled": False, "label": "Honeypot"},  # gated API
}

# If you ever register for Adzuna free tier (adzuna.com/api), drop keys here:
ADZUNA = {
    "app_id": os.environ.get("ADZUNA_APP_ID", "56bf71a8"),
    "app_key": os.environ.get("ADZUNA_APP_KEY",
                              "b6ef9b5ba4412279de0ebd6e935755a6"),
}

# Greenhouse + Lever: German tech companies that post publicly
COMPANY_BOARDS = {
    # German / DACH tech companies on Greenhouse public boards
    "greenhouse": [
        "celonis", "personio", "deliveryhero", "traderepublic",
        "sennder", "omio", "flaconi", "remazing", "taxfix",
        "kaiahealth", "raisin", "n26", "zalando", "hellofresh",
        "kayak", "babbel", "sumup", "wirecard", "qonto",
        "wolt", "bolt", "transfergo", "qonto", "revolut",
        "aleph", "contentful", "younited", "scalablecapital",
        "jimdo", "doctolib", "wefox", "adjust", "tandem",
        "weclapp", "personio", "raisin", "solaris",
    ],
    "lever": [
        # Lever API is unstable across companies; keep small verified list
        "justwatch", "aleph",
    ],
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