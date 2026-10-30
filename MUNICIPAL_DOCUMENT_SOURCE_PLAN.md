# Municipal document discovery: acceptance checklist

This changes the **source layer**, not the existing GIS-to-document pilot.
No new daily collectors, network requests, database schema changes, DeepSeek
usage or recurring scheduled tasks are enabled in this branch.

## First four official discovery indexes

- Toronto — Council/committee meeting and background-report system (TMMIS)
- Brampton — eSCRIBE Council and Planning & Development agendas, often combined PDFs
- Mississauga — Council and Committees calendar with associated records
- Hamilton — Council/committee agendas and eSCRIBE RSS listing

The sources, official municipal supporting links, and factual limitations are
recorded in `config/municipal_document_sources.csv`.

## Stage gates: do not claim operational until independently tested

1. Open an actual **dated 2026** planning committee meeting for each city.
2. Record public index URL, meeting ID, *direct report/agenda URL*, HTTP status,
   robots/access policy, document type, document title, publication timestamp
   and content checksum.
3. Prove the attachment can be read by a bounded, legal adapter **without**
   bypassing authentication, CAPTCHAs, access controls or robots restrictions.
   Fail closed otherwise, and mark the source blocked rather than repeatedly retrying it.
4. Parse HTML and digitally readable PDFs. Flag scans separately for OCR review.
   Don't infer a publication date from the download date.
5. Extract per-project application ID, location, developer, status, proposed use,
   dates and evidence excerpts **only if supported by the document**.
   Exclude meeting attendees' personal contact details from selling outputs.
6. Conservative cross-source matching: exact stable municipal IDs first,
   civic-address matches only for manual review.
7. Measure source publication, *Radar first-observed*, and eventual permit dates
   separately; don't infer that a historic date is when Radar discovered a project.
8. Source reuse/licensing and sales rights reviewed before products are marketed.
9. Report buyer contact route and supplier-award status as UNKNOWN unless
   independently evidenced.

## Run offline registry check

`python municipal_document_registry.py --out document_source_review`

This creates only `MUNICIPAL_DOCUMENT_REGISTRY_STATUS.json`, making no API calls.

**Current operational truth:** Official discovery index verified for four cities;
zero direct documents have passed the automated fetch/extraction acceptance gates.
Do not merge into the production 8:30 AM V8 task as a working collector.
