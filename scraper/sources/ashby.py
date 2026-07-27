"""
Ashby public job-board API adapter.

Docs (unofficial but stable):
  https://api.ashbyhq.com/posting-api/job-board/{token}

No auth required.
"""
import requests

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def fetch_jobs(company_name: str, token: str, timeout: int = 15):
    url = API_URL.format(token=token)
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    if resp.status_code == 404:
        return [], "404_not_found (token likely wrong or company left Ashby)"
    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    try:
        data = resp.json()
    except ValueError:
        return [], "invalid_json"

    jobs = []
    for job in data.get("jobs", []):
        loc = job.get("location", "") or ""
        jobs.append({
            "source": "ashby",
            "company": company_name,
            "title": job.get("title", ""),
            "location": loc,
            "job_url": job.get("jobUrl", "") or job.get("applyUrl", ""),
            "description_html": job.get("descriptionHtml", "") or job.get("description", "") or "",
            "posted_at": job.get("publishedAt", ""),
            "external_id": str(job.get("id", "")),
        })
    return jobs, None
