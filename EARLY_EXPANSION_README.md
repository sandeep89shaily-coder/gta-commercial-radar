# GTA Radar — All new early public cue pilots (manual-only, October 24, 2026)

**Do NOT merge or enable in V8 until live access, source coverage, data reuse rights, and commercial utility are verified.** This work is on the draft PR #74 feature branch and is not a real-time buying-contact engine.

## Primary business objective

Identify GTA/Southern Ontario industrial and commercial projects **early enough to be useful to relevant suppliers**, determine who purchases which work, verify source dates and contractor selection before sale. Milestones: **10 independently verified actionable opportunities and 2 paid pilot customers**. The source collection itself is not the product. $0.25/day DeepSeek ceiling; these manual collectors spend **$0**.

## One computer test later

In a **fresh folder containing the pilot branch** and the existing Python requirements, double click:

`RUN_EARLY_CUES_PREVIEW.bat`

Or run the Python commands separately in this sequence:

```sh
python early_cue_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
python early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
python early_discovery_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
python early_investment_tenders.py --data-dir data --output-dir GTA_RADAR_RESULTS
python toronto_aic_email_import.py --eml-folder data/toronto_aic_eml --data-dir data --output-dir GTA_RADAR_RESULTS
python early_ajax_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
python early_oakville_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
python early_evidence_match.py
python early_buyer_evidence.py --output-dir GTA_RADAR_RESULTS
python early_leadtime_evidence.py --output-dir GTA_RADAR_RESULTS --data-dir data --output-dir GTA_RADAR_RESULTS
python early_pilot_summary.py --output-dir GTA_RADAR_RESULTS
```

Requires `requests`, `beautifulsoup4`, `pandas` already present in `requirements.txt`. Does **not** rerun the original 32,269 planning/GIS features; it may READ the prior early-signals SQLite if it is present under `data/`. Nothing calls DeepSeek or modifies the Windows scheduler, source config, or production `data/radar.sqlite`. New collectors use **their own** SQLite files and preserve first-seen dates.

**Files worth uploading after the test:** `EARLY_PILOT_RUN_SUMMARY.txt`, `EARLY_TOP_RESEARCH_PREVIEW.csv` and failed `*_SOURCE_STATUS.csv` files. Check explicit per-source failures, never assume 0 results means 0 opportunities.

## Coverage that now has code (not live-tested)

| Manual source | Script | What is recorded | Important caveat |
|---|---|---|---|
| IESO connection applications | `early_cue_watch.py` | CAA ID, applicant, project, capacity, zone, status | Official visible table may be paginated / JS; zone not proof of GTA site; no contract |
| Burlington 3 known project pages | `early_cue_watch.py` | Proposed development, stage, pre-application mention | Three seeds, NOT an automatic full municipality feed |
| Milton first development notices page | `early_public_notices.py` | Posted date, application notice and optional detail scope | First page only; paginate later after live check |
| Pickering active application table | `early_public_notices.py` | Date Posted, applicant, site, proposal scope | Not a site-plan/permit comprehensive dataset |
| ERO industrial/environmental **Proposal** stage | `early_public_notices.py` | Original ERO proposal stage and posted date | Separate proof-of-value pilot REUSING parser; V8 already has an ERO collector |
| Burlington ward-to-project discovery | `early_discovery_watch.py` | Follows municipal planning nav to ward pages to detail pages | Fail-closed if city layout not navigable or any bounded page blocked; cap 120 detail pages |
| Brampton Planning & Development eSCRIBE agendas | `early_discovery_watch.py` | Linked meeting IDs, numbered application items, roles, purpose, location | Calendar HTML may be JS/403; meeting date is NOT publication date; agenda archive incomplete |
| Ontario Newsroom all-news RSS | `early_investment_tenders.py` | Company investment/plant announcements with original publication date | Recent rolling RSS only, may be blocked; many investment releases are non-project or post-contract |
| CanadaBuys OPEN federal tenders CSV | `early_investment_tenders.py` | Open snapshot, buying federal organization, work scope, region, posted/closing date | **Federal only**, not all municipal tenders, and often not a GTA/private industrial project |
| Toronto AIC subscribed email importer | `toronto_aic_email_import.py` | Optional local .eml city links and review stage | Requires YOUR voluntary official ward subscription and exported emails; sender header can be forged; no inbox access |
| Ajax official public planning application index | `early_ajax_watch.py` | Public indexed addresses, file numbers and current planning statuses | Not an owner, buyer, permit or verified commercial land use; official application/receipt dates not exposed in list |
| Oakville seven-ward development/site-plan index | `early_oakville_watch.py` | Public application titles, stages, project links and bounded supporting project details | Index has no verified publication date; planning contact is NOT the buyer; detail PDFs dates are not notice posting dates |

**Backbone scripts:** `early_evidence_match.py` reads available source databases WITHOUT changing them, conservatively proposes same-city/exact-civic-address pairs, never auto-merges project identities and only calculates public posting-date comparison if both original public posting dates exist. `early_buyer_evidence.py` preserves human evidence worksheets and produces formal verification gates without automatically certifying leads; `early_leadtime_evidence.py` requires human-confirmed project identity and original source posting dates before comparing earlier/later stages. `early_pilot_summary.py` produces the source-health recap and top-50 **research-only**, not sale-ready list.

