# Authorized municipal export intake — Burlington, Vaughan, Kitchener

This opt-in offline path closes the **data-format integration gap** only. It
does not grant website access, bypass robots or prove live source coverage.
Vaughan and Kitchener authorized-access requests were sent November 11, with
follow-ups on November 18, 2026. An automatic Vaughan acknowledgement is **not
permission**. Do not invent approval.

## Using a City-provided public CSV

1. Obtain a publisher-permitted CSV from an official City source, together
   with its reuse conditions. Do not scrape around blocked feeds.
2. In the existing Windows results folder
   `GTA_RADAR_RESULTS/GTA_RADAR_AUTHORIZED_EXPORTS/`, save the file as
   `kitchener.csv`, `vaughan.csv`, or `burlington.csv`.
3. Confirm the exact column headers in the supplied file. The application
   identifier must be **stable**; Kitchener's official dataset warns OBJECTID
   is not stable and should **not** be used as application number.
4. Generate its SHA256 from PowerShell:
   `(Get-FileHash .\kitchener.csv -Algorithm SHA256).Hash.ToLower()`.
5. Add a `manifest.json` in the same directory:

```json
{
  "exports": [
    {
      "city": "Kitchener",
      "permitted_public_export": true,
      "official_source_url": "https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/",
      "sha256": "REPLACE_WITH_ACTUAL_LOWERCASE_SHA256",
      "columns": {
        "application_id": "APPLICATION_NO",
        "address": "REPLACE_WITH_ACTUAL_ADDRESS_HEADER",
        "scope": "REPLACE_WITH_ACTUAL_DESCRIPTION_HEADER",
        "status": "REPLACE_WITH_ACTUAL_STATUS_HEADER",
        "application_date": "INDATE",
        "applicant": "REPLACE_IF_PRESENT"
      }
    }
  ]
}
```

Only the first three mappings are mandatory. **Do not enable the manifest
until the actual official CSV and legal reuse permission are confirmed.**

The next manual full run merges exact IDs conservatively into the same
24-city master and records `GTA_RADAR_AUTHORIZED_EXPORT_IMPORT_STATUS.json`.
This is **saved export evidence, not live city-wide coverage**.

Official Kitchener references:
- https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/
- https://app2.kitchener.ca/appdocs/GISImages/GIS_Web_External/GIS_Metadata_Open_Data/Planning_Applications_Active.html

## Existing unresolved access

- Vaughan: publisher response/permission or permitted export still required.
- Kitchener: a compliant download/export route and application stable-ID
  dataset mapping still need live verification. The City publishes GeoHub
  download options and `Planning_Applications_Active` metadata.
- Burlington: individual public planning pages and file IDs exist but
  completeness of its citywide application index remains unverified.

No export, historical master or index URL makes a verified open buyer contract.
