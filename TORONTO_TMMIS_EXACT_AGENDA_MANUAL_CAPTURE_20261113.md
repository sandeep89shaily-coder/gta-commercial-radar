# Toronto TMMIS exact-agenda collection — manual collector bridge (Nov 13, 2026)

## Official source verification

Toronto's own [TMMIS help](https://www.toronto.ca/legdocs/tmmis/help/help1.htm) says public council/committee agendas are dynamically published, agenda items have stable item numbers, and background information includes original report links. The City Clerk also maintains meeting schedule data, but an older schedule record is not proof of an agenda item's first publication.

Official sample public meetings confirmed by original City pages:
- [May 7, 2026 Planning and Housing Committee](https://secure.toronto.ca/council/report.do?meeting=2026.PH30&type=agenda), item PH30.1 and background staff reports.
- [May 20, 2026 City Council](https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda), item RM41.1 and more. These historical examples are **not fresh November opportunities**.

## New bounded collector

`gta_toronto_tmmis_authorized_agendas.py` takes at most three **exact, independently identified TMMIS meeting agenda URLs** (the already-established strict `toronto_tmmis_documents.agenda_url` allowlist), checks public DNS, published robots policy, no redirects, exact host/path/type, HTML MIME, and 8 MB cap before saving source HTML and invoking the existing item-level/background-PDF-link extractor. It records the original meeting URL and the HTML content hash, with an explicit unverified-original-publication indicator.

This is integrated into the existing `gta_council_integrated_manual.py` stage **only for a fresh manual daily run**, using the optional workspace configuration `GTA_RADAR_COUNCIL_INPUTS.json`:

```json
{
  "version": 1,
  "documents": [],
  "toronto_meeting_urls": [
    "https://secure.toronto.ca/council/report.do?meeting=2026.PH30&type=agenda"
  ]
}
```

**Replace this historical example with a current original meeting URL independently located on the City's official schedule.** The program deliberately does not guess or increment TMMIS meeting identifiers. Without actual registered official URLs, the run safely skips the extra network fetch and reports a source discovery gap.

The combined dated results ZIP includes `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/TORONTO_TMMIS_OFFICIAL` when this optional source is used. The source body, extracted item titles and report links remain review-only. The system does not automatically create buyers, tenders or verified new projects from them.

## Remaining source gap

The existing `municipal_meeting_capture.py` Toronto index still reads the official **watch meetings** webpage, not the dynamically published TMMIS meeting calendar. That index cannot by itself reliably discover current meeting IDs, so an original City schedule/committee lookup adapter or permission-approved official feed is still needed before claiming fully automatic current-incident collection. This change **connects retrieval to the usable downstream parser, but does not resolve that upstream dynamic discovery bottleneck**.

No paid AI, scheduled operations, additional collection pass, database mutation, hidden URL enumeration or account-spend changes were introduced.
