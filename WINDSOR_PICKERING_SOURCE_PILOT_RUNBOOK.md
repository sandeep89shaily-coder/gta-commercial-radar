# Windsor + Pickering planning intelligence — isolated collector pilot
_Date: 2026-11-19 · RESEARCHED_UNBUILT -> ISOLATED_OFFLINE_PILOT_

## Evidence and source boundaries

**Windsor** publishes a current-development-applications register with multiple
exact file numbers on the same project row, civic address, application type and
links to details. The index is useful for robust project identity but is **not**
a full project scope/contract announcement and has no confirmed original notice
date. Official source:
https://www.citywindsor.ca/residents/planning/land-development/development-applications/current-development-applications

Examples recorded from the live public page:
- Z-012/26 and ZNG/7372 — 1785 Turner Road
- Z-019/26, ZNG/7385, OPA 204 and OPA-7386 — 1356 Drouillard Road
- Z-026/26 / ZNG/7395 — 5855 Cabana Road East

**Pickering** publishes a ward-organized proposal index with applicant,
address and a *Date Posted*, plus corresponding /news/posts/ project pages
with exact OPA/SP/CP/zoning IDs, scope, supporting documents and planners.
The project article date and index posted date can **differ**. Neither is
automatically proof of first public disclosure.
Sources:
https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/
https://www.pickering.ca/news/development-proposals/

Example: Plaza 6 Inc., 666–682 Liverpool Road. Project detail lists
OPA 26-001P, SP-2026-01, CP-2026-01 and A 01/26, plus proposed residential
townhouses. Its site must **not** be promoted as a commercial-industrial
equipment opportunity merely because it has planning documents.

## Implementation
- `gta_windsor_pickering_source_pilot.py`: standard-library parser
  for publisher-approved saved municipal HTML snapshots; neither network nor
  DeepSeek or SQLite ever invoked.
- `tests/test_windsor_pickering_source_pilot.py`: exact-ID, mixed file
  number, page-date, address, scope, source-URL and offline tests.
- Windsor register rows with identifiers are captured as INDEX_ONLY,
  even when industrial prospects remain scope-unverified.
- Pickering register rows become a discovery list **only**. No final project
  application is published until its own linked project page establishes
  file number and site address.
- Named planners are **not** purchasing contacts.
- Existing 24 production municipalities stay unchanged.

## Offline usage
Prepare an authorized snapshot folder:

```
snapshots/
  windsor.html
  pickering.html
  pickering_detail_urls.json
  pickering_details/
    sample-one.html
```

Example `pickering_detail_urls.json`:

```json
{
  "sample-one.html": "https://www.pickering.ca/news/posts/plaza-6-inc/"
}
```

Run:

```powershell
py -3 gta_windsor_pickering_source_pilot.py --results "GTA_RADAR_RESULTS" --snapshot-dir "snapshots"
```

The default without `--snapshot-dir` is a zero-record preflight. It does not
access any website or mutate production.

## Remaining acceptance
1. Confirm permitted automated source retrieval and government reuse terms;
   snapshot-based local processing alone is not proof of permission for live
   automated collection.
2. Independently sample at least 20 current municipal application records if
   available, compare exact file numbers, address and full project-page scope
   against the city website, and record source URL/date.
3. Identify true original public publication date separately from Pickering
   index Date Posted, article date, and local first-seen.
4. Ensure no historical 2020 page is labelled a 2026 opportunity and no
   residential-only page is ranked as an equipment procurement lead.
5. Preserve multi-file project identity in one record, not four duplicate
   projects; clarify matching semantics before any 26/28-city join.
6. Demonstrate stable access and graceful blocked-source behavior before adding
   either pilot to the normal Windows full run.

**Commercial status:** Research evidence only. No named buyer, proven open RFQ,
unawarded supplier package or live source-readiness certification.
