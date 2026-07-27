"""
Seen-store: tracks (company, title, location) fingerprints with a timestamp
so the same job isn't re-shown every day. A job re-appears only if it wasn't
seen within the configured expiry window (default 7 days) -- e.g. if it was
reposted, or if enough time passed that it's worth a second look.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def make_key(job: dict) -> str:
    return "|".join([
        _normalize(job.get("company", "")),
        _normalize(job.get("title", "")),
        _normalize(job.get("location", "")),
    ])


def load_seen_store(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen_store(path: str, store: dict):
    with open(path, "w") as f:
        json.dump(store, f, indent=2, sort_keys=True)


def filter_new_or_expired(jobs: list, seen_store: dict, expiry_days: int):
    """
    Returns (jobs_to_show, updated_seen_store).
    A job is shown if its key isn't in the store, or its last_seen is older
    than expiry_days.
    """
    now = datetime.now(timezone.utc)
    cutoff = timedelta(days=expiry_days)
    jobs_to_show = []

    for job in jobs:
        key = make_key(job)
        last_seen_str = seen_store.get(key, {}).get("last_seen")
        should_show = True
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                if now - last_seen < cutoff:
                    should_show = False
            except ValueError:
                pass

        if should_show:
            jobs_to_show.append(job)

        seen_store[key] = {
            "last_seen": now.isoformat(),
            "company": job.get("company", ""),
            "title": job.get("title", ""),
        }

    return jobs_to_show, seen_store
