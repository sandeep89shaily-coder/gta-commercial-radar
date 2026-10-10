# GTA Commercial Radar v0.8 — Business Discovery

**Extension of the corrected v0.7 codebase.** Original `main.py`, SQLite permit data and source definitions remain intact. Separate `data/business_discovery.sqlite` stores additional business observations.

## Four configured collectors (live source pages verified, but imports not executed in this environment)
- Federal active business corporations (Ontario registered-office subset), CSV; daily cadence; large first run (~100MB). Not all new federally formed businesses operate locally.
- York Region Business Directory, **2024 vintage**, GIS; 30-day cadence (historical source, no automatic opening claim).
- Kitchener non-temporary business licences, GIS; daily cadence. Live schema fields LICENSEE, LICENCED_LOCATION and LICENSE_TYPE verified.
- Niagara consolidated Employment Inventory, GIS, 30-day cadence; **historical annual survey data**, not a real-time opening feed.

## Deliberately not automated
- Ontario Business Registry: authorized manual-review queue, NOT automatic search/scraping. Triggered by new/updated business observations from either new collectors or legacy Radar changes.
- Press releases: staged until feed URL and reuse/access conditions are validated.
- Corporate website crawling and provider directory collection: not yet implemented.

## Run on Windows
Extract alongside your current v0.7, preserving v0.7, then double-click **`START_BUSINESS_DISCOVERY.bat`**. It searches for the existing working v0.7 data folder, makes a **separate SQLite online backup** into v0.8, and runs the new business collectors. It refuses to replace an existing v0.8 database. You can alternatively run `python business_discovery.py run --data-dir PATH_TO_OLD_DATA_FOLDER` to use your old data folder directly (writes business_discovery.sqlite there but not radar.sqlite). First run creates baseline and **suppresses historical directory and corporation rows from new leads**. On subsequent due runs changed/new records appear in review-only CSV, with source evidence. No automatic lead sale/distribution.

Outputs: `data/business_dashboard.html`, `business_leads_REVIEW_ONLY.csv`, `ontario_registry_MANUAL_QUEUE.csv`, `business_source_status.csv`.

IMPORTANT: This is a functional initial acquisition release, not completion of all desired source families, and does not imply commercial redistribution rights, confirmed business opening, or confirmation that an Ontario registry lookup occurred. Source failures are isolated.
