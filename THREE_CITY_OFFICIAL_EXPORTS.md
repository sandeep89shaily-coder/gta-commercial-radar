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
