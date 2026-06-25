"""
StepStone DE scraper using Playwright (JS-rendered SPA).
We use Playwright because StepStone's search results need JS execution.
"""
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.stepstone.de/jobs/{query}"
# Stepstone accepts URL-encoded queries via path
QUERIES = [
    "rpa-developer",
    "automation-engineer",
    "test-automation",
    "uipath",
    "process-automation",
    "workflow-automation",
    "power-automate",
    "robotic-process-automation",
    "intelligent-automation",
    "product-owner-ai",
]


def _posted_age_to_hours(text: str) -> int | None:
    """Parse 'vor 2 Tagen', 'heute', 'vor 5 Stunden' etc. → hours."""
    if not text:
        return None
    t = text.lower()
    if "heute" in t or "today" in t or "just" in t:
        return 1
    m = re.search(r"vor\s+(\d+)\s+stunde", t)
    if m:
        return int(m.group(1))
    m = re.search(r"vor\s+(\d+)\s+tag", t)
    if m:
        return int(m.group(1)) * 24
    m = re.search(r"vor\s+(\d+)\s+woche", t)
    if m:
        return int(m.group(1)) * 24 * 7
    return None


def fetch(timeout_ms: int = 25000) -> list[dict]:
    out = []
    seen_ids = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="de-DE",
            )
            page = ctx.new_page()
            for q in QUERIES:
                url = f"https://www.stepstone.de/jobs/{q}/in-deutschland"
                try:
                    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    # scroll to lazy-load
                    for _ in range(3):
                        page.mouse.wheel(0, 1500)
                        page.wait_for_timeout(400)
                except Exception as e:
                    print(f"[stepstone:{q}] goto failed: {e}")
                    continue

                cards = page.query_selector_all(
                    "article[data-testid='job-item'], "
                    "[data-testid='job-item'], "
                    "article"
                )
                for c in cards[:25]:
                    try:
                        title_el = c.query_selector(
                            "h2 a, [data-testid='job-title'], a[data-testid='job-link']"
                        )
                        if not title_el:
                            continue
                        title = title_el.inner_text().strip()
                        href = title_el.get_attribute("href") or ""
                        if not title or not href:
                            continue
                        if href.startswith("/"):
                            href = "https://www.stepstone.de" + href
                        job_id = "stepstone-" + re.sub(r"\W+", "-", href)[-80:]
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        loc_el = c.query_selector(
                            "[data-testid='job-location'], "
                            "span[class*='location'], "
                            "div[class*='location']"
                        )
                        loc = loc_el.inner_text().strip() if loc_el else "Deutschland"

                        age_el = c.query_selector(
                            "[data-testid='job-age'], "
                            "span[class*='date']"
                        )
                        age_text = age_el.inner_text().strip() if age_el else ""
                        hours = _posted_age_to_hours(age_text)

                        company_el = c.query_selector(
                            "[data-testid='job-company-name'], "
                            "span[class*='company']"
                        )
                        company = company_el.inner_text().strip() if company_el else ""

                        out.append({
                            "id": job_id,
                            "source": "stepstone",
                            "title": title,
                            "company": company,
                            "location": loc,
                            "country": "Germany",
                            "remote_ok": "remote" in loc.lower()
                                         or "homeoffice" in loc.lower(),
                            "url": href,
                            "description": f"See full JD on StepStone: {href}",
                            "tags": [q.replace("-", " ").title()],
                            "salary_eur": None,
                            "posted_at": age_text,
                            "_age_hours": hours,
                        })
                    except Exception:
                        continue
            browser.close()
    except Exception as e:
        print(f"[stepstone] fatal: {e}")
    return out