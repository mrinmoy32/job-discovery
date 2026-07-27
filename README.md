# Job Discovery Tool

Finds jobs matching your profile from company career pages (via their public
ATS APIs) that either hire in India or show signals of visa sponsorship
elsewhere, along with any recruiter contact info that's publicly listed in
the post. Runs daily on GitHub Actions, free. You review results in a static
dashboard and reach out manually.

**What this does NOT do:** it does not auto-apply, does not fill forms, and
does not scrape LinkedIn profiles. It reads public job-board JSON APIs
(Greenhouse, Lever, Ashby, SmartRecruiters) plus best-effort HTML reads of YC
Jobs / Wellfound listing pages, and extracts contact details only when
they're written directly into the public job post.

---

## 1. One-time setup

```bash
# from inside the job-discovery/ folder
git init
git add .
git commit -m "Initial job discovery tool"
```

Create a new **private** GitHub repo (Settings allow Pages on private repos
on free personal accounts), then:

```bash
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

### Enable GitHub Pages
Repo → **Settings → Pages** → Source: "Deploy from a branch" → Branch:
`main`, folder: `/ (root)` → Save. You'll get a URL like
`https://<your-username>.github.io/<repo-name>/dashboard.html` — that's your
daily dashboard.

### Enable the scheduled workflow
Nothing else needed — `.github/workflows/daily_scrape.yml` is already set to
run at **04:32 UTC (10:02 AM IST)** every day. You can also trigger it
manually any time: repo → **Actions** tab → "Daily Job Discovery" →
**Run workflow**.

> GitHub disables scheduled workflows after 60 days with zero repo activity.
> Since this workflow commits data daily, it should stay active on its own.

---

## 2. Fill in your details

Edit **`config.json`**:
- `profile.resume_gdrive_link` — paste your resume's Google Drive share link
- `my_contacts` — your name/email/phone/LinkedIn/portfolio (kept for your
  own reference; not sent anywhere)
- `profile.roles` / `profile.skills` / `profile.min_yoe` / `max_yoe` — adjust
  any time; next run picks up changes automatically
- `countries.visa_sponsor_countries` — add/remove countries
- `sources` — toggle any source `true`/`false` (e.g. turn off `wellfound` if
  it starts getting rate-limited)

No code changes needed for any of the above — the scraper reads this file
fresh every run.

---

## 3. Adding a company to `companies_seed.json`

Each entry needs the company's **ATS type** and **board token**. How to find
the token depends on the ATS — check the company's own "Careers" link:

| ATS | Careers URL pattern | Token = |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/{token}` | the `{token}` slug |
| Lever | `jobs.lever.co/{token}` | the `{token}` slug |
| Ashby | `jobs.ashbyhq.com/{token}` | the `{token}` slug |
| SmartRecruiters | `jobs.smartrecruiters.com/{token}` | the `{token}` slug (case-sensitive) |

Add a new object to the `companies` array in `companies_seed.json`:
```json
{ "name": "Example Corp", "ats": "greenhouse", "token": "examplecorp" }
```

If a token is wrong or the company migrates ATS providers, the scraper
doesn't fail — it logs the entry to `data/broken_seed_entries.json` so you
know what to fix. Check that file occasionally.

---

## 4. Understanding the output

- **`data/jobs_today.json`** — new matches from the most recent run (what
  the dashboard shows)
- **`data/jobs_archive.json`** — every match ever shown, kept for history
- **`data/jobs_seen.json`** — internal dedupe bookkeeping, not meant for
  direct reading
- **`data/broken_seed_entries.json`** — seed companies whose token/API call
  failed this run
- **`data/run_log.json`** — quick summary of the last run (counts, warnings)

A job is hidden for **7 days** after being shown once (configurable via
`run_settings.seen_expiry_days`), then can reappear if still open.

### Visa signal on the dashboard
- **India** badge — location matched your India aliases list; no visa
  needed
- **sponsor mentioned** — location is one of your target countries and the
  post text contains sponsorship-friendly language
- **no sponsorship** — post explicitly says it won't sponsor; shown so you
  can skip it, not hidden automatically
- **unclear** — country matched, but no explicit sponsorship language found
  either way — worth a manual check on the actual post

None of this is a certainty — it's keyword matching on public text. Always
verify on the actual job post before spending time on outreach.

### Contact info
Only extracted when it's directly written into the public job post. If
there's no named recruiter email, the dashboard gives you a pre-built
LinkedIn people-search link for that company so you can look up a recruiter
yourself — nothing is scraped from LinkedIn automatically.

---

## 5. Running locally (before pushing, or for testing)

```bash
pip install -r requirements.txt
python scraper/main.py
```

Then view the dashboard:
```bash
python -m http.server 8000
# open http://localhost:8000/dashboard.html
```
(Opening `dashboard.html` directly via `file://` won't work — browsers block
local `fetch()` calls for security. Always use a local server or GitHub
Pages.)

---

## 6. Known limitations (by design, not oversights)

- **YC Jobs / Wellfound adapters are best-effort.** Neither has a stable
  public API; their HTML structure can change and break the scraper
  silently returning fewer/no results. Greenhouse/Lever/Ashby/
  SmartRecruiters are the reliable tier — lean on those.
- **LinkedIn is intentionally not scraped.** Automated LinkedIn scraping
  violates their Terms of Service and is actively detected/blocked. You get
  a search link instead.
- **"500+ employees" isn't automatically verified.** ATS APIs don't expose
  headcount. Curate `companies_seed.json` with companies you already know
  are large/reputable; this is a judgment call left to you.
- **Visa-sponsorship detection is a heuristic, not a database lookup**,
  except implicitly for very well-known cases. Treat "sponsor mentioned" as
  a lead to verify, not a guarantee.
