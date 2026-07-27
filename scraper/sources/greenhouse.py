"""
Greenhouse public job-board API adapter.

Docs (unofficial but stable, widely used): 
  https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

No auth required. Returns JSON with all open jobs + full HTML description.
"""
import requests

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch_jobs(company_name: str, token: str, timeout: int = 15):
    """
    Returns (jobs, error). jobs is a list of normalized dicts.
    error is None on success, or a short string describing what went wrong
    (used to flag broken seed entries -- e.g. company migrated ATS or renamed board).
    """
    url = API_URL.format(token=token)
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    if resp.status_code == 404:
        return [], "404_not_found (token likely wrong or company left Greenhouse)"
    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    try:
        data = resp.json()
    except ValueError:
        return [], "invalid_json"

    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "source": "greenhouse",
            "company": company_name,
            "title": job.get("title", ""),
            "location": (job.get("location") or {}).get("name", ""),
            "job_url": job.get("absolute_url", ""),
            "description_html": job.get("content", "") or "",
            "posted_at": job.get("updated_at", ""),
            "external_id": str(job.get("id", "")),
        })
    return jobs, None
