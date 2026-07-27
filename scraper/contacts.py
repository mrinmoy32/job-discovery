"""
Contact extraction.

We only extract contact info that is directly present in public job-post
text (e.g. "reach out to jane@company.com" or a listed HR phone number) --
this is information the poster put there for candidates to use. We do NOT
scrape LinkedIn profiles or any other source of personal data. Instead, for
recruiter lookup, we generate a LinkedIn people-search URL per job that you
can open yourself to check, keeping that step manual and low-risk.
"""
import re
import urllib.parse

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Generic emails companies expect applicants to see; still useful as a fallback
# contact even when no named recruiter is present in the post.
GENERIC_INBOX_HINTS = ("careers@", "talent@", "jobs@", "recruiting@", "hr@", "people@")

PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}"
)


def extract_emails(text: str):
    if not text:
        return []
    found = set(m.group(0).lower() for m in EMAIL_RE.finditer(text))
    # filter out obvious non-recruiter noise like image/script artifacts
    cleaned = [e for e in found if not e.endswith((".png", ".jpg", ".svg", ".gif"))]
    return sorted(cleaned)


def extract_phones(text: str):
    if not text:
        return []
    candidates = []
    for m in PHONE_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if 8 <= len(digits) <= 15:  # plausible phone-number length range
            candidates.append(raw.strip())
    # dedupe while preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def linkedin_recruiter_search_url(company: str) -> str:
    query = f"recruiter OR \"talent acquisition\" OR \"technical recruiter\" {company}"
    params = urllib.parse.urlencode({"keywords": query})
    return f"https://www.linkedin.com/search/results/people/?{params}"


def enrich_contacts(job: dict, raw_description_text: str) -> dict:
    emails = extract_emails(raw_description_text)
    phones = extract_phones(raw_description_text)
    job = dict(job)
    job["contact_emails"] = emails
    job["contact_phones"] = phones
    job["has_named_contact"] = bool(emails or phones)
    job["linkedin_recruiter_search"] = linkedin_recruiter_search_url(job.get("company", ""))
    return job
