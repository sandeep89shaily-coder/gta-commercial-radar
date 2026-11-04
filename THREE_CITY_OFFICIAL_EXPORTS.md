# Three-city official early-planning exports

Automated ArcGIS collection is **not authorized** on the tested City of Kitchener and York Region feature-host targets under their current robots policies. Do not change headers, use proxy domains, or bypass robots. The download/export buttons in the publisher's ordinary UI may be used manually, or request an authorized machine-readable export from the publisher.

## Permitted-assisted intake into the existing daily runner

Create `GTA_RADAR_RESULTS/official_exports/` in your existing Desktop workspace.

- Kitchener: obtain the City of Kitchener's **Planning Applications Active** official CSV using the official Open Data/GeoHub download interface: https://www.arcgis.com/home/item.html?id=b7e2f8feda7340eaa5f4dd7b9c4d5ac0 . Place it as `KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv`. Its columns must include `APPLICATION_NO` and `DESCRIPTION`.
- Vaughan: obtain York Region's **Active Development Application** official CSV from its own Open Data interface: https://www.arcgis.com/home/item.html?id=d599fcc0898f42ad8b58fd376bcdbf54 . Place it as `YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv`. It must include `MUN_NAME`, `REG_FILE_NUM`, and `APPL_DESC`. Only rows with municipality Vaughan and true `REG_FILE_NUM` or `EXT_REF_NUM` are accepted.
- Burlington: the two official City GIS layers publish only named project signals without application-number fields. There is no verified automated file-ID feed; official planning pages visibly contain file numbers, but automated fetching is restricted. Do not fill the gap with invented numbers.

Now run the normal `RUN_TOTAL_INTELLIGENCE_TODAY.bat` or simply

```powershell
python gta_three_city_official_csv.py --output ".\GTA_RADAR_RESULTS"
```

Results: `GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv`, `GTA_RADAR_OFFICIAL_CSV_IMPORT_NEW_OR_CHANGED.csv`, `GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json`, and a persistent first-seen ledger. The first import is a historical baseline; only subsequent first-observed IDs or meaningfully changed records are candidates for review.

**Limitations:** Assisted/manual CSVs are schema-checked but their origin is not cryptographically authenticated. They are deliberately kept **separate from the canonical auto-collected 16-city coverage count**, and cannot establish the original publication date of an application. The city coverage status remains 13/16 until successful permitted live application-ID fetching, independent origin checks and a repeated run are proved.


## Burlington saved-official-page application IDs (new)

The City's public development-project detail pages can show actual planning file
numbers even though its public GIS layer only returns project names and URLs.
For example, the City's page for **Alinea — Bronte Creek Meadows Phase 1**
publishes 505-02/26, 520-02/26, and 510-01/26. This is **not a new
automated, policy-cleared web scraper**: some city-page retrieval attempts
return HTTP 403, so use the normal browser's permitted Save Page action.

1. In `GTA_RADAR_RESULTS/official_exports/burlington_pages/`, save the
   HTML of one or more official Burlington project detail pages from
   `https://www.burlington.ca/en/news/current-development-projects/`.
   Save as HTML, not PDF, MHTML or screenshot.
2. Create `burlington_pages_manifest.csv` in the same directory with
   exactly these headers: `url,html_file`. Example:

   ```csv
   url,html_file
   https://www.burlington.ca/en/news/current-development-projects/alinea-bronte-creek-meadows-phase-1.aspx,alinea.html
   ```

3. Run normal `RUN_TOTAL_INTELLIGENCE_TODAY.bat` or:

   ```powershell
   python -c "from gta_burlington_official_pages import run; print(run('GTA_RADAR_RESULTS'))"
   ```

Outputs are `GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_APPLICATIONS.csv`,
`GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_NEW_OR_CHANGED.csv`, and
`GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_STATUS.json`.
Each validated file number becomes an **assisted, unverified** application
candidate with its exact official project-page URL. The first snapshot is
baseline-only; changes in later *saved* snapshots are observed changes, not
proof of a new city publication. File numbers never come from phone numbers,
meeting dates, or GIS OBJECTIDs. No saved pages means zero imported records.

This assisted intake remains **outside the automatic 13/16 coverage measure**.
Full coverage still requires permitted live collection, authentication of the
source records, repeat fetches, and application inventory validation.

## Kitchener schema and publisher support

Kitchener's official metadata documents an `APPLICATION_NO` column,
`DESCRIPTION`, `ADDRESS`, `INDATE`, `APPLICANT`, and
`PROPERTY_OWNER`; the ArcGIS layer is a real active-application feed.
The city's open-data policy explicitly offers CSV exports and REST/GeoJSON
interfaces, but a general data licence is not proof that this installation
can ignore ArcGIS-host robots restrictions. Continue using its official CSV
download UI or ask `gis@kitchener.ca` for authorized API/CSV access.
The existing `gta_three_city_official_csv.py` importer supports this.

## Vaughan / York provenance

York's open-data layer describes applications **being reviewed by York Region**
and is not a complete municipal Vaughan PLANit feed. A York file number is
not automatically a Vaughan municipal application number. Use the assisted
York export for regional-review intelligence and cross-check Vaughan's
PLANit application viewer before claiming complete Vaughan coverage.
No robots bypass, anti-bot workaround, or fabricated timestamps.
