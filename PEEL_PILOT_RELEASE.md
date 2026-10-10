# Peel government network pilot — research and conservative integration

This release builds on the event-date-corrected Radar application. The 35-row `PEEL_GOVERNMENT_SOURCE_MATRIX.csv` maps Peel Region, Brampton, Mississauga, Caledon, Peel/Dufferin-Peel school boards, CVC, TRCA and provincial sources relevant to Peel. **It is a source-family research matrix, not 35 independently proven live collectors or an exhaustive department audit.**

## Implemented
- `peel_pilot.py`: two public-page readers, for Caledon current development-application IDs and Peel Flow water/wastewater project references. Results go into **data/peel_pilot.sqlite**, separate from the existing municipal and business databases.
- Content revisions and newly observed entries are recorded, with **no first-run baseline alerts**, no record removals on missing entries, and no replacement of pre-existing data after a failed fetch.
- Each entry retains official URL, source, last-seen observation and an explicit **NO_SOURCE_DATE** marker. A project number containing 2026 is **not** treated as a 2026 event date. New-on-website observations are also **not automatically qualified leads**.
- Daily runs and `START_RADAR.bat` attempt the pilot without making it a prerequisite for normal Radar operation; failures are logged and existing datasets are not cleared.
- `RUN_PEEL_PILOT.bat` runs just these two pilot collectors to view results separately. Outputs: `peel_pilot_observations.csv`, `peel_pilot_changes_REVIEW_ONLY.csv`, `peel_pilot_runs.csv`.

## What is NOT claimed
- No live remote import is verified in this release. Local parsing tests use representative HTML fixtures. Website access, scraper reuse permissions, and long-term stability must be verified on the user's network before these should be called production sources.
- The two new lists do not currently flow into the main commercial lead queue; they remain separately stored source evidence while we validate dates, identity and licensing.
- Procurement portals, school boards, conservation authorities and further municipal departments are **inventoried**, not automatically collected; they require official record-level access and licence checks.
- No DeepSeek tokens were used for these pilot sources, and no autonomous registry scraping was added.

## User operation
Extract this complete ZIP next to the older Radar folders, preserving them. Open `GTA_RADAR_PEEL_PILOT` and double-click `START_RADAR.bat`. The existing program will run plus a best-effort Peel pilot. The first Peel run is a baseline; use `RUN_PEEL_PILOT.bat` later for source-specific reporting. No files in older folders are modified.

## Source references
- https://www.caledon.ca/en/town-services/current-applications.aspx
- https://peelregion.ca/construction/watermain-construction/flow-program/flow-program-map
- https://peelregion.ca/construction/projects/current-construction-projects
- https://peelregion.bidsandtenders.ca/
- https://www.brampton.ca/EN/residents/Roads-and-Traffic/Pages/Construction-Projects.aspx
