# GTA Radar — Northern major-city priority expansion (November 17, 2026)

Owner direction: prioritize **Barrie, Greater Sudbury, North Bay** before
small municipalities around Barrie. Defer new engineering work on nearby small
municipalities; retain existing live feeds and their baselines.

## Experimental source adapters

| Priority | City | Official sources | Evidence fields and limitations |
| --- | --- | --- | --- |
| 1 | Barrie | https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/Planning/MapServer/4 | File_No, address, proposal, status, Applicant_Owner, Date_Application_Received. Receipt date is not original publication. Does not reset old 24-row AnnexedLand GGH pilot. |
| 1 | Barrie | https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/APLI/MapServer/1 | Issued permits RECORD_ID, Full_Address, Description, RECORD_STATUS and Date_Status. Issue/status date is not open procurement. |
| 1 | Barrie | https://gispublic.barrie.ca/arcgis/rest/services/Open_Data/APLI/MapServer/0 | Metadata monitor only: public layer exposes subtype/status/date, not stable permit number or address. No individual permits invented. |
| 2 | Greater Sudbury | https://www.greatersudbury.ca/do-business/planning-and-development/pending-planning-applications/ | Extract exact PL- file IDs where shown; names, site, commercial scope, receipt date. Without exact file ID, applicant+address becomes unverified project-only signal. Index-only HTML is reported as such. |
| 3 | North Bay | https://northbay.ca/city-government/media-room/public-notices/ | Bounded pages of project-specific planning notices. Exact ID only when published, source date only with actual time metadata. Official applicant portal is not a verified public feed. |

## Guardrails

- Original 16-city measured coverage and all prior city ledgers are preserved.
- First-ever source observations establish baseline, **not a newly published project**.
- Subsequent changes to source text are review-only, not first-publication proof.
- Project applicant is not verified purchasing authority.
- No additional DeepSeek calls or automatic outreach. Open supplier packages unverified.
- Policy-safe public DNS, robots checks of exact requested ArcGIS URLs, HTTPS
  official hosts, TLS validation, no redirects, byte and page caps.
- Metadata and named fields validated before GIS queries.
- Barrie active permit layer is metadata-only until actual permit identifiers
  and addresses or an authorized alternative are available.
- Barrie query is bounded and reports incomplete/sampled coverage explicitly.
- Sudbury and North Bay HTML may prove index-only; measure actual live output.

## Operator workflow

Normal RUN_GTA_RADAR_TODAY.bat invokes these three northern major-city lanes
in a real manual full collection. Skip-collection and injected CI tests do not
perform additional network calls.

New root-level outputs in GTA_RADAR_RESULTS and the dated ZIP:
- GTA_RADAR_NORTHERN_MAJOR_CITY_EVIDENCE.csv
- GTA_RADAR_NORTHERN_MAJOR_CITY_SOURCE_CHANGES.csv
- GTA_RADAR_NORTHERN_MAJOR_CITY_STATUS.json

Local persistent ledger:
- GTA_RADAR_NORTHERN_MAJOR_CITY_LEDGER.json

Full manual report section: northern_major_city_sources.
Original customer-release gates are unaffected.

## Acceptance in next owner-side ZIP

1. Barrie planning and issued-permit query status, source row counts, exact
   file/permit numbers, applicant names, dates, and sample/truncation flag.
2. Sudbury exact-ID candidates versus named project-only signals or index-only.
3. North Bay official planning articles fetched and exact-number ratio,
   or explicit no-public-project-data status.
4. Review at least five original applications/notices per working city,
   validating scope, source date, applicant and possible unawarded buying work.
5. Do not call 3 cities fully operational or call any buyer/contract verified
   merely because the source API returned records.

Later major-market candidates: Sault Ste. Marie, Thunder Bay and Timmins.