## One-shot public live check — October 24, 2026

GitHub Actions `Early public source live health (one-shot)`, run **40117942636**, checked only each publisher's minimum *index* schema, not full extraction or unattended rights:

| Source | Official index reachability | Limits |
|---|---|---|
| Oakville | PASS — all 7 ward indexes found | Full application/detail monitoring not yet live-tested |
| Milton | PASS — 10 first-page notices parsed | No later pagination |
| Pickering | PASS — 27 visible active proposal rows | Not every municipal filing |
| Brampton council calendar | PASS — 1 matching planning meeting link | Does not prove complete meeting archive or agenda text extraction |
| IESO | FAIL — expected HTML project table absent | Site may render table via JavaScript; currently no live data in watcher |
| Burlington ward index | FAIL — HTTP 403 from GitHub runner | Do not bypass protection or assume original seed pages are accessible |
| Ajax | FAIL — public index has different markup/JS response | Collector must not report missing applications as zero |

**A 'PASS' means publisher index accessible/schema readable only.** These numbers are not new leads or verified contractors. Neither RSS nor CanadaBuys were in this seven-source probe. The `early_live_source_probe.py` script and a gated, one-shot GitHub workflow can rerun the same read-only check; it never touches V8.

## New evidence outputs

- `EARLY_OAKVILLE_SOURCE_STATUS.csv`, `EARLY_OAKVILLE_RESEARCH_QUEUE.csv`, `EARLY_OAKVILLE_DETAILS_REVIEW.csv`
- `EARLY_BUYER_EVIDENCE_WORKSHEET.csv` — **editable human research** preserved across later snapshots; record exact buyer organization, business contact route, current stage, real work package, procurement status, evidence URLs, reviewer and date.
- `EARLY_BUYER_EVIDENCE_GATE_AUDIT.csv` — checks field completeness, but can NEVER authenticate web claims; anything complete remains `ASSEMBLED_FOR_HUMAN_REVIEW_NOT_VERIFIED_LEAD`.
- `EARLY_LEADTIME_EVIDENCE_WORKSHEET.csv` — reviewer confirms SAME project and enters **actual first public posting dates**, with sources; merely matching an address is not enough.
- `EARLY_LEADTIME_REVIEW_MEASUREMENTS.csv` — human-attested, evidence-linked date differences, not inferred advantage.
- `EARLY_BUSINESS_MILESTONES.csv` — metrics state no automatic verified sales-ready leads; paying customers cannot be inferred from code.

These worksheets make the **10 verified projects / 2 paying pilots** business objective measurable through human source evidence, rather than inflated GIS candidate counts.

## Protection and evidence rules

- First successful snapshot of each source is BASELINE, **never 'NEW'**. Later publisher record changes can be NEW / UPDATED.
- Failed source, partial pages or blocked sites are marked FAILED/limited; absent listing records do not mean a development was cancelled.
- Source `source_date` is based only on an attributable public posted date for eligible source; eSCRIBE meeting date, application receipt date, first observed date, newsletter email Date, and proposed in-service date are all **different date types**.
- Every candidate remains buyer-unverified and procurement-unknown unless an exact official procurement notice, verified organization role and current status provide evidence.
- An open **federal** tender is labeled `OPEN_AT_SOURCE_SNAPSHOT_VERIFY_DEADLINE`, not an unawarded GTA private work package.
- Cross-signal matches are **POSSIBLE_SAME_ADDRESS_NOT_VERIFIED_SAME_PROJECT** and never counted as verified project deduplication.
- No business contact guessing, private residential homeowner searches or unsolicited sales emails.
- Source publishing and commercial reuse permissions must be checked before enabling continuous commercial monitoring.
- Tests use synthetic HTML, RSS, CSV and email fixtures. Green CI is not proof the live publisher endpoints will respond from a Windows desktop.

## Still outstanding despite this code

1. **LIVE checks / pagination / rights**: confirm each current publisher format and endpoints, including Burlington complete ward links and Brampton eSCRIBE access. Never bypass WAFs.
2. **Sourced first-posting comparison**: establish the earliest *real public* exposure across source types for the SAME physical project and compare against later GIS/permit milestones; exact-address matches require manual identity checks.
3. **Buyer research and vendor availability**: verify owner/developer/operator, named work package, vendor already selected or not, public business contact and relevant service provider; unknown remains unknown.
4. **Additional source-specific feeds researched but not yet validated/built:** Toronto AIC automated bulk feed (City provides e-updates, not confirmed public bulk API), Markham/Vaughan/Richmond Hill/Hamilton and expanded Southern Ontario; AGCO full fit-out stage, utility connections beyond IESO, investments/land/leasing, Ontario Environmental Assessments, municipal tender/awards and GC prequalification signals. See **main branch** `GTA_RADAR_RESEARCH_REGISTER.md` for the complete catalogue.
5. **Business validation**: 10 verified opportunities and two paying pilot customers; no software test can establish buyer interest.

## CI / deployment

Manual test fixtures:
```sh
python -m unittest discover -s tests
```

The automated regression tests run on Linux + Windows through the repository's existing GitHub Action. The new code is on the **draft early-signals branch**; no merge or unattended task creation has occurred. Reassess success by incremental *verified* early leads, not a higher record count.
