# Today's integrated GTA Radar manual run — November 13, 2026

## Single command (Windows PowerShell, from existing repository directory)

```powershell
.\RUN_GTA_RADAR_TODAY.bat
```

The existing launcher first safe-fast-forwards code to GitHub `main` when local tracked code is clean and update is fast-forward-only; it preserves the existing local `radar.sqlite`, existing first-seen history and source evidence. If code cannot be safely updated, the launcher stops before collecting. The manual daily collector runs **once**. It then performs industrial, activation, facility, Toronto 20-permit research, **three-city council index and agenda-item review**, and the free AI harness preflight. It writes a dated ZIP to the existing `GTA_RADAR_EXPORTS` directory. Daily DeepSeek spending is capped at the configured **US$1/day integrated ledger**, with no additional paid calls from council review. No automatic outreach or scheduling.

## Integrated council stage

The stage is `gta_council_integrated_manual.py` and is automatically invoked by `gta_monday_full_run.py` in the one-click launcher. It performs the existing three-city official meeting-index audit for Brampton, Mississauga and Toronto and **optionally** parses actual previously saved local documents, using each city’s different source-specific item extractor. It does not treat index links as project facts.

Documents must be registered in `GTA_RADAR_COUNCIL_INPUTS.json` at the existing `new data` workspace root. The file is optional; if absent, the run still performs the official three-city source-index audit, then explicitly reports no saved agenda documents registered. **It does not falsely claim to have parsed new Toronto/Brampton/Mississauga agenda content.** The optional manifest is the only path to original local document input in this release; there is no automatic PDF fetch or guessing of meeting/document IDs.

Example optional workspace manifest (replace all illustrative URLs with the **exact** original official source URLs; paths must exist under the workspace):

```json
{
  "version": 1,
  "documents": [
    {"city": "Toronto", "file": "council_sources/toronto_agenda.html",
     "meeting_url": "https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda"},
    {"city": "Brampton", "file": "council_sources/brampton_agenda.pdf",
     "meeting_url": "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
     "agenda_pdf_url": "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=12345"},
    {"city": "Mississauga", "file": "council_sources/mississauga_agenda.pdf",
     "agenda_pdf_url": "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234"}
  ],
  "matching_exports": {
    "applications_csv": "official_exports/applications.csv",
    "permits_csv": "official_exports/permits.csv"
  }
}
```

Replace the Toronto meeting ID and Brampton DocumentId placeholders; **do not invent official IDs or use this example as source evidence**. Mississauga DocumentId 82234 is an existing public example, but the registered local PDF must be the actual corresponding file. The matching CSVs are optional; when absent, the 20-case comparison reports its source deficiencies rather than fabricating matches. The comparison CSVs have required fields specified in `gta_agenda_application_permit_20_case.py`.

**Outputs and review:** `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/COUNCIL_INTEGRATED_REVIEW_STATUS.json`, per-city `SOURCE_INDEX`, `TORONTO`, `BRAMPTON`, `MISSISSAUGA` item-level CSV/JSON, and optional `MATCHING_REVIEW` twenty-case report. The daily full manifest is `GTA_RADAR_RESULTS/MONDAY_FULL_RADAR/MONDAY_FULL_RADAR_STATUS.json`, and the dated archive includes the new `COUNCIL_INTELLIGENCE_REVIEW` directory excluding logs, SQLite and secrets. The source document bytes are **not** included in the upload ZIP by default; item extraction outputs contain source URL and hash for provenance.

The council stage is **review-only**: a missing input file, unpermitted index, unreadable agenda item structure, ambiguous permit link or missing origin date remains a documented HOLD, not a sale-ready opportunity. The 20 original Toronto permit-record source baseline remains in `research/agenda_20_real_permit_coverage_baseline_20261113.json`; that is not a confirmed 20-project early-discovery advantage.

**Owner execution remains necessary** for an actual November 13 data run on the Windows PC holding the original persistent ledger and sources. CI validates code only; no claim of a fresh source run or verified new buyer is made solely from a successful GitHub merge.
