"""
Indeed DE scraper using Playwright.
Indeed has aggressive bot detection; we use realistic headers + slow scroll.

NOTE: Indeed DE is currently behind Cloudflare/captcha bot protection.
This scraper is preserved for future use. Import is wrapped so the
pipeline works when playwright is not installed.
"""
import re

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

QUERIES = [
    "RPA Developer",
    "UiPath Developer",
    "Automation Engineer",
    "Test Automation Engineer",
    "Power Automate",
    "Process Automation",
    "Workflow Automation",
    "AI Automation",
    "Product Owner Automation",
    "Python Automation",
]


def _parse_age(text: str) -> int | None:
    if not text:
        return None
    t = text.lower()
    if "heute" in t or "today" in t or "gerade" in t or "just" in t:
        return 1
    m = re.search(r"(\d+)\s*stunde", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*tag", t)
    if m:
        return int(m.group(1)) * 24
    m = re.search(r"(\d+)\s*woche", t)
    if m:
        return int(m.group(1)) * 24 * 7
    m = re.search(r"(\d+)\s*monat", t)
    if m:
        return int(m.group(1)) * 24 * 30
    return None


def fetch(timeout_ms: int = 30000) -> list[dict]:
    if not _PLAYWRIGHT_AVAILABLE:
        print("[indeed_de] playwright not installed, skipping")
        return []
    out = []
    seen = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="de-DE",
                viewport={"width": 1366, "height": 900},
            )
            page = ctx.new_page()
            for q in QUERIES:
                url = (f"https://de.indeed.com/jobs?q={q.replace(' ', '+')}"
                       f"&l=Deutschland&fromage=1")
                try:
                    page.goto(url, timeout=timeout_ms,
                              wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    for _ in range(3):
                        page.mouse.wheel(0, 1500)
                        page.wait_for_timeout(500)
                except Exception as e:
                    print(f"[indeed:{q}] goto failed: {e}")
                    continue

                # Indeed markup is heavy & obfuscated; try multiple selectors
                cards = page.query_selector_all(
                    "div.job_seen_beacon, "
                    "div[class*='job_seen_beacon'], "
                    "div[data-jk], "
                    "li[class*='job']"
                )
                for c in cards[:20]:
                    try:
                        title_el = c.query_selector(
                            "h2 a, a[data-jk], a.jcs-JobTitle, "
                            "[class*='JobTitle'] a"
                        )
                        if not title_el:
                            title_el = c.query_selector("h2 span")
                        if not title_el:
                            continue
                        title = title_el.inner_text().strip()
                        href = title_el.get_attribute("href") or ""
                        if href and href.startswith("/"):
                            href = "https://de.indeed.com" + href
                        elif not href:
                            jk = c.get_attribute("data-jk")
                            if jk:
                                href = f"https://de.indeed.com/viewjob?jk={jk}"

                        if not title or not href:
                            continue
                        job_id = "indeed-" + (c.get_attribute("data-jk")
                                              or re.sub(r"\W+", "-", href)[-60:])
                        if job_id in seen:
                            continue
                        seen.add(job_id)

                        loc_el = c.query_selector(
                            "[data-testid='text-location'], "
                            "[class*='companyLocation'], "
                            "div[class*='location']"
                        )
                        loc = loc_el.inner_text().strip() if loc_el else "Deutschland"

                        age_el = c.query_selector(
                            "[data-testid='myJobsStateDate'], "
                            "span[class*='date'], "
                            "span[class*='age']"
                        )
                        age_text = age_el.inner_text().strip() if age_el else ""
                        hours = _parse_age(age_text)

                        company_el = c.query_selector(
                            "[data-testid='company-name'], "
                            "span[class*='companyName']"
                        )
                        company = (company_el.inner_text().strip()
                                   if company_el else "")

                        salary_el = c.query_selector(
                            "[class*='salary'], "
                            "[data-testid*='salary']"
                        )
                        sal_text = (salary_el.inner_text().strip()
                                    if salary_el else "")
                        sal = _parse_salary_eur(sal_text)

                        out.append({
                            "id": job_id,
                            "source": "indeed_de",
                            "title": title,
                            "company": company,
                            "location": loc,
                            "country": "Germany",
                            "remote_ok": "remote" in loc.lower()
                                         or "homeoffice" in loc.lower(),
                            "url": href,
                            "description": f"See full JD on Indeed: {href}",
                            "tags": [q],
                            "salary_eur": sal,
                            "posted_at": age_text,
                            "_age_hours": hours,
                        })
                    except Exception:
                        continue
            browser.close()
    except Exception as e:
        print(f"[indeed_de] fatal: {e}")
    return out


def _parse_salary_eur(text: str) -> int | None:
    """Extract yearly EUR from '60.000 € – 80.000 € pro Jahr'."""
    if not text:
        return None
    nums = re.findall(r"([\d.]+)", text.replace(".", "").replace(",", ""))
    nums = [int(n) for n in nums if n.isdigit() and int(n) > 5000]
    if not nums:
        return None
    # use the lower bound as min
    return min(nums)