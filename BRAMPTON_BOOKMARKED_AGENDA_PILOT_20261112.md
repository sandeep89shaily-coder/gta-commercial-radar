# Brampton bookmarked-PDF agenda intelligence — controlled pilot (November 2026)

## Official rationale
Brampton's [General Agenda Information](https://www.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/Pages/General-Information.aspx) explicitly says City Council and Planning and Development Committee agendas are supplied as **single PDF files with bookmarks to individual agenda items** and supplementary information can be added close to or during the meeting. This is a fundamentally different input format from Toronto TMMIS HTML agenda items. The official posting schedule is not independent evidence for the publication date of any particular PDF.

## Implemented
`gta_brampton_bookmarked_agenda.py` reads an already-authorized, locally saved Brampton agenda PDF. A PDF bookmark yields its title, page reference, depth, and hierarchy. Results include an exact SHA-256 of the saved PDF and a bounded screen of bookmark titles for industrial, commercial or planning terminology.

The module maintains a persistent ledger for repeat analyses of the **same meeting page/source**, distinguishing an initial local baseline, identical bytes and a revised saved PDF. Revision does not imply a newly announced project, approval, procurement or new publication date. All outputs are review-only.

```powershell
python gta_brampton_bookmarked_agenda.py --pdf "C:\Research\brampton_agenda.pdf" --meeting-url "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/" --agenda-pdf-url "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=EXACT_OFFICIAL_ID" --out "C:\Research\brampton_review"
```

Replace the illustrative URL with the **actual** official agenda PDF source URL. Do not guess a document ID. A saved PDF is a file supplied by the operator or obtained through existing authorized collector controls; this script performs no network access.

Outputs:
- `BRAMPTON_AGENDA_BOOKMARK_ITEMS_REVIEW.csv`
- `BRAMPTON_AGENDA_BOOKMARK_AUDIT.json`
- `BRAMPTON_AGENDA_PDF_VERSIONS.json`

Current limitations: PDF outline/bookmark structure must exist. This extracts bookmark titles and associated starting pages, not document-body commercial facts. It does not validate that every agenda item is bookmarked or that the input PDF matches the cited URL; manual source verification is required. The same generic meeting index URL should not be used for two distinct meeting PDFs in one ledger—provide unique authoritative meeting URLs to preserve identity. No restricted/closed agenda download, bypass, automated transcript, DeepSeek call, or production-project promotion is performed.

## Acceptance gates
1. Independently verify three actual Brampton bookmarked agenda PDFs, specifically Planning and Development Committee packages, and check the extraction against actual bookmarks/page numbers.
2. Confirm whether revised packages preserve the original PDF URL or use new document IDs; reconcile meeting identities when URLs change.
3. Pair bookmarked items with exact text/page citations and authoritative application identifiers before any project promotion.
4. Build a separate source-specific adapter for Mississauga, whose official Council and Committees calendar offers meeting documents but is not documented as a Brampton-style bookmarked-PDF system.
5. Compare 20 confirmed source-backed early projects across the three-city pilot with the existing permit/application collector and measure genuine first-published lead time.

US$1/day integrated DeepSeek ceiling and manual operation remain unchanged.
