# GTA Radar — November 6 municipal recovery and regional commercial evidence gate

## Automatic municipality recovery: what is and isn't working

This PR adds a bounded, policy-aware City of Burlington current-development
page parser and a City of Vaughan official public-notice parser. Both recognize
**explicit municipal application numbers**, never a map OBJECTID, an address,
generic index link or a numeric phone number.

The shared official HTML retrieval client enforces public DNS, robots policy,
response bounds, HTTPS and no redirect. The live GitHub source probe returned
`POLICY_DENIED:ROBOTS_ACCESS_DENIED` for both Burlington and Vaughan.
**The source parsers exist, but automated application coverage is NOT proven.**
No header spoofing, proxies or robots bypass is attempted.

Kitchener has an *already integrated* official
`Planning_Applications_Active` FeatureServer with `APPLICATION_NO`,
and an assisted-export fallback in `official_exports`.
Richmond Hill and Newmarket similarly already have schema-checked GIS
adapters and official-export fallbacks, but automated GIS access was denied
in earlier checks. No second conflicting scraper has been created.

After the existing official/assisted collector stages, the daily runner writes
`GTA_RADAR_FIVE_CITY_APPLICATION_RECOVERY.csv` and
`GTA_RADAR_FIVE_CITY_APPLICATION_RECOVERY_STATUS.json`. They distinguish
automated applications, assisted-only records, blocked access, source gaps,
verified source publication (0) and verified citywide completeness (0).

## Evidence-backed project and capital work review

The same daily runner now reads:
- regional official project detail records (York, Peel, Waterloo)
- regionally linked source PDFs
- Toronto official 2026 capital pipeline projects with scope, budget band
  and *target* sourcing year
- newly added municipal official-notice application records.

It writes:
- `GTA_RADAR_EVIDENCE_BACKED_COMMERCIAL_REVIEW.csv` for source-changed
  project evidence and future-year scheduled procurement for **manual review**
- `GTA_RADAR_EVIDENCE_BACKED_PROJECT_WATCHLIST.csv` for baseline,
  unchanged, already-under-construction, expired planned sourcing-year,
  and current-year planned work without verified open status
- `GTA_RADAR_EVIDENCE_BACKED_REVIEW_STATUS.json` with source/selection totals.

The integrated HTML dashboard links to these files, and manually reviewable
changed evidence is also added to `GTA_RADAR_INTEGRATED_INTELLIGENCE.csv`.
Explicit completed, awarded, refused and cancelled statuses are excluded from
the new review queue. This is *not* an automatically verified tender feed:
a capital-project target year and first-observation time cannot establish
that a current solicitation exists. No guessed names, contacts, award dates,
new publication dates or sales leads are generated.

Test:
```powershell
python -m pytest -q tests/test_municipal_review_and_regional_gate.py tests/test_five_city_recovery_status.py
```

Install from main using the existing `desktop_update.py`, preserve your
`GTA_RADAR_RESULTS` first-seen ledgers, then use your normal daily launcher.
First successful extraction of a new source is still historical baseline.
