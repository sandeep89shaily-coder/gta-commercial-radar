# ComIntel public opportunity edition — November 22, 2026

**Editorial date:** 2026-11-22 (America/Toronto)  
**Rolling inclusion dates:** November 18–22, inclusive (five calendar days).  
**Public feed:** `website/data/opportunities.json`  
**Approved for publication:** 7 research leads; **0 verified open supplier packages**.

## Input provenance and selection limitations

This edition used the user-supplied **GTA_RADAR_RESULTS_2026-11-22_082802.zip**
as the municipal source capture, together with independently checked City of
Toronto public notices and contemporary public permit-index corroboration.

That ZIP predates merging the new five-day all-candidates queue. Its
`GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_CHANGES.csv` has **119 rows, all Toronto**.
The raw rows were individually screened for *source event dates* between
November 18 and 22 (even though the ZIP's saved previous shortlist used a
three-day policy). This does NOT constitute exhaustive municipal coverage or
a complete November 18–22 live rerun across all configured municipalities.

All 5 permit leads below appear with exact source IDs and scope in the November
22 captured City Toronto active-permits extract. They are linked to an
ID-filtered **official Toronto Open Data CKAN source**, but the live API query
could not be independently fetched in this environment. Public permit-index
pages offered secondary corroboration. The source-check approval represents
the inspected, captured official-source row plus permitted source attribution,
**not** a live municipal status confirmation. The cards explicitly retain
the November 22 snapshot status and a date-basis disclaimer.

The two November 20 new *planning notices* were independently opened on
City of Toronto's official public-notice system and link to the precise
individual notice, not a homepage.

## Released cases

| Public dossier | Date basis | Original-source evidence | Why it is research-only |
| --- | --- | --- | --- |
| 1350 Sheppard Ave W — Arbo Phase 2 | Nov 20 official public notice | [City notice 8046](https://secure.toronto.ca/nm/api/individual/notice/8046.do) · 26 257236 NNY 06 OZ / 26 257298 NNY 06 SB | Planning application; no open construction packages verified |
| 60 Overlea Blvd — mixed-use towers | Nov 20 official public notice | [City notice 8047](https://secure.toronto.ca/nm/api/individual/notice/8047.do) · 26 253544 NNY 15 OZ | Planning amendment; no open contracts verified |
| 529 Carlingview Dr — industrial batching plant | Nov 20 municipal permit record | 26 272920 BLD · corroboration [The Permit Map](https://thepermitmap.com/) | Reinstallation proposed; supplier/equipment procurement unverified |
| 130 King St W — National Bank office fit-out | Nov 19 municipal permit record | 26 272291 BLD · corroboration [commercial permits](https://thepermitmap.com/structure/multiple-use-non-residential/) | Office tenant identified; buying authority not verified |
| 5207 Dundas St W — daycare fit-out | Nov 18 municipal permit record | 26 271554 BLD · corroboration [street permits](https://thepermitmap.com/street/dundas-st-w/) | Permit stage snapshot only |
| 55 University Ave — fire alarm panels | Nov 19 municipal permit record | 26 272511 FSU · corroboration [fire alarm permits](https://thepermitmap.com/work/fire-alarm/) | Procurement may already be assigned |
| 90 Wynford Dr — sprinkler revisions | Nov 20 municipal permit record | 26 272935 FSU · corroboration [sprinkler permits](https://thepermitmap.com/work/sprinklers/) | Contract availability not established |

The notices identify Build Canada Homes as the 1350 Sheppard *proponent*
and National Bank of Canada as an office *tenant* at 130 King. **Neither is
represented as verified buying authority**. All records set
`buyer_verified=false` and `open_supplier_package_verified=false`.

### Publication rights / attribution

Toronto active permit data:
[Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/),
which permits commercial re-use with attribution. The public page carries the
licence's attribution and no endorsement claim. The official notice briefs
summarize public municipal application facts and link to source notices.
No personal contacts, private enrichment, source ZIP, or confidential AI
research have been published.

### Held records / exclusions

**114** of the 119 older unified municipal daily rows remain unpublished.
Reasons include older source dates, already-issued permits, held/cancelled or
less actionable stages, duplicate / unspecific work, or lack of independent
corroboration. This is a **hold for more review**, not a conclusion that
114 companies have no prospective work.

Also deliberately excluded:

* **Ford Oakville** Nov 20 announcement:
  https://news.ontario.ca/en/release/1008308/ontario-welcomes-nearly-5-billion-investment-from-ford-of-canada-to-support-next-generation-auto-production
  — the factory had already reopened and commenced production. An announcement
  dated inside the rolling window is not necessarily an unawarded order.
* **Mississauga 2233/2235 Hurontario St** — the primary planning application
  predates the window. Do not repackage the old application as newly announced
  because a search snippet suggests a more recent page modification.
* Other historical Toronto development applications with recently changed
  statuses but without new substantive scope.

## Continuous publish behavior

The GitHub Pages workflow reacts to changes of the **editor-approved**
`website/data/opportunities.json` on `main` after this PR merges. It
runs its existing fail-closed schema validator and deploys only public assets.
**It does not automatically promote the private daily municipal/AI outputs**.

After each production Radar run, review the two **uncapped five-day CSVs** in
the local owner-only `website/publisher.html`; verify dated sources, rights
and scope and generate/commit the next approved JSON. The public website
also independently hides records older than four calendar days by source date.

No emails were sent. No private customer contacts or AI API secrets are included.
