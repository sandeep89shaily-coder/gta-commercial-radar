# GTA Radar — Free early-cue pilot v0.1 (manual, isolated)

**Status: implemented source adapters, OFFLINE fixtures; live Windows validation still required.** Not merged into V8. DeepSeek calls: **zero**. No schedule, outreach, third-party paid data, or changes to `config/sources.json`.

## What this first slice actually monitors

1. **IESO official public connection application/status page**:
   https://www.ieso.ca/Sector-Participants/Connection-Process/Application-Status

   Extracts CAA ID, published applicant, project, connection type, region/zone, capacity, SIA stage and proposed in-service date. Each CAA is one IESO published queue entry; **not a GTA construction project, purchasing buyer, or available contract**. Transmission zones do not establish precise locations. Some public pages are paginated or JavaScript-based. If project table is missing, report FAILED; if the page is paginated, flag `PAGINATED_WINDOW_NOT_FULL_QUEUE`, never claim the total queue was collected.

2. **Three verified Burlington project pages** at known official URLs:
   - https://www.burlington.ca/en/news/current-development-projects/3056376-canada-inc-777guelphline.aspx
   - https://www.burlington.ca/en/news/current-development-projects/1376-1382-plains-rd-e.aspx
   - https://www.burlington.ca/en/news/current-development-projects/2076-old-lakeshore-rd.aspx

   Extracts title, municipal application status, site address, published applicant/proponent, proposal description and whether the source mentions a pre-application meeting. **This is an initial three-page watch, not a Burlington-wide discovery feed.** Later work must find a reliable official current development index/ward feed and document first public appearance.

**Important:** Burlington web pages confirm that pre-application community meetings may occur before formal planning application. That does **not** demonstrate a new record today, guaranteed lead-time advantage or unawarded suppliers.

## How to test on the user's GTA Radar folder

Double-click `RUN_EARLY_CUES_PREVIEW.bat` in the latest **pilot branch folder**, or run:

```shell
python -m unittest tests.test_early_cue_watch
python early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
```

Requires existing repository dependencies in `requirements.txt` (requests, beautifulsoup4). These are already installed for GTA Radar's other collectors in most setups; no additional paid API.

Pilot outputs:
- `GTA_RADAR_RESULTS/EARLY_CUES_SOURCE_STATUS.csv`
- `GTA_RADAR_RESULTS/EARLY_CUES_RESEARCH_QUEUE.csv`
- `GTA_RADAR_RESULTS/EARLY_CUES_CHANGES_REVIEW_ONLY.csv`
- `data/early_cues_review.sqlite` (separate database from `data/early_signals_review.sqlite` and production `data/radar.sqlite`)

**First successful source observation is baseline, not 3 new leads / 7 new leads.** Later genuinely unseen published IDs create NEW and meaningful content edits create UPDATED. Historical entries never become 'new' just because of installation. `first_seen_at` is Radar first observation, **not publication date**, and IESO CAA year is not an exact source date. Failure of a request leaves that source's old snapshots untouched. A stale item from a paginated window is not called current.

### Known limitations and acceptance gates

- Live availability and publisher HTML structure must be confirmed on the user's PC. Automated CI tests use offline synthetic HTML fixtures and **cannot guarantee a live service response**.
- IESO listing may be server- or browser-paginated. Current parser monitors **visible rows** only. Add full pagination only after inspecting the actual official public service; do not falsely claim comprehensive queue coverage.
- Burlington's municipal-wide discovery is **not implemented**; only the three verified project URLs are observed. Without an official dynamic index new Burlington project pages won't be found automatically.
- Brampton eSCRIBE Planning & Development Committee meeting agendas are a **next pilot source**. The official public May 11, 2026 agenda with detailed application item sections is verified:
  https://pub-brampton.escribemeetings.com/Meeting.aspx?Agenda=Agenda&Id=25022e86-016b-490b-b051-1bae3971fa77&lang=English
  Automatic *current meeting discovery* and commercial use/access terms still need testing, so do not fabricate feed coverage.
- Proposal and record dates must never be inferred from page text or CAA year as official **publication dates**.
- Compare candidate names/addresses against the original seven planning/GIS sources and later permits to demonstrate incremental early advantage; a province-wide connection status may have no GTA impact.
- Verify publisher terms/robots/data rights, respectful request rate and publisher URL availability before commercial-scale scheduling.
- No buyer role, public business contact, supplier availability or contract status is verified by this pilot.
- Keep US$0.25/day DeepSeek limit and V8 production unchanged; don't schedule until project quality and value are demonstrated.

## Next build milestones (full research register remains active)

1. Validate IESO table rendering and pagination and Burlington three-page parsing on Windows. Do not call FAIL as 0 events.
2. Build **automatic discovery** of Burlington pre-application project pages from a confirmed index; parse source meeting notices and attachments with true first-publication dates where available.
3. Build Brampton eSCRIBE Planning & Development Committee new-meeting discovery and agenda item extraction; source PDF attachments without OCR by default.
4. Improve existing ERO **proposal-stage** changes rather than duplicating collector.
5. Compare actual first public posting dates to the same projects' GIS/permit dates; use only genuine lead-time advantage to expand.
6. Independently verify 10 real industrial opportunities and sell to 2 paying pilot customers.

**Do not mark any research candidate sale-ready from these new sources alone.**
