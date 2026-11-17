# Three-city official-source expansion pilot — November 17, 2026

This is an **experimental, non-billing** source upgrade in the normal
RUN_GTA_RADAR_TODAY.bat launcher. It does **not** change the core sixteen-city
coverage denominator, source baseline, DeepSeek limits or customer-release gate.

## Changes

1. **Niagara Falls:** enrich a bounded batch (up to 18) from the existing
   GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv. Follow only exact
   https://webpublic.niagarafalls.ca/Planning/Details/<numeric-id> links.
   Match the City file number in the detail-page heading. Capture the actual
   proposed construction scope, meeting date, planner contact and labels of
   official posted supporting files. A future meeting is NOT an original
   publication date or open bid. The existing 58-record GGH baseline remains.
2. **City of Brantford:** separately query City's two explicitly configured
   open-data ArcGIS layers (planning applications and building permits).
   County of Brant is **not** Brantford. Validate metadata to identify City
   file number/permit number before querying. Bounded to two pages of the
   100 most recent object IDs per layer; sort newest first. Capture the
   applicant, city planner email, address, scope, submitted date or permit
   issue date **only when each named source field is published**. Those
   dates are not original construction announcements. The city may block
   API queries; do not defeat robots/TLS/authentication or imply 200 rows
   means entire municipal coverage.
3. **St. Catharines:** inspect a bounded set (up to 14) of individual planning
   notice pages linked from the City's official public-notices index.
   Capture distinct notice-posting and application-complete dates,
   project-specific scope, published City file numbers and public planner
   contact. A notice about an application completed the previous year
   remains a historical application unless a **genuinely new scope** is
   verified separately. The existing restricted permit-export audit remains.

All fetches use configured HTTPS official domains, public DNS, robots checks,
TLS verification, no redirects and response caps. Sources that are blocked,
empty or have unexpected schemas are explicitly held, not treated as covered
or converted into fake project IDs.

## Outputs (in every post-upgrade manual run archive)

- GTA_RADAR_THREE_CITY_EVIDENCE_CANDIDATES.csv: project-specific raw
  evidence for **manual research** only; official file number when published
- GTA_RADAR_THREE_CITY_EVIDENCE_CHANGED.csv: source content changes since
  the first successful local baseline; **not new public disclosures**
- GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json: per-source access errors,
  bounded record counts and limits; buyer/new-publication/open-bid flags zero
- GTA_RADAR_THREE_CITY_EVIDENCE_SEEN.json: persistent first-observed/digest
  history. Do not delete or reset between runs to manufacture new opportunities.
- MONDAY_FULL_RADAR/MONDAY_FULL_RADAR_STATUS.json:
  experimental_three_city_evidence section, including per-source status
  and no buyer/procurement/publication claims.

An injected runner in tests and --skip-collection historic mode never make
live web calls. Additional collection costs **$0 paid AI**. A failure cannot
cause source data to be labelled as a fresh opportunity.

## Source references

Niagara Falls: https://webpublic.niagarafalls.ca/Planning/
St. Catharines: https://www.stcatharines.ca/news/public-notices/?page=1

City of Brantford (NOT County of Brant):
https://services.arcgis.com/aji2lCmjXt0KpGzI/ArcGIS/rest/services/Planning_Application_Open_Data_view/FeatureServer/0
https://services.arcgis.com/aji2lCmjXt0KpGzI/ArcGIS/rest/services/City_of_Brantford_Building_Permits_view/FeatureServer/0

The Brantford ArcGIS URLs were identified from official catalog/index evidence;
successful live metadata and permitted queries must be confirmed in the next
owner-side run before calling either a working collector.

## Offline test

python -m unittest tests.test_three_city_evidence_pilots -v

## Acceptance after owner-side Windows run

A source is **working** only when the owner ZIP includes an actual fetched
count and saved source records with exact application IDs. Record identity,
scope, published contact roles and distinct dates should be verified against
at least five original notice/detail pages per city where available. Open
supplier procurement and verified purchasing authority stay zero until
independently established. If access is blocked, request an official export
instead of substituting the County of Brant or any unrelated GIS source.
