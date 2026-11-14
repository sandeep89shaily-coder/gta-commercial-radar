# GTA Radar: one-click document review preview (2026-10-26)

**No installation, scheduler updates, paid AI, API keys, collector runs or database migrations.**
This creates review files only within the existing `GTA_RADAR_RESULTS` folder.

1. Download the ZIP of this **development branch** from GitHub.
2. Extract the ZIP anywhere (such as Downloads). Do not replace your production GTA Radar folder.
3. Double-click `RUN_DOCUMENT_REVIEW_PREVIEW.bat`.
4. If prompted, paste the location of your existing `GTA_RADAR_RESULTS` folder.
5. It opens `GTA_RADAR_DOCUMENT_OPERATIONS.html` automatically.

**With V8 results only:** The preview links V8 candidate IDs and investigations and displays a review queue. Documents processed = 0 until actual local TXT/HTML documents are supplied. That is not a failure.

**Optional documents:** Add lines to `GTA_RADAR_RESULTS\DOCUMENT_SOURCE_MANIFEST.csv` using `project_id,local_path,source_url,source_id,source_date,title`. Place TXT/HTML files inside the results folder; `local_path` is relative to the results folder. Run the launcher again. PDF parsing has not been implemented. Never place personal, confidential or unlicensed files into this review.

**Outputs:** `GTA_RADAR_DOCUMENT_OPERATIONS.html` and `DOCUMENT_REVIEW\*`. The module never overwrites existing V8 candidate/investigation files or databases and never declares a lead sale-ready.

**Important:** This is an isolated preview, **not** integration into the scheduled daily production dashboard. GitHub automated tests cannot verify your desktop deployment. Check the new review page before considering that next deployment step.
