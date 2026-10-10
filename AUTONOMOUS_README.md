# v0.12 Autonomous Lead Investigator

This release extends v0.11. It automatically queries a **licensed search API** (Brave Search), follows selected permitted public webpages, and optionally asks an OpenAI model to reconcile business identity and contacts. It **does not scrape search engine result pages**, scrape the Ontario Business Registry, invent contacts, or call private databases.

## Configure

1. Install requirements: `pip install -r requirements.txt`
2. Obtain a Brave Search API subscription key. In Windows PowerShell set `$env:BRAVE_SEARCH_API_KEY="..."` for the current session. To use the optional AI step, also set `$env:OPENAI_API_KEY="..."` (requires independently billed OpenAI API account). Do **not** paste keys into chats.
3. Use the existing business lead workflow to create `data/business_leads_REVIEW_ONLY.csv`, then `RESEARCH_LEADS.bat` to prepare candidate IDs.
4. Run `python autonomous_investigator.py --limit 10 --max-searches 30 --max-pages 20 --ai` from the same PowerShell session. Omit `--ai` for no AI charge. Or set credentials in the system environment and double-click `AUTONOMOUS_RESEARCH.bat`.

`AUTONOMOUS_PREVIEW.bat` works without keys; it **does not search the internet**.

## Outputs

- `data/autonomous_investigations_REVIEW_ONLY.csv` — candidate investigations; NEVER auto-approved or sales-ready.
- `data/autonomous_evidence_REVIEW_ONLY.csv` — source references and observed webpage contact hints.
- `data/autonomous_fetch_audit.csv` — searches attempted, pages accepted/skipped/errors.
- `data/autonomous_research_cache.json` — cached search API results to reduce repeated charges.

## Constraints and known limitations

- Brave Search API discovery requires an API key, an internet connection, and may incur fees/limits. OpenAI is independent and optional. **No live search/AI credentials were available in the build environment**, so the external services were not end-to-end verified here.
- Candidate research is automatic once invoked, but is not yet scheduled unattended on Windows. Existing scheduled data collection is unaffected.
- To limit false attribution, extracted public page emails/phones remain evidence *hints*; the AI module does not automatically promote them to a verified or sales-ready contact. Search-result snippets are unverified and must be corroborated at the actual source. Personal director data and regulated registry data need appropriate authorization and privacy review.
- The existing website fetcher uses robots.txt, no redirects, public IP checking and size limits. It may skip many pages deliberately. No bypass of anti-bot or CAPTCHA protections.
- Search calls and page checks are global run budgets. Cache avoids repeated discovery unless `--refresh`. An unsuccessful API request is audited and not counted as a successful verified lead.
- Never overwrite your existing v0.7/v0.8/v0.9/v0.10/v0.11 database. Copy the existing `data` folder if you want to reuse locally collected leads; this package contains no user data.

### Easiest Windows run

After your candidate export exists, double-click `START_AUTONOMOUS_INVESTIGATOR.bat`. It prompts for your Brave API key for this run and asks if you also want AI analysis. The launcher does not store keys in a project file. For larger runs or custom budgets use the Python command above.
