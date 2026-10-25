GTA RADAR - THREE OFFICIAL SOURCE REPAIR PACK V2
October 24, 2026 | Manual pilot only

This ZIP repairs/retests:
  1. IESO - use official published applicationstatusdata.json, not absent HTML table
  2. Brampton PDC - parse Planning & Development Committee meeting cards
     as well as 'Planning and Development Committee'
  3. Ajax - use Town's public ArcGIS planning MapServer layers 0/1,
     not old /bootrest application HTML index

Burlington already returned 29 records in your screenshot, so this pack
does not run Burlington.

INSTRUCTIONS
1. Locate the GTA Radar EARLY PILOT folder you extracted.
   Do NOT change or overwrite your V8 production folder.
2. Extract this repair ZIP into the root of that PILOT folder
   (same directory as early_cue_watch.py). Replace the supplied
   Python source files in the pilot folder when prompted.
   DO NOT delete/copy/overwrite the existing data subfolder;
   it contains important first-seen SQLite history.
3. Double-click RETEST_3_FAILED_SOURCES_V2.bat.
4. Read the '=== GTA Radar three official sources: exact diagnostics ==='
   section at the end of the terminal.
5. ZIP GTA_RADAR_RESULTS and send it here if any source reports
   FAILED / PARTIAL_CALENDAR_ONLY / UNKNOWN.

Status report files:
  GTA_RADAR_RESULTS\EARLY_CUES_SOURCE_STATUS.csv
  GTA_RADAR_RESULTS\EARLY_DISCOVERY_SOURCE_STATUS.csv
  GTA_RADAR_RESULTS\EARLY_AJAX_SOURCE_STATUS.csv

If a collector fails, the underlying HTTP / JSON / parser exception
is shown in the diagnostics. A publisher's 403, missing JSON or JavaScript
shell is NOT evidence of zero applications.

Python RequestsDependencyWarning from requests/urllib3/chardet is
independent of project-data parsing. If needed, manually upgrade via:
  py -3 -m pip install --upgrade requests urllib3 charset-normalizer

No V8 changes, no paid DeepSeek, no scheduled collection and no outreach.
All first successful source snapshots are baseline, not NEW project alerts.
Even SUCCESS does NOT establish a buyer or an open supplier contract.
