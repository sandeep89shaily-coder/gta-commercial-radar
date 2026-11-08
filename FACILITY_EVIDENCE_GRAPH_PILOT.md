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

## November 8: field-schema audit from an existing Radar export

Inspected a previously supplied `GTA_RADAR_RESULTS` archive, without a fresh Windows run:

- `GTA_RADAR_COLLECTION_MASTER.csv`: **1,640** rows, of which **1,517** are application-ID records and **123** are project-only signals. **1,391** rows were labelled `UNCHANGED`; they must not become newly discovered sales leads solely due to graph import. A historic planning application can still provide site context.
- `GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv`: **161** new/changed rows. Some Brampton permit records carry `city=Peel`, so facility matching derives **Brampton** from the known official source identifier, explicitly labelled as a source-jurisdiction interpretation. If configured source jurisdiction and explicit city contradict one another, site joining is refused.
- Toronto permit civic addresses may include just the first three postcode characters, e.g. `220 YONGE ST M5B`. The normalization removes that postal prefix, but never changes a street number.
- A bounded Oakville planning description names `Pinty's Delicious Foods - 2714 Bristol Circle` with the structured address blank. Such address extraction is allowed as **description-only unverified context** only when unique; multi-application snippets with multiple addresses are not auto-linked.
- A source date older than **180 days**, unknown/future source date, or historical planning baseline cannot be promoted into a fresh actionable opportunity simply because Radar has just seen it.

These counts are a **previous export snapshot**, not a new run, and not a claim that today's full collector/database was checked.

## Next layer: per-event commercial evidence dossiers

A **second offline processor** now turns a facility graph into distinct `one source event = one possible work package` investigative dossiers. Never merge ERO equipment replacement, a planning addition and a business licence into one "confirmed opportunity" just because the street address matches.

- `gta_facility_dossiers.py` consumes facility event and link CSVs. It assigns investigative priority (equipment-specific, activation, general application), and separately holds dated historical/withdrawn/unverifiable records.
- `GTA_RADAR_EVIDENCE_DOSSIERS.csv` contains source IDs, site and organization clues, evidence dates and URLs, potential customer segments, blockers, and explicit **NO** fields for verified open contracts, buyers and outreach authorization.
- `GTA_RADAR_EVIDENCE_DOSSIERS.jsonl` contains one structured dossier per event and related records as **unverified same-site context**, not proof of the same project or tenant.
- `GTA_RADAR_DOSSIER_VERIFICATION_TASKS.csv` gives a precise human worklist: source record recheck, scope/timeline, current procurement, buying authority, public business contact, actual opening (if relevant), and same-project identity.
- `GTA_RADAR_EVIDENCE_DOSSIERS.html` is a safe escaped research browser; invalid source links and spreadsheet formula injection are blocked.

The dossiers *cannot* become a certified sales opportunity through this offline stage. It intentionally does not guess contacts or assert open purchase orders. Verified procurement needs independently checked actual source documents, purchasing authority and procurement-stage evidence.

### Isolated one-click review (manual acceptance only)

`RUN_FACILITY_EVIDENCE_REVIEW.bat` runs **only** the shared graph and dossier processors using existing `GTA_RADAR_RESULTS` snapshots. It does not start a collector, schedule any action, communicate with companies, or spend AI funds. No action is required from the user during code development.

For a future controlled acceptance:

```powershell
py -3 gta_facility_review_run.py --workspace "%USERPROFILE%\Desktop\new data" --as-of 2026-11-08
```

Both output directories are isolated beneath `GTA_RADAR_RESULTS`: `FACILITY_INTELLIGENCE_PILOT` and `FACILITY_DOSSIER_PILOT`. The runner refuses to create a misleading empty report if none of the four underlying source exports exists.

### Real export quality constraint

In the previously uploaded November 7 Radar archive, only **13** of the **161** daily project IDs were found as exact IDs in `GTA_RADAR_PROJECT_OPPORTUNITIES.csv`; of those, just **one** had a populated operator value. These are historical snapshot counts, *not current live verification*. We will not join company names or buying authorities to a facility solely on address/name similarity. Dossiers therefore expose a **company/operator evidence gap** instead of pretending those associations are verified.

### Technical acceptance

Automated regressions: **21** shared graph checks, **17** dossier checks and **4** end-to-end manual runner checks; the full existing GitHub cross-platform test suite must pass as well. Passing synthetic tests does not verify actual match precision or business value. The next real validation should sample actual facility joins, historical exclusions and role identification against original official records, then benchmark supplier actionability before merging.

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
