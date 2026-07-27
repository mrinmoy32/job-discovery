"""
Lever public postings API adapter.

Docs (unofficial but stable):
  https://api.lever.co/v0/postings/{company}?mode=json

No auth required.
"""
import requests

API_URL = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch_jobs(company_name: str, token: str, timeout: int = 15):
    url = API_URL.format(token=token)
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return [], f"request_failed: {e}"

    if resp.status_code == 404:
        return [], "404_not_found (token likely wrong or company left Lever)"
    if resp.status_code != 200:
        return [], f"http_{resp.status_code}"

    try:
        data = resp.json()
    except ValueError:
        return [], "invalid_json"

    if not isinstance(data, list):
        return [], "unexpected_response_shape"

    jobs = []
    for job in data:
        categories = job.get("categories", {}) or {}
        location = categories.get("location", "") or ""
        jobs.append({
            "source": "lever",
            "company": company_name,
            "title": job.get("text", ""),
            "location": location,
            "job_url": job.get("hostedUrl", ""),
            "description_html": job.get("descriptionPlain", "") or job.get("description", "") or "",
            "posted_at": job.get("createdAt", ""),
            "external_id": str(job.get("id", "")),
        })
    return jobs, None
