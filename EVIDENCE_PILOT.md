# Evidence + DeepSeek pilot (review-only)

The one-click `START_RADAR.bat` now reports the number of source-linked opportunities among the first three candidates. It **does not access the internet or spend money** for this pilot by default.

For the controlled pilot (local Python only):

1. `python pilot_evidence.py --fetch` — request at most six pages from official HTTPS record URLs **already attached to the queue**. Disallows redirects, respects robots.txt, restricts to approved official domains, enforces public DNS and limited HTML sizes. If no source links exist, the audit reports that gap rather than guessing an application page.
2. `python pilot_ai.py` — dry-run count only, **no charge**.
3. `python pilot_ai.py --confirm-paid` — optional explicit DeepSeek review of up to three candidates with fetched evidence, using the existing API key and daily budget ledger. Never auto-enabled. Repeated runs cannot charge the same candidate on the same day.

Files in `data/`: `pilot_evidence_audit.csv`, `pilot_official_evidence_REVIEW_ONLY.csv`, `deepseek_pilot_REVIEW_ONLY.csv` (only created for paid investigations).

**Current boundary:** This is a safe official-link fetcher and DeepSeek evidence analyzer, **not yet a general free web search engine or autonomous DeepSeek tool-calling browser**. The next integration is source-specific official application-number/address lookup to supply missing links. No lead is marked verified, sale-ready, or contacted.

**Constraints:** No automated Ontario registry scraping, no alternate paid search provider, no guessed contact identities, no writes to `radar.sqlite`, no surprise AI charges. Results always need human verification.
