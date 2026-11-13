# Mississauga agenda-to-application-to-permit collection gate — Nov 13, 2026

## Live public-source format verified

The City of Mississauga [Council and Committees calendar](https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/) exposes agendas, minutes and meeting media. The City's Planning and Development Committee page directs readers to it. Public 2026 agendas are distributed via official **eSCRIBE PDF downloads** at `https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=<number>`, not via Toronto's TMMIS HTML-item scheme and not necessarily Brampton's PDF bookmark scheme.

Two real City source documents were inspected from public web-PDF text:

- [February 23, 2026 PDC agenda, document 81898](https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=81898): item 6.1 `T-OZ 26-1 W11` at 46 William Street (temporary outdoor storage of refrigeration trailers, **no new construction** according to the attached City staff report); item 6.2 `OZ/OPA 25-18 W7`, 51–55 Dundas Street West and other Agnes Street addresses, mixed-use apartment proposal; 6.3 proposed Cooksville TOC at 3210 Hurontario Street with no explicit OZ file in the agenda summary.
- [March 9, 2026 PDC agenda, document 82234](https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234): item 6.1 `OZ/OPA 25-3 W11`, 64 & 66 Thomas Street, 95 Joymar Drive, 65 Tannery Street, residential apartments; item 6.2 `OZ/OPA 24-14 W7`, 2463 and 2469 Mimosa Row, townhouses; item 6.3 `OZ 25-20 W1`, 893 Seventh Street, semidetached homes. The 6.1 attached staff report states the proposal **should not be approved**, underscoring why no proposed project can be called an approved procurement opportunity.
- [May 11, 2026 PDC agenda, document 84942](https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=84942): four numbered matters (6.1–6.4) on citywide neighbourhood commercial zoning, plan amendments, growth monitoring and employment surveys. These are not four new construction projects.

This establishes the structure on actual official documents, **not** complete automated live collection or 20 project-level matches.

## Implemented

`gta_mississauga_pdc_agenda.py` reads a locally saved, exact official eSCRIBE agenda PDF, extracts **initial table-of-contents** numbered matters and inline planning identifiers, owners and civic address strings when unambiguous, retains the source file SHA256 and PDF page, and marks candidate titles **review-only**. It refuses a non-eSCRIBE or non-numeric DocumentId URL and does not infer source posting dates.

`gta_agenda_application_permit_20_case.py` reads exported agenda results plus separate original planning and permit CSVs. It requires source PDF SHA256, exact normalized city + application file number + civic site on both sides, distinct trusted HTTPS URLs, and unique matches. Mixed or repeated multi-site addresses stay held. Even a three-way match is an **identity review candidate**, not independently verified same project or earlier publication.

Run:
```powershell
python gta_mississauga_pdc_agenda.py --pdf "C:\RadarResearch\pdc_agenda.pdf" --pdf-url "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=ACTUAL_ID" --out "C:\RadarResearch\pdc_review"
python gta_agenda_application_permit_20_case.py --agenda-csv "C:\RadarResearch\pdc_review\MISSISSAUGA_PDC_AGENDA_ITEMS_REVIEW.csv" --applications-csv "C:\RadarResearch\official_applications.csv" --permits-csv "C:\RadarResearch\official_permits.csv" --out "C:\RadarResearch\pdc_review" --limit 20
```
Use actual official numeric DocumentId, not the illustrative placeholder. Input city/application/permit files must be genuine authorized source exports with the exact documented schema, not synthetically generated data. No network access or extra paid AI is initiated.

## Explicit official eSCRIBE source capture

The manual `gta_mississauga_pdc_authorized_fetch.py` adapter accepts up to five **exact original publicly referenced eSCRIBE DocumentId URLs** in one invocation. Without `--fetch` it performs **no network calls**. With `--fetch` it requires public DNS, permitted robots access, exact URL and host, no redirects, bounded size, PDF signature and valid PDF structure:

```powershell
python gta_mississauga_pdc_authorized_fetch.py --pdf-url "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234" "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=81898" --out "C:\RadarResearch\Mississauga" --fetch
```

It writes `MISSISSAUGA_PDC_EXPLICIT_FETCH_AUDIT.json` and isolated per-document PDF and item-review outputs. Source URLs shown are exact known City-published original documents, **not guesses**. Denials are recorded as holds, not empty data. Successful offline CI is not a live-network acceptance test. Commercial reuse permission and source publication dates require separate source evidence.

## Actual 20-case result and blockers

**Independently verified 20 full agenda → application → permit chains: NOT YET ACHIEVED.** We performed a real-source baseline audit of all 20 official Toronto permit entries from `research/toronto_20_city_exact_scope_20261108.json`, retaining each exact permit/revision, original City CKAN URL, civic address and source-validation status in `research/agenda_20_real_permit_coverage_baseline_20261113.json`. All 20 were previously checked at the permit source; **zero** have a verified cross-linked early committee item or independently established early-publication time. These are not substitutes for 20 matching Mississauga agenda/permit projects. Public primary-source PDC agendas and a prior repository pilot containing 20 exact *Toronto permit* records exist, but the Toronto records are not Mississauga planning/permit identities and cannot be used as substitutes. The original local Radar historical ingestion ledger and a corresponding Mississauga permit export are not in GitHub, and no 20 exact-item agendas have been materialized, hashed and checked against actual application and permit records in this change.

Do **not** report 20 measured lead times, 20 new industrial projects, a first-to-detect superiority claim, or newly available commercial bid opportunities. The 20-case report explicitly shows how many cases were actually available, how many were held for missing original records and how many independently proven publication intervals exist (initially zero).

## Follow-on acceptance

1. Obtain permitted exact PDC agenda PDF bytes and validate parser against at least 10 real item numbers and source PDF hashes.
2. Confirm Mississauga GIS planning exports and official permit/app-number lineage; where no permit includes the same app ID, hold, don't merge on address alone.
3. Complete 20 independently reviewed *actual* project identities across GTA, including source-linked original file IDs and the persisted Radar first-observation timestamps.
4. Use `gta_lead_time_proof.py` only after obtaining verified first-publication and later-permit posting dates. A meeting date is not a first-publication date.
5. Preserve all manual-run controls and US$1/day integrated DeepSeek limit. Existing municipal source access blocks and robots/authorization requirements remain in force.
