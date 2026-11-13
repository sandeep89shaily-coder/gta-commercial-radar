# Datum benchmark: agenda-first source refinement (2026-11-12)

## Public comparison (not reverse engineered)
Datum describes collecting municipal council/committee agendas, minutes and video from eSCRIBE, Granicus, CivicWeb and municipal open-data feeds, using transcription and document AI, structured extraction with field evidence, and resolution across project stages. Source: https://datumai.ca/ ; attribution and permitted-source rules: https://datumai.ca/attribution . Its internal API, scraper implementation, customers and extraction quality are not publicly verified.

## What GTA Radar already has
- `municipal_meeting_capture.py`: official city meeting index discovery and agenda/document link recognition; official HTML fetched only, no video download.
- Document, transcript and buyer/permit linking pilots. These are not evidence of full citywide agenda coverage or successful source-content extraction.
- Original GIS/permit and industrial ERO collectors with source-health and run history.

## Increment implemented as an isolated manual research pilot
`python gta_council_document_delta.py --city Brampton --out MY_REVIEW_FOLDER`

The new module reuses the existing permitted official municipal index discovery. It writes:
- `COUNCIL_DOCUMENT_LINK_LEDGER.json`: persistent URL-identity first/last observed timestamps and latest title.
- `COUNCIL_DOCUMENT_LINK_EVENTS.csv`: initial baseline, first-observed new links, and title edits; never a claim that the municipality *published* a new project.
- `COUNCIL_DOCUMENT_LINK_STATUS.json`: fetched vs blocked/failed, visible link counts, known-but-now-missing links retained; zero falsely verified projects.

The initial baseline generates **zero newly published claims**; subsequent runs can report link deltas for analyst attention. Failing, partial or 403 source checks do not delete or rebaseline known history. No private or blocked sources are crawled, no extra page/doc fetch occurs, and existing commercial daily collection and US$1/day DeepSeek settings are unchanged.

**Important limitation:** This is a durable link-change collection checkpoint, **not a completed Datum-equivalent agenda-item collector**. A visible agenda link can refer to a meeting index or a staff report, may be dynamically rendered, and is not necessarily a project. We cannot claim to have read a file or proved an original posting date until original source content is separately retrieved, checked, and cited.

## Next required acceptance
1. On authorized primary portals, collect actual agenda items, staff-report attachments and official meeting IDs from eSCRIBE, Granicus and CivicWeb, with per-platform permission/reuse checks.
2. Extract exact report pages, proposal/project identities, decision status and dated source provenance without manufacturing first publication.
3. Join to municipal development applications and permit history and measure true lead-time advantage on >=20 independently reviewed projects.
4. Only then enable qualified candidate events in the standard manual daily runner. Do not add a paid AI step to an unverified index link.
