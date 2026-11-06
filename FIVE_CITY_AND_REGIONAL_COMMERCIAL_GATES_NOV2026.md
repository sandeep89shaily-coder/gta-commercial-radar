# GTA Radar — November 6 official five-city recovery and regional shortlist

## Why this change

The November 5 run included project-index signals, historical planning
applications and source-dated changes but did not provide a reliable,
evidence-gated regional commercial shortlist. Burlington, Vaughan and
Kitchener lacked verified automatic file-ID extraction. Richmond Hill and
Newmarket published rich official GIS layers, but their endpoints denied
permitted automated access.

## Municipal recovery

The existing daily launcher now executes a *bounded* follow-up collector:

- Burlington: when the existing municipal GIS supplies exact official project
  URLs, open at most 16 project pages. If no GIS URLs are available, attempt
  the official current-development index. Extract **only** file numbers
  explicitly labelled in the official project's File Numbers section.
  Accept both 505-10/26 and 505-10-26 formats. Missing IDs, robots denials
  and unsupported layouts are recorded, not manufactured.
- Vaughan: one official Public Notices index
  (`https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices`),
  using its explicitly labelled City File No., Subject Land and notice
  description. Meeting dates do **not** become original publication dates.
- Kitchener: existing official ArcGIS layer and sanctioned CSV export remain
  the only application-ID candidates. The new five-city report shows the
  actual status and does not treat GIS metadata as records.
- Richmond Hill and Newmarket: existing GIS source denial remains visible.
  Authorized CSV exports from their publisher UIs are supported by the
  existing assisted importer, never counted as live automated recovery.
- All extracted official live file IDs go into the existing canonical
  application deduplication, with first-run baseline handling. An application
  is **not** a verified commercial contract, and not proof of citywide
  completeness.

New artifacts:
`GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv`,
`GTA_RADAR_FIVE_CITY_OFFICIAL_NEW_OR_CHANGED.csv` and
`GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json`.

## Regional commercial evidence gate

The new `gta_regional_commercial_review.py` stage consumes:

- Toronto planned capital procurement tables (not open tenders).
- York, Peel and Waterloo official extracted project detail pages.
- Corresponding official PDF text evidence where present.

It creates:
- `GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW.csv` — screened, source-backed
  planned or stage-to-verify work, not confirmed open.
- `GTA_RADAR_REGIONAL_COMMERCIAL_CHANGES_TO_REVIEW.csv` — only changes
  after a historical baseline, merged into the existing combined daily report.
- `GTA_RADAR_REGIONAL_COMMERCIAL_EXCLUDED.csv` — already underway,
  historically targeted, explicitly completed or awarded work,
  **with reasons**, never silently dropped.
- `GTA_RADAR_REGIONAL_COMMERCIAL_REVIEW_STATUS.json`.

No row can assert verified tender availability without a separate
current procurement source check. Historical capital sourcing years are
removed from the current planned-review queue. Generic policy/meeting
index links are not promoted. Re-observed older OMB/OLT-approved Toronto
applications are not published as fresh commercial leads.

## Tests and acceptance

```powershell
python -m pytest -q tests/test_five_city_application_recovery.py tests/test_regional_commercial_review_gate.py
```

Dedicated GitHub source acceptance probes real official Burlington and
Vaughan pages with the existing DNS/robots/no-redirect checked fetcher.
**A green workflow can still report access or schema denial.** Observe
its underlying per-city statuses, not just the workflow pass/fail.

This PR does not ask for or bypass access permissions and does not
claim that all five cities now have verified automatic coverage.

Run normally after `python desktop_update.py`. Your November 5 results,
original ledgers and manual exports remain untouched.
