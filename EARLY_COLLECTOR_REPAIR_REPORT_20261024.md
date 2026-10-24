# GTA Radar — four failed source collectors: repair and live validation
_2026-10-24 · isolated early pilot, not production V8_

This work directly addresses the user's uploaded `GTA_RADAR_RESULTS.zip`, in which IESO, Burlington citywide ward discovery, Brampton PDC agendas and Ajax were reported FAILED. We did not alter V8, existing daily runs, DeepSeek calls or customer outreach.

## 1. IESO — FIXED and actually live-tested

**Cause:** The official public `/Application-Status` page renders the queue as a JavaScript grid. The original parser incorrectly expected an HTML `<table>` element, so it produced FAILED.

**Repair:** The page itself links to official JSON `https://www.ieso.ca/-/media/files/IESO/files/applicationstatusdata.json`. `early_cue_watch.py` now reads that JSON directly, requires a credible record count, checks duplicate CAA identifiers, preserves applicant/queue/type/status, and never calls a queue ID year a first-published date. Records retain UNVERIFIED purchaser and UNKNOWN private procurement.

**Live GitHub Actions result:** IESO SUCCESS, **2,085** historical connection queue items in first manual snapshot, **0 NEW** as expected. Publication date of each item unknown; this does NOT imply 2,085 construction prospects or live tenders.

## 2. Ajax — FIXED and actually live-tested

**Cause:** Ajax's old `https://ajaxmaps.ajax.ca/bootrest/planningapps/property.html` webpage no longer presents the historical "All applications" listing. Its published ArcGIS map service has usable planning layers.

**Repair:** `early_ajax_arcgis.py` reads official `https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer` layer 0 **Pre-consultation** and layer 1 **Active Applications**, via complete `returnIdsOnly` IDs, bounded feature queries and cardinality/identity checks. Layer 3 duplicates an active visual layer and is intentionally not summed as extra projects. Publishes applicant (NOT buyer), planning status, proposal description, non-res floor area and source submission date **NOT** public-first-posted date.

**Live GitHub Actions result:** Ajax SUCCESS, **98 official GIS features** (10 pre-consultation + 88 active), **0 NEW** on initial baseline. These are planning features, not confirmed unique sales opportunities.

## 3. Brampton PDC — SAFE PARTIAL repair, agenda items still unavailable

**Cause:** The public eSCRIBE meeting calendar is accessible, but the `Meeting.aspx` agenda response is a JavaScript shell without rendered item details under ordinary HTTP GET. The previous parser rejected the response as a failed feed.

**Repair:** The source now preserves public PDC meeting IDs and explicit scheduled meeting dates where exposed, with `PARTIAL_CALENDAR_ONLY` status when agenda items can't be read. These calendar rows have blank site/owner/company and `USE_UNKNOWN` fit, so **no fake OZS/SPA application or buyer record** can enter the business shortlist. The published calendar is bounded to reviewed links, not falsely called a full historic archive.

**Live GitHub Actions result:** Brampton **PARTIAL_CALENDAR_ONLY**, one public committee meeting link checked; **ZERO application-specific agenda items verified**. True project-level agenda extraction remains **UNRESOLVED**, pending a supported accessible publication mechanism or official application notices.

## 4. Burlington — PARTIAL mitigation, official access BLOCKED

**Cause:** Some official project detail pages are refused by the publisher (HTTP 403), and the GitHub runner additionally receives **403 for the planning-and-development index page**. Do not bypass the publisher's protection.

**Repair:** When a ward index is readable but any linked project detail fails, the collector writes `EARLY_BURLINGTON_BLOCKED_DETAILS.csv` and `EARLY_BURLINGTON_PARTIAL_REVIEW.csv`, with `PARTIAL_UNCOMMITTED` source status, **without committing an incomplete municipality-wide snapshot or creating false NEW alerts**. If the ward index itself returns HTTP 403, the source stays FAILED/BLOCKED with an explicit access error. The separate original 3 verified seed pages are an independent *limited* watcher, not citywide coverage.

**Live GitHub Actions result:** **Not fully repaired**: ward-index fetch HTTP 403 in runner. On the user's prior desktop run the main index was accessible but a 4103 Palladium Way detail page was 403; the new partial-handling code is designed and regression-tested for exactly that case. **Desktop repeat is needed** to verify partial output. No false projects or contacts inferred.

## Engineering safety rules

- All sources use separate early-only SQLite database files under `data/`, never production `radar.sqlite`.
- First successful collection is baseline: 0 NEW until a later actual publisher change.
- Missing pages and partial indexes are not interpreted as 0 municipal opportunities.
- Source receipt/submission/meeting date != actual first public posting date.
- Applicant/general company contact != project procurement decision-maker.
- Open municipal project application != open supplier purchasing contract.
- No login, blocked-host bypass, scraping private records, DeepSeek spending, scheduling or outbound emails.

## Repeat and verification

Use `RUN_EARLY_CUES_PREVIEW.bat` manually from this pilot branch, or just:

```powershell
py -3 early_cue_watch.py --source ieso_connections --data-dir data --output-dir GTA_RADAR_RESULTS
py -3 early_ajax_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
py -3 early_discovery_watch.py --source brampton_planning_agendas --data-dir data --output-dir GTA_RADAR_RESULTS
py -3 early_discovery_watch.py --source burlington_ward_discovery --data-dir data --output-dir GTA_RADAR_RESULTS
```

Do not overwrite prior `data/*.sqlite`; the first-seen history is important. The standalone repaired ZIP is for a separate copy; copy existing **early-only** `data` folder into the extracted pilot only if intentional, never overwrite V8.

**Live source evidence:** GitHub Actions `Four repaired early collectors live check` run **40133850905**. Fixture/regression run on the same code snapshot validated updated adapter semantics and failure safety; the complete Windows/Linux green run is reported separately. Source code remains draft PR #74 until publishing rights, reliability, and actual commercial value are proven.
