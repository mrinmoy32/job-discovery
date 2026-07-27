"""
SmartRecruiters public postings API adapter.

Docs (official, public):
  https://api.smartrecruiters.com/v1/companies/{token}/postings

No auth required for public postings list. Note: SmartRecruiters company
identifiers are usually the exact company name as registered (case-sensitive
in some cases) -- verify via the company's public careers page URL, which
typically looks like: https://jobs.smartrecruiters.com/{token}
"""
import requests

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"


def fetch_jobs(company_name: str, token: str, timeout: int = 15):
    url = LIST_URL.format(token=token)
    try:
        resp = requests.get(url, timeout=timeout, params={"limit": 100})
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    if resp.status_code == 404:
        return [], "404_not_found (token likely wrong or company left SmartRecruiters)"
    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    try:
        data = resp.json()
    except ValueError:
        return [], "invalid_json"

    jobs = []
    for job in data.get("content", []):
        location = job.get("location", {}) or {}
        loc_str = ", ".join(filter(None, [location.get("city"), location.get("country")]))
        jobs.append({
            "source": "smartrecruiters",
            "company": company_name,
            "title": job.get("name", ""),
            "location": loc_str,
            "job_url": job.get("applyUrl", "") or job.get("ref", ""),
            "description_html": "",  # requires a second call per-job; kept light for rate limits
            "posted_at": job.get("releasedDate", ""),
            "external_id": str(job.get("id", "")),
        })
    return jobs, None
