# v0.6 PREVIEW — isolated, review-only incremental release

This is **not** a production-certified v0.6. It is an opt-in York source plus review-only service-category lead hypothesis export, built on the v0.5 code without a database schema migration. All 18 existing enabled sources retain their definitions.

## What's new
- York Region Active Development Applications ArcGIS adapter configured; **disabled by default** until live source acceptance (licence, schema, stable key, pagination, filtered row counts, incremental window) on your Windows machine.
- `lead_candidates_REVIEW_ONLY.csv` automatically exported alongside `feed.csv` and dashboard. This builds **service-category hypotheses** from new/updated events only; they are explicitly unverified, not finished leads, and must not be sold directly. No email/phone harvesting or outbound messages.
- Three additional candidate export tests.

## Safe setup
1. Keep your full v0.5 data directory, and close any scheduled poller.
2. Extract this package beside v0.5 (e.g. `gta_commercial_radar_v06_preview`).
3. Open PowerShell inside it, then run:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py adopt --from-data "..\gta_commercial_radar_v05\data"
python main.py doctor --source york_region_active_development_applications
```

Adopt **only once** and only into a clean v0.6 data folder. It does not modify v0.5.

The York feed remains disabled from all-source normal polling. If doctor passes, inspect the licence and source field definitions, then intentionally baseline ONLY this source:

```powershell
python main.py poll --source york_region_active_development_applications
python main.py status
```

Its first run should baseline records without generating fresh leads. Run a subsequent poll to verify incremental behavior. Do not enable routine York polling until these checks pass.

## Cautions
- The York regional feed appears to be weekly updated and may cover regional-review applications, not every municipality's application.
- Stable `APPL_GISID` and `MOD_DATE` are selected based on service metadata; real row completeness and timestamp query support require live acceptance.
- Some existing source records default to UNKNOWN commercial relevance; do not mistake hypotheses for qualified commercial demand.
- ZIP intentionally **excludes** the 990 MB data directory, preserving it solely in the original v0.5 folder.
