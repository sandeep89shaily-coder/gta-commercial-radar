# GTA Radar — one permanent workspace (foundation)

This is the **first consolidation change**, not a claim that the 29-feed local
experiment is already deployed or that buying opportunities are verified.

## Objective

Use **one durable folder** rather than installing a new isolated test folder
with each revision. Consolidate already collected public-source evidence into
one SQLite master index while preserving original collector databases and
source-specific first-seen history.

On Windows, from a checkout of the development branch with Python installed:

    python radar_workspace.py --home "C:\GTA_Radar" init
    python radar_workspace.py --home "C:\GTA_Radar" import "C:\path\to\GTA_RADAR_FULL_SYSTEM_TEST" "C:\path\to\GTA_RADAR_EARLY_TEST"
    python radar_workspace.py --home "C:\GTA_Radar" status

These commands **do not make web requests, use DeepSeek, change scheduled
tasks, or change any original database**. Import is repeatable: the second run
doesn't re-add unchanged record versions. A corrupt legacy database is reported
without erasing previously imported evidence.

The file "C:\GTA_Radar\Data\radar_master.sqlite" stores normalized snapshot
records, record versions, historical observed change events, and reported
per-feed statuses with their source provenance. Original source data and
separate pilot SQLite schemas remain unchanged.

To run the early collectors into this same permanent workspace, use:

    python radar_workspace.py --home "C:\GTA_Radar" collect

This uses the currently committed early investment runners, without DeepSeek;
the local Business Openings and latest full-system experimental code require
explicit integration into this GitHub branch before claiming all 29 feeds.
Collection failures must be examined in "Results\EARLY_LOGS". The command
does not claim 100% source success just because records exist.

## Safety and limitations

- Importing source snapshots is **historical ingestion**, not evidence that
  newly discovered or unawarded opportunities exist.
- Records share one database but are **not yet verified as the same project**.
  Buyer/project entity resolution, source coverage, automatic unattended
  scheduling, client views, and controlled AI investigation are **next steps**.
- Source timestamps are retained separately from the import date.
- Failures and incomplete feeds are recorded; they are not zero leads.
- No automatic migration/reset of the user's existing Windows installations.
- No environment variable or API key is copied, printed, or saved.
- Research remains off by default; the prior local US$0.25/day DeepSeek software
  cap is not a provider-wide spending limit.

**Coverage note:** This first importer recognizes SQLite `snapshots` and
`changes` tables used by the early pilots. Databases with other schemas,
including the old V8 core database, are **counted as unsupported** rather than
misreported as successfully imported. Their original files are untouched;
a dedicated V8 adapter will be needed before claiming complete history.
