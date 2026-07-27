"""
Job discovery orchestrator.

Run: python scraper/main.py

Reads config.json + companies_seed.json, pulls open jobs from each configured
source, filters for role/skills/YOE/country/visa-signal match, extracts any
publicly-listed contact info, dedupes against the 7-day seen-store, and
writes:
  data/jobs_today.json          -- new matches from this run
  data/jobs_archive.json        -- rolling history of every match ever shown
  data/jobs_seen.json           -- internal dedupe store (not for direct viewing)
  data/broken_seed_entries.json -- seed companies whose ATS token 404'd/failed
  data/run_log.json             -- last-run summary (counts, timings, errors)
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.sources import greenhouse, lever, ashby, smartrecruiters, yc_jobs, wellfound
from scraper import filters, contacts, dedupe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
SEED_PATH = os.path.join(ROOT, "companies_seed.json")
DATA_DIR = os.path.join(ROOT, "data")

JOBS_TODAY_PATH = os.path.join(DATA_DIR, "jobs_today.json")
JOBS_ARCHIVE_PATH = os.path.join(DATA_DIR, "jobs_archive.json")
SEEN_STORE_PATH = os.path.join(DATA_DIR, "jobs_seen.json")
BROKEN_SEED_PATH = os.path.join(DATA_DIR, "broken_seed_entries.json")
RUN_LOG_PATH = os.path.join(DATA_DIR, "run_log.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=False)


def fetch_from_ats_companies(config, seed):
    """Fetch raw jobs from Greenhouse/Lever/Ashby/SmartRecruiters companies in the seed list."""
    sources_cfg = config["sources"]
    delay = config.get("run_settings", {}).get("request_delay_seconds", 1.5)

    adapter_map = {
        "greenhouse": greenhouse.fetch_jobs,
        "lever": lever.fetch_jobs,
        "ashby": ashby.fetch_jobs,
        "smartrecruiters": smartrecruiters.fetch_jobs,
    }

    all_jobs = []
    broken = []

    for entry in seed.get("companies", []):
        ats = entry.get("ats")
        if ats not in adapter_map or not sources_cfg.get(ats, False):
            continue

        fetch_fn = adapter_map[ats]
        jobs, error = fetch_fn(entry["name"], entry["token"])
        if error:
            broken.append({"company": entry["name"], "ats": ats, "token": entry["token"], "error": error})
        else:
            all_jobs.extend(jobs)

        time.sleep(delay)

    return all_jobs, broken


def fetch_from_html_sources(config):
    """Fetch raw jobs from best-effort HTML-scraped sources (YC, Wellfound)."""
    sources_cfg = config["sources"]
    delay = config.get("run_settings", {}).get("request_delay_seconds", 1.5)
    all_jobs = []
    warnings = []

    if sources_cfg.get("y_combinator_jobs"):
        jobs, error = yc_jobs.fetch_jobs(request_delay=delay)
        if error:
            warnings.append({"source": "y_combinator_jobs", "note": error})
        all_jobs.extend(jobs)
        time.sleep(delay)

    if sources_cfg.get("wellfound"):
        # A handful of role slugs relevant to this profile; extend as needed.
        role_slugs = ["frontend-engineer", "full-stack-engineer"]
        for slug in role_slugs:
            jobs, error = wellfound.fetch_jobs(slug, request_delay=delay)
            if error:
                warnings.append({"source": f"wellfound:{slug}", "note": error})
            all_jobs.extend(jobs)
            time.sleep(delay)

    return all_jobs, warnings


def process_jobs(raw_jobs, config):
    matched_jobs = []
    for job in raw_jobs:
        raw_text = filters.strip_html(job.get("description_html", ""))
        evaluated = filters.evaluate_job(job, config)
        if evaluated:
            enriched = contacts.enrich_contacts(evaluated, raw_text)
            matched_jobs.append(enriched)
    return matched_jobs


def main():
    run_started = datetime.now(timezone.utc)
    config = load_json(CONFIG_PATH, {})
    seed = load_json(SEED_PATH, {"companies": []})

    if not config:
        print("ERROR: config.json missing or invalid. Aborting.")
        sys.exit(1)

    ats_jobs, broken_seed = fetch_from_ats_companies(config, seed)
    html_jobs, html_warnings = fetch_from_html_sources(config)
    raw_jobs = ats_jobs + html_jobs

    matched_jobs = process_jobs(raw_jobs, config)

    seen_store = dedupe.load_seen_store(SEEN_STORE_PATH)
    expiry_days = config.get("run_settings", {}).get("seen_expiry_days", 7)
    new_jobs, seen_store = dedupe.filter_new_or_expired(matched_jobs, seen_store, expiry_days)

    max_new = config.get("run_settings", {}).get("max_new_jobs_per_run", 200)
    new_jobs = new_jobs[:max_new]

    for job in new_jobs:
        job["discovered_at"] = run_started.isoformat()

    save_json(JOBS_TODAY_PATH, new_jobs)
    dedupe.save_seen_store(SEEN_STORE_PATH, seen_store)

    archive = load_json(JOBS_ARCHIVE_PATH, [])
    archive.extend(new_jobs)
    save_json(JOBS_ARCHIVE_PATH, archive)

    save_json(BROKEN_SEED_PATH, broken_seed)

    run_log = {
        "run_started": run_started.isoformat(),
        "run_finished": datetime.now(timezone.utc).isoformat(),
        "raw_jobs_fetched": len(raw_jobs),
        "jobs_matched_filters": len(matched_jobs),
        "new_jobs_shown_today": len(new_jobs),
        "broken_seed_entries": len(broken_seed),
        "html_source_warnings": html_warnings,
    }
    save_json(RUN_LOG_PATH, run_log)

    print(json.dumps(run_log, indent=2))
    if broken_seed:
        print(f"\n{len(broken_seed)} seed compan(y/ies) failed to resolve -- see data/broken_seed_entries.json")


if __name__ == "__main__":
    main()
