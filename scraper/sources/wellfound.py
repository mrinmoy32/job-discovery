"""
Wellfound (formerly AngelList Talent) -- best-effort scraper.

IMPORTANT CAVEAT: Wellfound has no official public API and actively rate-limits
/ fingerprints scraping traffic. This adapter is intentionally conservative:
low request volume, generic desktop User-Agent, delay between requests, and
it fails soft (returns empty + a reason) rather than retrying aggressively.

Given Wellfound's own site already lets you filter by "Visa Sponsorship" and
remote/India, many users get more value checking it manually a few times a
week than relying on this adapter. It's included for completeness, kept
deliberately light-weight, and should be the first thing you disable in
config.json if it ever causes trouble (429s, CAPTCHAs).
"""
import time
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://wellfound.com/role/r/{role_slug}"


def fetch_jobs(role_slug: str, timeout: int = 15, request_delay: float = 2.0):
    try:
        resp = requests.get(
            SEARCH_URL.format(role_slug=role_slug),
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (job-discovery personal tool)"},
        )
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    time.sleep(request_delay)

    if resp.status_code == 429:
        return [], "rate_limited (backing off; consider disabling this source or reducing frequency)"
    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    for card in soup.select("[data-test='JobSearchCard']"):
        title_el = card.select_one("[data-test='job-title']")
        company_el = card.select_one("[data-test='company-name']")
        link_el = card.select_one("a[href]")
        if not title_el or not link_el:
            continue
        href = link_el.get("href", "")
        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
        jobs.append({
            "source": "wellfound",
            "company": company_el.get_text(strip=True) if company_el else "",
            "title": title_el.get_text(strip=True),
            "location": "",
            "job_url": full_url,
            "description_html": "",
            "posted_at": "",
            "external_id": full_url,
        })

    if not jobs:
        return [], "no_jobs_parsed (markup may have changed, or request was soft-blocked)"

    return jobs, None
