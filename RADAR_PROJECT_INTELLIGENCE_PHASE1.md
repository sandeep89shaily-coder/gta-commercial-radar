# GTA Radar — evidence-first project intelligence (phase 1)

This upgrade builds a **derived** project intelligence layer on top of the permanent
`Data/radar_master.sqlite`. It does not replace V8, remove any historical records,
change source schedules, or make paid AI calls.

## What runs automatically

At the end of `radar_production.py --home HOME run`, after the V8 and early
feeds are imported, `radar_project_engine.build(HOME)`:

1. Reads commercially relevant official-source records already available in the
   master database. It intentionally excludes undifferentiated business registries.
2. Creates a project identity using a **published application reference together
   with a municipality**, where available. Otherwise every source record stays
   separate, even if multiple records have the same address.
3. Stores individual field values with source identifiers, record identifiers,
   source URLs, date basis and first-observed timestamps in `project_facts`.
4. Creates **REVIEW_REQUIRED** graph links when separate records have matching
   full numbered street addresses. These links NEVER merge projects automatically.
5. Exports a quality-gated project research view, separate identity review,
   possible duplicate review, and a document extraction review.

Outputs in `HOME/Results`:

- `GTA_RADAR_PROJECT_RESEARCH.csv` — candidate **projects for research**,
  **not sale-ready leads**.
- `GTA_RADAR_PROJECT_REVIEW.csv` — missing identity/source evidence,
  inactive statuses and other review failures.
- `GTA_RADAR_PROJECT_LINKS_REVIEW.csv` — same-address **possible** matches.
- `GTA_RADAR_DOCUMENT_REVIEW.csv` — readable or failed supplied documents.
- `GTA_RADAR_OPERATIONS.html` — operations dashboard with a new project section.

Buyer identity, actual purchasing decision maker, contract award status and
vendor selection always remain **UNVERIFIED/UNKNOWN** until independently
documented. Source application dates are not assumed to be website publication
dates. Historical imports are not new live detections.

## Add municipal staff reports, agenda attachments or meeting minutes

Create `HOME/Data/official_documents/manifest.csv` and put PDF, TXT or HTML
copies of **permitted public documents** in the same folder. Example:

```csv
filename,source_url,document_type,public_date,city,address,application_id
staff_report_01.pdf,https://example.municipality.ca/public-report.pdf,STAFF_REPORT,2026-10-02,Brampton,42 Queen Street,SP-123
meeting_minutes_02.pdf,https://example.municipality.ca/minutes.pdf,COMMITTEE_MINUTES,,Mississauga,,
```

Use **real source URLs**, not the illustrative examples above. File names must
be simple names in this folder, not relative paths to other directories. The
first 40 PDF pages are read locally, bounded to 30,000 characters and 12 MB.
Image-only/scanned PDFs are flagged for review rather than guessing through OCR.
A document gets project facts only where there is a commercial-use excerpt and
sufficient explicit municipality/application or street address information.
Extracted text is **not independent factual verification**.

**No unattended document downloading or video transcription in this phase.**
A separate source-specific permission and parser review must precede broad
automated collection of third-party municipal meeting portals. The previous
Brampton eSCRIBE JavaScript-shell limitation is not magically solved.

## Build without collecting

With the installed Radar Python virtual environment, run:

```text
python radar_project_engine.py --home "C:\\Users\\YOU\\Desktop\\GTA_RADAR" build
python radar_production.py --home "C:\\Users\\YOU\\Desktop\\GTA_RADAR" dashboard
```

The first build scans the existing master database and may take several minutes.
It is idempotent; the source evidence, V8 database and recorded historical events
are preserved. Don't run two collections at the same time.

## Evidence integrity / limitations

- Source **names** or raw record descriptions may be inaccurate or out of date.
- Exact municipal application references can be reused or renamed; cross-source
  app-reference grouping still needs periodic auditing.
- Same-address links are suggestions, never proof of one underlying project.
- A quoted staff-report excerpt proves that the supplied document contained
  text, not that a project, operator or purchasing opportunity is independently verified.
- All project candidates are REVIEW/RESEARCH only. No customer outreach triggered.
- Zero API use; DeepSeek stays OFF.
- If no matching source records/documents are available, the outputs can be empty;
  emptiness is not proof of no regional opportunities.

## Next phases (not represented as done)

* Official PDF links discovered/downloaded with source-specific permission checks
  and per-portal HTML or agenda attachment extraction.
* OCR for scanned files; optional meeting transcription only if it adds signal.
* Independently confirmed operator identity, role and buyer contact.
* Supplier award checks; blind field scoring calibrated against real examples.
* Real lead-time comparison with a saved prospective first-observation trail.

Run offline CI tests using `python -m unittest discover -s tests`.
