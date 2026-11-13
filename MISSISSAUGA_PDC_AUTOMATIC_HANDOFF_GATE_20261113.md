# Mississauga discovered PDC agenda PDF handoff — 2026-11-13

## Verified source situation

The City's [Council and Committees calendar](https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/) publicly describes meeting records, agendas, minutes and videos. Its normal HTML does **not** reliably expose the eSCRIBE PDF URLs to the existing direct-link index parser. The linked eSCRIBE portal has produced HTTP 403 when independently inspected. This is a *source-access gap*, not proof that no committee agendas exist.

City PDC agendas are issued as eSCRIBE direct `FileStream.ashx?DocumentId=<exact-number>` PDFs (the existing `gta_mississauga_pdc_agenda.py` source parser already supports them). Never enumerate, guess, or alter document IDs to bypass denied access.

## Implemented source-to-parser bridge

`gta_mississauga_discovered_pdc_run.py` now:
- Reads `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/SOURCE_INDEX/COUNCIL_DOCUMENT_LINK_LEDGER.json` **only after the same run's Mississauga source status confirms index access and eligible direct links**.
- Filters to direct original Mississauga eSCRIBE PDF URLs with exact PDC/Planning-and-Development labels, current-check source evidence and the official City calendar as discovery provenance.
- Limits downloads to **three PDFs per manually triggered fresh run**. Uses the existing `gta_mississauga_pdc_authorized_fetch.py` (public DNS, robots, exact host/ID, no redirects, size and PDF validation).
- Sends successfully retrieved PDF agenda items to `gta_mississauga_pdc_agenda.py`, then passes verified-as-source-text item CSVs to `gta_agenda_application_permit_20_case.py` for **identity review only**.
- Reports `NO_DIRECT_PDC_URLS_SOURCE_ADAPTER_GAP`, `PDC_PDF_ACCESS_OR_EXTRACTION_HELD`, or `EXTRACTED_REVIEW_ONLY` in a dedicated JSON audit. An inaccessible or zero-yield calendar remains a documented gap.
- Is enabled through the existing `RUN_GTA_RADAR_TODAY.bat` manual full-run path, not `--skip-collection`. No standalone schedule, paid DeepSeek call, database mutation, email, or automatic customer-ready lead.

New outputs are under `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/MISSISSAUGA_DISCOVERED_PDC` and will be included in the existing dated safe ZIP.

## Actual remaining gate

**The source calendar's missing direct PDF links are not solved by connecting the downloader.** The city or eSCRIBE may need to publish a usable HTML/subscribe notification feed, or approve an authorized data export. Without validated direct URLs, the collector performs zero PDF requests and says so explicitly.

The existing `GTA_RADAR_COUNCIL_INPUTS.json` route for owner-provided actual saved agendas remains available. Do not turn original City meeting dates into publication dates or count policy reports as construction projects. Keep the US$1/day shared DeepSeek limit unchanged; collector work itself makes no paid AI calls.

Source references: [Mississauga calendar](https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/), [Planning and Development Committee](https://www.mississauga.ca/council/committees/planning-and-development-committee/).
