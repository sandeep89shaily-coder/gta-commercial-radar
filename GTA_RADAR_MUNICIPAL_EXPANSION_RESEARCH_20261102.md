# GTA Radar — next municipal intelligence source research
**Research date:** 2026-11-02 · **Scope:** Southern Ontario expansion beyond the eight configured municipal meeting indexes.  
**Goal:** Freshness First. Evidence Always. Early, independently sourced commercial development intelligence competitive in usefulness with GROUND and Datum.

## What is already configured (do not confuse configuration with live coverage)
The `municipal_meeting_capture.py` normal daily meeting-index list contains Toronto, Brampton, Mississauga, Hamilton, Burlington, Oakville, Vaughan and Kitchener. The bounded same-host PDF adapter is **not** proof of successful live retrieval in the seven non-Toronto cities. The owner's current Windows live-run metrics must determine actual functioning coverage. This research adds **no new live city collectors or paid API spend**.

## Priority A: early application data, not just meetings
Public official municipal sources, checked 2026-11-02. Feasibility is **preliminary architectural judgment** from published pages; not a live robots/HTML/API/PDF test. File reference **is not** first-publication timestamp; independently capture the source's date if available.

| Priority | City | Best official public source | Early intelligence provided | Initial integration hypothesis |
|---|---|---|---|---|
| 1 | **Markham** | [Circulated planning applications + agendas](https://www.markham.ca/economic-development-business/planning-development-services/current-planning-applications-and-agendas) | **Biweekly circulation PDFs**, file IDs, addresses, descriptions, dates, anticipated approval route; public meeting information reports, ePLAN search | High-value PDF index + application-ID parser; source date is circulation interval, not proven publication |
| 2 | **Oshawa** | [Active development applications](https://www.oshawa.ca/business-development/planning-and-development/development-applications/) | File numbers, property location, proposals, named corporate applicants, meeting status; industrial and commercial examples | Structured HTML stage extraction, watch additions and status changes; council reports as corroboration |
| 3 | **Milton** | [Dated development application notices](https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/) and [ward applications](https://www.milton.ca/business-development/planning-and-development/development-applications/ward-4-development-applications/) | Dated complete applications, zoning and subdivision IDs, applicants, project descriptions, staged supporting studies including employment lands | Dated notice feed first, ward-detail attachment second, then council reports |
| 4 | **Halton Hills** | [Development proposals under review](https://www.haltonhills.ca/developmentproposalsunderreview) | Application file numbers, descriptions, locations and status; the **401–407 Premier Gateway Business Park** grouping | Page/map data source inspection and stable file ID extraction; do not rely on third-party derivative tracking |
| 5 | **Caledon** | [Development applications](https://www.caledon.ca/en/town-services/development-applications.aspx), [planning public meetings](https://www.caledon.ca/en/town-services/public-meetings-planning-and-development.aspx), [council eSCRIBE](https://www.caledon.ca/en/government/agendas-and-minutes.aspx) | Application numbers, applicants, dates, project notices; pre-consultation program exists but confidential content should never be inferred or scraped | Official public application notice pages now; eSCRIBE adapter only after permitted fetch test |
| 6 | **Cambridge** | [Current development applications and submissions](https://www.cambridge.ca/business-building-development/building-planning/current-development-applications/) | Supporting studies, planning reports, technical documents, application IDs and project changes | Detailed HTML extraction + allowed linked reports; some materials require contacting staff and are **not auto-fetchable** |
| 7 | **Waterloo (City)** | [Public planning projects](https://www.engagewr.ca/development-planning-projects) | Public project titles, zoning/OPA IDs and proposal descriptions | Page-level structured parse with explicit dates; test dynamic site delivery |
| 8 | **Guelph** | [Current development applications](https://guelph.ca/city-government/planning-and-development/current-development-applications/), [planning updates](https://guelph.ca/city-government/planning-and-development/) | Named current applications, industrial/employment area developments, dated public updates | Publication-aware HTML feed + staff report links |

## Priority B: Durham + York municipal coverage
| City / tier | Official source | Why it matters / special handling |
|---|---|---|
| **Pickering** | [Pre-submission and public development proposals](https://www.pickering.ca/news/categories/development-proposals/) | **Pre-submission projects** can precede formal planning applications: treat as potentially early, and keep their own phase. [Meeting calendar](https://www.pickering.ca/meetings) publicly reports **intermittent calendar disruptions**; use proposals as primary, calendar as corroboration |
| **Whitby** | [Statutory public planning notices](https://www.whitby.ca/town-hall/council-and-committee-meetings/participation-at-public-meetings/) | Lists active proposals and usually publishes staff reports about a week before planning meetings |
| **Clarington** | [Agendas, minutes and reports](https://www.clarington.net/town-hall/mayor-and-council/council-meeting-calendar/agendas-minutes-and-reports/) | Official council reports plus searchable historical archive; regular agendas by noon Friday before meeting |
| **Ajax** | [Meeting and agenda calendar](https://ajax.ca/town-hall/online-meetings/) | Calendar and public committee items, including adjustments; confirm portal/API access |
| **Durham Region** | [Regional council and committee agendas](https://www.durham.ca/regional-government/council/agendas-and-minutes/) | Regional infrastructure and development context; Friday afternoon agenda publication the prior week |
| **Richmond Hill** | [Council agendas, reports and meeting materials](https://www.richmondhill.ca/en/living-here/Council-Meetings-Agendas-and-Minutes.aspx), [adjustment staff reports](https://www.richmondhill.ca/en/learn-more/committee-of-adjustment-meeting-agendas---staff-reports.aspx) | Planning reports, drawing and hearing material listed in Council Calendar from May 7, 2026 |
| **Aurora** | [Meeting agendas and public planning](https://www.aurora.ca/your-government/council-and-committees/agendas-and-minutes/) | Public Planning agendas usually one week before meetings; council agendas Thursday prior |
| **Newmarket** | [Council and committee meeting schedule](https://www.newmarket.ca/local-government/council/council-meetings) and [Committee of Adjustment](https://www.newmarket.ca/business-development/development-planning/development-applications/committee-adjustment) | Committee of Whole agendas generally **9 days ahead**, Council **3 days ahead**; planning portal mentioned |
| **York Region** | [Regional agendas, minutes and reports](https://yorkmain.acquiaedge.net/york-region/council-and-committee/agendas-minutes-and-reports) | Regional reports posted Friday evenings before meetings; confirm canonical domain and portal backend before integration |

## Priority C: regional overlap, additional cities and differentiation
| Jurisdiction | Official source | Focus |
|---|---|---|
| **Peel Region** | [Agendas, minutes and reports](https://peelregion.ca/about/peel-region-council/agendas-minutes-reports) | Regional infrastructure and planning; agendas approx. one week prior; **do not duplicate** municipal project entities |
| **Halton Region** | [Council and committee documents](https://www.halton.ca/the-region/regional-council-and-committees/council-committee-documents) | Region posts council agendas Friday morning roughly 1.5 weeks before meetings |
| **Waterloo Region** | [Agendas, minutes and webcasts](https://www.regionofwaterloo.ca/government-and-council/council/agendas-minutes-and-webcasts/) | Regional infrastructure; agendas week before, addenda day before |
| **Niagara Region** | [Regional council and committees](https://www.niagararegion.ca/government/council/default.aspx?home_task=1) | Regional reports and infrastructure; require calendar backend identification |
| **St. Catharines** | [Council and agenda access](https://www.stcatharines.ca/council-and-administration/mayor-and-council/) | Niagara urban development and municipal capital projects |
| **Niagara Falls** | [Meeting agendas and minutes](https://niagarafalls.ca/city-government/city-council-and-mayor/agendas-minutes-and-schedule/) | Civic portal / video and meeting calendar; agendas Thursday before meeting |
| **Brantford** | [Council and committee agendas](https://www.brantford.ca/your-government/city-council/agendas-and-minutes/) | Industrial and employment expansion; public agenda calendar |
| **Halton Hills** | [Council meeting portal](https://www.haltonhills.ca/meetings-workshops) | eSCRIBE agenda corroboration in addition to high-priority planning list |

## Proposed engineering rollout (fixed acceptance gates)
1. **Application-first intake** for Markham, Oshawa, Milton and Halton Hills. Track source identity, exact municipal file ID, declared submission/circulation date vs later updates, description, applicant, source URL and durable first-observed timestamp. Keep full first-run baseline separate from new projects. No paid AI to classify an HTML index.
2. **Document attachments** from confirmed sources, with source-policy check, explicit host allowlists, bounded size/requests and PDF validity. Capture report page and exact quoted text. **Do not** claim that a dynamic eSCRIBE/Agenda portal is a document source until actual PDF capture works.
3. **AI extraction/identity assistance**: use the existing shared DeepSeek budget first. Request project type, proposer/developer and owner separately, stage, source dates, commercial sector and file IDs; retain source page/quote for each claim. Cheap deterministic parsing for known ID/date/address fields, AI for unstructured reports and conflicts.
4. **Exact ID merge, not address-only merge** into V6 project entities. Attach multiple OPA/ZBA/Site Plan IDs only where same-project evidence is strong; otherwise research candidate queue with human review. No "open procurement" claims without direct award/tender evidence.
5. **One integrated daily output** showing new source-dated applications, new/updated report content, verified project matches and budget-deferred AI. Preserve existing contact research, $0.25/day cap, manual decision-making and historical ledgers.

### Per-city acceptance checklist (must pass in a live Windows run)
- Official index fetch and robots/reuse checks pass
- Actual dated application or report accessible (not only an index)
- Stable application ID and original source link preserved
- File-by-file hash and source change deduplication works across 2 runs
- First-seen versus first-public/date-in-record accurately distinguished
- Extraction correctly identifies project scope and company role from **cited** content
- At least one independently hand-reviewed relevant project; false-positive/missed-example review
- Logs indicate redirects, blocked portals, missing attachments, partial content and backlog honestly

**Competitive benchmarking caution:** public source existence is not proof of independent first detection, and accessible competitor feeds cannot be systematically copied. No extra cities or APIs are considered deployed by this research-only memo.

## Research-specific findings of special value
- Markham's circulation PDFs include **file number, location, circulation date and approval route**: likely a higher-value early signal than its meeting agenda alone.
- Oshawa's active page contains explicit industrial and commercial proposals and the named applicant: strong source for evidence-grounded DeepSeek research.
- Milton's dated complete-application notices should be ingested independently from its ward-by-ward application pages; council dates are later lifecycle markers.
- Pickering publicly labels some **pre-submission** applications. Never collapse that phase into an issued building permit.
- Cambridge's active page references some document packages that require contacting planning staff; respect these limits and do not count them as downloaded.
- Halton Hills' official page groups applications in the **401–407 Premier Gateway Business Park**, useful for supplier-sector relevance.
- Source checks and exact developer/company matching are more valuable than growing an untested municipality count.

**Next execution order recommended:** Markham → Oshawa → Milton → Halton Hills → Caledon → Cambridge → Pickering, while registering regional council reports for later cross-source corroboration.
