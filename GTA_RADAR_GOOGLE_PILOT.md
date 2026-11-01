# GTA Radar — Google Search Grounding Pilot (owner-approved, November 1, 2026)

## Scope
- Keep the existing Radar collector, DeepSeek selective search, and initial **public business contact search** unchanged (US$0.25/day DeepSeek local limit).
- Make up to **10** opt-in Google-grounded investigations from **new/changed** source records already discovered by Radar. This is **not automatically scheduled** and does **not** run from the daily collector.
- Compare with DeepSeek notes, show official project descriptions and sources, and hand every finding to the owner for physical/manual verification. Neither Gemini nor Radar confirms actual purchasing authority, supplier status, or an open contract.
- Free Google Search and Google Maps links are included in manual-review HTML. No Google Places billing, no automatic Google Earth scraping.

## Cost and control
- Separate local Google budget **US$5/month**, with US$0.50 pre-reserved per request and a maximum of 10 distinct project IDs per calendar month.
- Ledger: `GTA_RADAR_RESULTS/GTA_RADAR_GOOGLE_PILOT_LEDGER.sqlite`; no deletion or overwrite of DeepSeek results or owner notes.
- Grounding with Google Search is currently quoted at 5,000 free search requests/month shared among Gemini 3+ models, then US$14/1,000; individual model calls can generate multiple search queries.
- Default model: `gemini-3.1-flash-lite`; paid-tier list price US$0.25/M input tokens and US$1.50/M output/thinking tokens (subject to provider updates). The local estimate pessimistically assigns $0.014 to *every* returned Google query even if Google's shared quota may still be free.
- **Important:** The ledger is a *software-side estimate and admission control*, NOT a Google billing hard-stop. Google charges are determined by Google's servers, shared free quota, other Google projects and API calls. A single request may execute more searches than requested; users must set a Google Cloud Billing budget/alerts and restrict the key separately. Cloud budget alerts are not necessarily spending caps.
- Errors and timeouts retain the US$0.50 reservation; the same project is never silently retried during the same month.

## Setup
1. Open [Google AI Studio](https://aistudio.google.com/apikey) and create a Gemini API key for an appropriate billed project, checking the account's billing and Google API quota settings. Do not commit the key or paste it into chat.
2. In **PowerShell** for the current terminal session, set `$env:GEMINI_API_KEY = "YOUR_API_KEY"` (use a private terminal; protect your key). The tool reads `GEMINI_API_KEY` from the environment only.
3. Run `py -3 gta_google_grounding_pilot.py --reviewed-top10` to **preview** the exact November 1 ten-project cohort (no external API). Or double-click `RUN_GTA_RADAR_GOOGLE_PILOT.bat`, which previews this same cohort.
4. After checking the selection, run `py -3 gta_google_grounding_pilot.py --reviewed-top10 --paid`. Only `--paid` authorizes Google API requests. The original ten exact permit IDs are frozen at `config/google_pilot_reviewed_projects_20261101.txt`; if an ID is absent from the source CSV, the pilot refuses to silently substitute an unrelated project.
5. Output is dated `GTA_GOOGLE_PILOT_*.csv` and `GTA_GOOGLE_PILOT_*.html` plus a cost/status summary in `GTA_RADAR_RESULTS`.
6. For a different future cohort, omit `--reviewed-top10`; the default ranks the latest first-observed and changed records. You can also pass `--source-csv "C:\\path\\to\\projects.csv"` with fields `project_id`, `observation` (FIRST_OBSERVED or RECORD_CHANGED), `address`, `city`, and optionally `description` and `record_source_url`. Pilot still limits to ten.

## Safe first test on Windows (no generation or grounding)
1. Update your existing Radar code folder from GitHub **without replacing** `GTA_RADAR_RESULTS`, databases or review notes.
2. Double-click `RUN_GEMINI_KEY_CHECK_NO_COST.bat`. If the key is not already available in your environment, the launcher asks for it in a hidden console prompt. It is used in memory only and is not saved to disk or printed.
3. The diagnostic makes **one model-metadata GET request** to Google. `MODEL_LOOKUP_OK` means the key can access the model metadata; it **does not** prove that a paid Google Search request will work. `MODEL_LOOKUP_FAILED` includes a bounded, redacted HTTP error and status to diagnose access or billing settings. No project is sent and no local budget reservation is made.
4. Only after the key lookup passes, preview `RUN_GTA_RADAR_GOOGLE_PILOT.bat`. A subsequent `--paid` run remains a **separate deliberate step**, never triggered by this key checker or by normal daily Radar.

If you need to share the diagnostic, share only the status and error fields, **never the API key**. No GitHub Actions secret or Google Places configuration is required for this local key check.

## Quality check
For each project, review: (a) whether Google found a distinct current primary source beyond DeepSeek; (b) whether project use, work scope and dates match the official record; (c) whether any business contact is corroborated on a company-owned website; and (d) whether the research is new enough to justify future API spending. Count independently confirmed corrections, not only more model output.

References:
- https://ai.google.dev/gemini-api/docs/google-search/
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models
