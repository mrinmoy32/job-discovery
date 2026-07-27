"""
Filtering & matching logic.

None of this is a guaranteed-accurate classifier -- it's keyword/heuristic
matching against job titles, locations, and description text. It's designed
to be permissive (favor showing you a maybe-relevant job over hiding a
relevant one) since a human reviews the dashboard anyway.
"""
import re
from html import unescape

US_VISA_KEYWORDS = [
    "visa sponsorship", "will sponsor", "sponsor visa", "h-1b", "h1b",
    "relocation assistance", "relocation support", "work permit sponsorship",
    "sponsorship available", "able to sponsor",
]

NO_SPONSOR_KEYWORDS = [
    "no visa sponsorship", "not able to sponsor", "unable to sponsor",
    "will not sponsor", "cannot sponsor", "must be authorized to work",
    "must have valid work authorization without sponsorship",
]


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def title_matches_role(title: str, roles: list) -> bool:
    title_lower = title.lower()
    return any(role.lower() in title_lower for role in roles)


def skills_matched(description_text: str, skills: list) -> list:
    text_lower = description_text.lower()
    return [s for s in skills if s.lower() in text_lower]


def location_country_match(location: str, description_text: str, countries_cfg: dict):
    """
    Returns (matched: bool, matched_country_label: str, visa_signal: str)
    visa_signal is one of: "india_no_visa_needed", "sponsor_mentioned",
    "no_sponsor_mentioned", "unclear", "not_applicable"
    """
    loc_lower = (location or "").lower()
    text_lower = (location or "") + " " + (description_text or "")
    text_lower = text_lower.lower()

    india_cfg = countries_cfg.get("india", {})
    if india_cfg.get("include") and any(alias in loc_lower for alias in india_cfg.get("aliases", [])):
        return True, "India", "india_no_visa_needed"

    remote_ok = countries_cfg.get("remote_global_counts_as_match", True)
    if remote_ok and "remote" in loc_lower and "india" not in loc_lower:
        # ambiguous remote listing -- surface it, let visa-keyword check inform the user
        pass

    for country in countries_cfg.get("visa_sponsor_countries", []):
        if country.lower() in loc_lower:
            if any(k in text_lower for k in NO_SPONSOR_KEYWORDS):
                return True, country, "no_sponsor_mentioned"
            if any(k in text_lower for k in US_VISA_KEYWORDS):
                return True, country, "sponsor_mentioned"
            return True, country, "unclear"

    if remote_ok and "remote" in loc_lower:
        if any(k in text_lower for k in US_VISA_KEYWORDS):
            return True, "Remote (unspecified)", "sponsor_mentioned"
        return True, "Remote (unspecified)", "unclear"

    return False, "", "not_applicable"


def yoe_in_range(description_text: str, min_yoe: float, max_yoe: float) -> bool:
    """
    Best-effort: look for patterns like '5+ years', '3-6 years experience'.
    If nothing found, we don't exclude the job (returns True) -- absence of a
    stated YOE requirement isn't evidence you're unqualified.
    """
    text = description_text.lower()
    patterns = [
        r"(\d+)\s*\+?\s*-\s*(\d+)\s*years",
        r"(\d+)\s*\+\s*years",
        r"minimum of\s*(\d+)\s*years",
        r"at least\s*(\d+)\s*years",
    ]
    found_any = False
    for pat in patterns:
        for match in re.finditer(pat, text):
            found_any = True
            nums = [int(g) for g in match.groups() if g]
            if not nums:
                continue
            lo = min(nums)
            hi = max(nums) if len(nums) > 1 else lo + 3  # "5+ years" treated as open-ended upper bound
            if lo <= max_yoe and hi >= min_yoe:
                return True
    return not found_any  # no explicit range stated -> don't filter it out


def company_size_ok(employee_count, min_employees: int) -> bool:
    """
    If we don't know the employee count (None), we don't exclude the job --
    company size data isn't available from ATS APIs directly; this is meant
    to be populated by an optional enrichment step or manual seed curation.
    """
    if employee_count is None:
        return True
    return employee_count >= min_employees


def evaluate_job(job: dict, config: dict):
    """
    Runs a raw job dict through all filters. Returns an enriched dict with
    match metadata if it passes, or None if it should be dropped.
    """
    profile = config["profile"]
    countries_cfg = config["countries"]

    description_text = strip_html(job.get("description_html", ""))
    full_text = f"{job.get('title','')} {job.get('location','')} {description_text}"

    if not title_matches_role(job.get("title", ""), profile["roles"]):
        return None

    matched_skills = skills_matched(full_text, profile["skills"])
    if len(matched_skills) < profile.get("min_skill_matches", 1):
        return None

    country_match, country_label, visa_signal = location_country_match(
        job.get("location", ""), description_text, countries_cfg
    )
    if not country_match:
        return None

    if not yoe_in_range(full_text, profile.get("min_yoe", 0), profile.get("max_yoe", 99)):
        return None

    job_out = dict(job)
    job_out["matched_skills"] = matched_skills
    job_out["country_match"] = country_label
    job_out["visa_signal"] = visa_signal
    job_out["description_html"] = ""  # drop heavy HTML before saving to output JSON
    job_out["description_snippet"] = description_text[:400]
    return job_out
