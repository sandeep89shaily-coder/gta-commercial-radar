# Four new live-source lanes integrated into the daily 28-city Radar run

_Implemented 2026-11-19. Validating against actual municipal network data requires the operator's Windows run. SOURCE COLLECTORS ARE AUTOMATIC; source ACCESS IS NOT GUARANTEED._

## Operator run

The unchanged one-click launcher automatically fast-forwards verified code on `main` and executes the standard full Radar collection. It now also attempts these four municipal sources, builds a **28-city** research master, and uses the **same** paid DeepSeek Top 10 budget.

```powershell
.\RUN_GTA_RADAR_TODAY.bat
```

## Source strategies

| City | Official source | Live mode | Scope limitations |
| --- | --- | --- | --- |
| Ajax | https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/FeatureServer/3 | ArcGIS feature paging (<=300, 100/page), REF_ID | Original publication unknown; completeness unknown if service has >300 features |
| Newmarket | https://services3.arcgis.com/tSwsWwbYRimLwcCZ/ArcGIS/rest/services/OpenNewmarket_Developments/FeatureServer/23 | ArcGIS feature paging (<=300, 100/page), FILE_NUM | EDIT_WHEN is NOT first publication; source-use permission subject to city policy |
| Windsor | https://www.citywindsor.ca/residents/planning/land-development/development-applications/current-development-applications | Fetch and parse official current application index, composite planning IDs | Index only: many rows lack commercially relevant project scope, planner does NOT equal buyer |
| Pickering | https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/ | Index fetch then up to 25 same-host project pages, require each detailed project file ID and address | Dated index and article dates are different. Incomplete detail fetches held; projects aren't verified buyers |

Every request obeys source robots policy. Sources that fail policy, TLS, HTTP, malformed JSON or source requirements are reported as **blocked or unverified**. There is no bypass or retry storm. A blocked city is still a configured city but **NOT a successfully collected municipality**.

## Current run artifacts

In the established workspace's `GTA_RADAR_RESULTS` folder:

- `GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv` — source rows actually fetched this run; no fabricated or carried-forward rows
- `GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json` — exact outcome per city, including blocked sources and real ID counts
- `GTA_RADAR_FOUR_CITY_FIRST_SEEN.json` — persistent first-seen and fingerprint ledger, stored separately from original database; not verified public publication time
- `GTA_RADAR_COMBINED_28_CITY_PROJECT_MASTER.csv` — original 24-city master + genuinely collected four-city source records
- `GTA_RADAR_COMBINED_28_CITY_COVERAGE.csv` — 28 configured cities, with new-source health separately identified
- `GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv`
- `GTA_RADAR_COMBINED_28_CITY_RESEARCH_TOP10.csv`
- `GTA_RADAR_COMBINED_28_CITY_TOP10.csv` — shared-budget AI review or honest deterministic fallback
- `GTA_RADAR_COMBINED_28_CITY_AI_TOP10_STATUS.json`

The entire source audit is included in the regular dated `GTA_RADAR_RESULTS_*.zip` (root `GTA_RADAR_*.csv/json` files).

## Acceptance meaning

- **Code-integrated**: all four collect automatically on a fresh operator-initiated run.
- **Live-source-confirmed**: status includes `LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE` and nonzero exact application IDs for a city. A zero-row success is NOT live project coverage.
- **Citywide complete**: remains FALSE absent separately audited completeness proof.
- **Buyer ready / RFQ open**: remains FALSE until separately evidenced; contact from planner, city agent or general company inbox is not a purchasing decision maker.
- **Source date**: an application's submission/edit/publication-on-index date is never called first-ever project announcement.
- No repeated paid analysis: **one** shared-budget combined review; 24-city legacy artifacts remain preserved.

## Source completeness and legal safeguards

Do not market an unsupported 28/28 fully covered network. Review the generated city statuses and validate each official publisher's automated access/reuse conditions before using records commercially. Any official refusal must remain blocked and be resolved through an authorized export or notification feed.

This changes the **automatic collection workflow**; it does not claim that the assistant's restricted development environment has successfully retrieved real records from all four endpoints. The operator's saved output ZIP is the audit evidence.
