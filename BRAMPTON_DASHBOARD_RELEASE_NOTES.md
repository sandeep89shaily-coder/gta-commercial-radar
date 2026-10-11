# GTA Radar — Brampton dashboard release candidate

This branch introduces read-only operational monitoring and exploratory information intelligence. The last completed GitHub Actions test job passed. **Live public-source collection and Windows unattended execution remain unverified.**

## Outputs

After this branch is approved and deployed locally, each daily run generates:
- `data/radar_intelligence_dashboard.html`: source health, stored record counts, ArcGIS checkpoints, evidence versions, document URLs, business events, and labelled unverified address-match candidates.
- `data/radar_readiness.json`: read-only SQLite integrity and coverage checks, explicitly marking live endpoint and scheduler execution as UNVERIFIED.

You can also open `OPEN_INTELLIGENCE_DASHBOARD.bat` on Windows to rebuild both reports without collecting data.

## Boundaries and source-faithful treatment

- No rebaselining and no deletion inference. All database reads use SQLite read-only mode.
- A recorded version is an observation, **not necessarily a new public notice**. Baseline records do not count as fresh intelligence.
- An address match is a research candidate only: it is **not proof of ownership, a transaction, or commercial value**.
- Document links and excerpts retain source URLs. PDF extraction remains bounded and incomplete for scanned documents.
- The reports are offline files in ignored `data/`, **not published online**.
- This branch does not claim evidence of product-market fit or legal permission to resell every source.

## Release gate

Before merging/deploying to the Windows collector, run a live preflight using the current data (not a copied demonstration database) and verify:
1. `production_readiness.py` reports readable Brampton, municipal and business DBs.
2. The last scheduled task ran successfully on Windows; check the local task status/log.
3. Several official Brampton URLs and their intended record completeness are manually verified, including licences and PDF documents.
4. The new dashboard opens and source links correspond to underlying evidence.
5. Existing SQLite database/checkpoint backups are available.

The repository and GitHub Actions cannot independently confirm these desktop conditions. Until verified, treat this as a **release candidate**, not a production-complete deployment.
