# GTA Radar — November 11 four-municipality source pilot

**Scope:** Ajax, Whitby, Clarington and Brantford, in addition to the existing
16-municipality diagnostic and separate 12-municipality GGH experimental pilot.

**Business goal:** increased *unique, source-backed* private commercial/industrial
opportunity candidates, not a larger unverified municipality count.

## Manual integrated entrypoint

The normal `RUN_GTA_RADAR_TODAY.bat` already calls the integrated intelligence
pipeline. It now executes an optional, free, source-specific stage:
`next_four_municipalities_notice_pilot` from
`gta_next_four_municipalities.py`. It makes no paid AI calls, does not schedule
a run, does not send outreach and does not write the original Radar database.
One-click execution continues to collect only on the owner's Windows device.

New original-output files under `GTA_RADAR_RESULTS`:

- `GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_REVIEW.csv`
- `GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_CHANGED_REVIEW.csv`
- `GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json`
- `GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_SEEN.json`

They are captured by the existing dated archive (top-level
`GTA_RADAR_*.csv/json` files). The dashboard links the candidate review and
its source diagnostics. No new source is included in the sixteen-city
production success denominator.

## Original official source starting points

| City | Source | Conservative evidence boundary |
| --- | --- | --- |
| Ajax | https://ajax.ca/news-notices-topic/development-planning-notices/ | City notices may link to applications; the Town's separate Planning Application Dashboard has more structured file/land-use data but is NOT automatically scraped through unapproved API endpoints |
| Whitby | https://www.whitby.ca/town-hall/council-and-committee-meetings/participation-at-public-meetings/ | Statutory public meeting descriptions may show sites and names but omit file numbers; project signals only without explicit labelled IDs |
| Clarington | https://www.clarington.net/news/ | Only up to five same-host notice-detail links; proposals without file numbers remain project signals |
| Brantford | https://buildbrantford-002-ca.govstack.com/planning-and-development-services/planning-applications-data/ | Planning map is not an HTML file-ID listing; index-only by default until original permitted query/export documented |

**Safety/access:** Existing `gta_early_applications._fetch` checks public DNS,
robots, HTTPS, redirects, HTML content and response size. Detail links must
stay on the exact source hostname, have no query/fragment and match restricted
municipal planning notice patterns. At most five pages per city. A blocked
notice causes a source failure and preserves its prior accepted baseline.
There is no GIS bypass, login, browser automation, PDF copying or fabricated
permit identity.

**Truth labels:** On first successful collection, rows are
`INITIAL_BASELINE_NOT_NEW_PUBLICATION`. After a previous accepted baseline,
a newly detected, still-undated file or notice is
`FIRST_OBSERVED_UNDATED_HELD`; changed page text is
`RECORD_CHANGED_REVIEW`. No date is inferred from local crawling, a meeting
or an application "received" field; no applicant is asserted to be a buyer.
Application-ID rows require the explicit "File" or "Application" label
immediately followed by a recognisable municipal file format.
Unnumbered proposal articles remain `PROJECT_NOTICE_SIGNAL`.

## Acceptance gates before production rollout

1. Real owner Windows collection with `STATUS.json` showing individual
   per-city successful and blocked source states.
2. Compare two *separately dated* original runs, retain exact URLs, file IDs,
   first-seen observations and source-specific content snapshots.
3. Audit 20 records across working cities against the original municipality,
   reject old, residential-only, changed-page and duplicate results; document
   independently verified public posting date when available.
4. Verify real organization roles and public business contact methods; qualify
   stage, whether vendors are already selected and actual unawarded work.
5. Only after measurable new value, consider selective promotion to the
   geographic coverage numerator and use in industry-specific client reports.

**No citywide completeness or commercially sale-ready contact claimed.**
Vaughan/Kitchener approvals, the current sixteen-city collector repairs, and
the existing US$0.25/day shared paid-research cap remain unchanged.

## Tests

```bash
python -m pytest -q tests/test_next_four_municipalities.py
```

Offline fixture tests cover source registry, original number parsing, first
baseline, repeat run, held later IDs, changes, project-only notices, index-only
map, external URL rejection, robots-blocked page and preserved baseline.
