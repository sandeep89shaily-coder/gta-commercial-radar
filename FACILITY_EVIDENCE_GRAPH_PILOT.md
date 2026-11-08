# Shared Facility Evidence Graph — Sunday development branch

**Status: draft foundation, not integrated into production; no live source recheck.**

## Purpose

Both GTA Radar pilots and the core daily intelligence runner refer to overlapping companies, street locations and projects. Instead of three isolated lead tables, we need a **conservative shared physical-facility evidence view**. This implementation distinguishes:

- **Facility / site**: an exact civic address and municipality, including the distinction between different suites/units.
- **Source event**: a permit, planning application, ERO equipment proposal or business-licence/activation indicator, identified by source family + original record identity.
- **Organization mention**: a *proponent*, operating name, developer, builder or agent; this is **not** verified legal-entity identity and **not** proof of a purchasing decision-maker.
- **Potential project / work-package connection**: an investigative link, never automatically a verified same-project or available supplier contract.
- **Dates**: source-record dates and Radar first-observed dates remain separate; a late historical import does not get a manufactured new-publication timestamp.

## Sources and run boundaries

`gta_facility_intelligence.py` is an **offline post-processor**. It requires no key, network, external dependencies or changes to the shared source database.

Inputs (missing sources appear as zero rows, not invented coverage):
- `GTA_RADAR_RESULTS/GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv`
- `GTA_RADAR_RESULTS/GTA_RADAR_COLLECTION_MASTER.csv` — only canonical `APPLICATION_ID` planning records
- `GTA_RADAR_RESULTS/INDUSTRIAL_PILOT/GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv`
- `GTA_RADAR_RESULTS/COMMERCIAL_ACTIVATION_PILOT/GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv`

Manual command (do **not** run it now; this is for future acceptance):

```powershell
py -3 gta_facility_intelligence.py --results "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS"
```

Outputs are isolated under `GTA_RADAR_RESULTS/FACILITY_INTELLIGENCE_PILOT/`:

- `GTA_RADAR_FACILITY_EVIDENCE_EVENTS.csv`: individual source events and their provenance
- `GTA_RADAR_FACILITY_HISTORY.csv`: one *physical-site* review profile per exact civic address and city
- `GTA_RADAR_FACILITY_SOURCE_LINKS.csv`: transparent relationship records with explicit uncertainty labels
- `GTA_RADAR_FACILITY_COMMERCIAL_REVIEW.csv`: supplier-interest hypotheses, qualification blockers and review status
- `GTA_RADAR_FACILITY_INTELLIGENCE.html`: first 500 sites for readable manual review
- `GTA_RADAR_FACILITY_INTELLIGENCE_STATUS.json`: input counts, reasons for exclusions, and acceptance limits

The official data, pilot exports and production daily runner are **never modified**. No DeepSeek calls, emails, automated outreach, scheduled runs or change to PRs #152/#153.

## Anti-false-positive gates

- The same civic address **is not** proof of the same tenant, company, project or buyer.
- Explicitly different unit/suite numbers **do not join tenants**.
- When a suite exists on one source only, link is at building level and marked uncertain.
- Addresses extracted from planning **description text** are weaker than structured addresses and must be rechecked.
- An ERO proponent is not automatically a purchaser. A licence operating name is not independently verified occupancy.
- A proposal, licence, permit or inspection is **not** an available purchase order.
- Closed, withdrawn, revoked, expired, awarded or completed statuses block active-prospect labeling.
- Source observation dates are never substituted for dates of project publication.
- Invalid, non-HTTPS and credential-bearing URLs are excluded from direct-source link output.

## Testing and further work

Automated tests should pass on Ubuntu/Windows (Python 3.11, 3.12). Required next stages:

1. Verify actual data field formats and physical-site matches from local Radar exports. Compare exact project IDs and source pages; record any false positives/false negatives.
2. Integrate the shared site/event identity into the two existing pilots **only after** verified results and reviewed schema compatibility.
3. Expand with independent company legal-ID, contractor/developer/operator role evidence, and exact purchasing authorization, rather than broad name-based joins.
4. Review commercial opportunities independently and confirm purchase timing; verify a first ten actionable, sourced dossiers, and gain two paying pilot customers prior to release.

**A combined-site history is an investigation aid, not an automatic sales lead.**
