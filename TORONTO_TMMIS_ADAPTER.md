# Toronto TMMIS — first source-specific document adapter

Grounded on the City of Toronto's own TMMIS meeting documentation and the
public City Council agenda for May 20, 2026:
- https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda
- https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf

The former visibly links to the latter as a background report. This is an
example **of a confirmed indexed link, not a successful automated PDF
download or rights-to-resell validation**.

## What works now

Run against saved official public agenda HTML (no internet access):

```
python toronto_tmmis_documents.py --agenda-html meeting.html --meeting-url "https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda" --out meeting_pdf_links.csv
```

It outputs unique official background-report PDF URLs and marks every source
`DISCOVERED_NOT_FETCHED`, publication date `UNVERIFIED`. No source URL
is inferred from an address or GIS record.

`extract_local_pdf(path)` extracts text from an explicitly supplied,
already-downloaded, digitally readable PDF and flags blank/scanned files
for OCR review; `pypdf` is an optional dependency required only for
that function. No automated OCR, network, data upload or paid AI is used.

## Not yet operational

- Live source discovery from an agenda date range
- Permission/robots validation per source host
- Automated PDF retrieval and extraction with per-file evidence dates
- Project ID linkage, document citation review, commercial qualification
- V8 daily scheduler integration

The adapter is deliberately review-only. It does not touch the user's
existing `GTA_RADAR_RESULTS` or Radar database.

Next acceptance: one dated agenda HTML and linked staff-report PDF fetched
through a policy-compliant access path, independently checked for date,
content-type, checksum and extraction fidelity.
