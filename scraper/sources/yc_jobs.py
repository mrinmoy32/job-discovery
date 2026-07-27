"""
Y Combinator public jobs listing (ycombinator.com/jobs) -- best-effort scraper.

IMPORTANT CAVEAT: unlike Greenhouse/Lever/Ashby/SmartRecruiters, YC does not
expose a stable public JSON API for its full job board (much of workatastartup.com
requires a logged-in session). This adapter reads only the public, unauthenticated
jobs listing page and is the most likely adapter to break or return few/no
results if YC changes their page structure. Treat it as supplementary, not
a primary source. When it returns nothing, main.py logs it and moves on --
it never blocks the rest of the run.
"""
import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.ycombinator.com/jobs"


def fetch_jobs(timeout: int = 15, request_delay: float = 1.5):
    try:
        resp = requests.get(
            LISTING_URL,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (job-discovery personal tool)"},
        )
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    # YC's jobs page is a JS-rendered React app in many cases; a plain requests+bs4
    # fetch will often only see the initial HTML shell. We attempt a light best-effort
    # parse of any server-rendered job cards / links; if none are found, we return an
    # empty list rather than guessing at markup that may not exist.
    for link in soup.select("a[href*='/companies/'][href*='/jobs/']"):
        title = link.get_text(strip=True)
        href = link.get("href", "")
        if not title or not href:
            continue
        full_url = href if href.startswith("http") else f"https://www.ycombinator.com{href}"
        jobs.append({
            "source": "y_combinator_jobs",
            "company": "",  # often not cleanly separable from this markup; filled in from title text where possible
            "title": title,
            "location": "",
            "job_url": full_url,
            "description_html": "",
            "posted_at": "",
            "external_id": full_url,
        })

    if not jobs:
        return [], "no_jobs_parsed (page likely JS-rendered; consider a headless-browser upgrade if this source matters to you)"

    return jobs, None
