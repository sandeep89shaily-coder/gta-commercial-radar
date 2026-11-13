# Toronto City Clerk schedule → verified TMMIS agenda-item collector — Nov 13, 2026

## Genuine new functionality

The existing Toronto Open Data schedule collector (PR #195) contained exact dates, the committee name and meeting numbers, but **zero original agenda links**. TMMIS itself publishes a different original City endpoint for *Agenda Item List*: `https://secure.toronto.ca/council/agenda-items.do?meeting=2026.PH31`. The real City page for Planning and Housing Committee Meeting 31 explicitly shows June 11, 2026 and numbered items `PH31.1`, `PH31.2`, etc. This is a real published City page, **not** an invented fixture URL.

Sources:
- Official City item list: https://secure.toronto.ca/council/agenda-items.do?meeting=2026.PH31
- Official City Clerk schedule catalogue: https://open.toronto.ca/dataset/3bfab808-105b-45ab-8d92-cf1916594653/
- Official TMMIS help: https://www.toronto.ca/legdocs/tmmis/help/help1.htm

The new `gta_toronto_schedule_tmmis_bridge.py` uses **only recent original City Clerk 2022–2026 schedule rows labeled exactly `Planning and Housing Committee`**, derives **at most three candidate** canonical item-list URLs from year/meeting number, and checks the official TMMIS response before accepting anything. Candidate URLs are not counted as verified source links or project evidence. The validation requires the independent response page's *committee heading, identical meeting number, identical calendar date, and one or more actual numbered `PH<number>.<item>` headings* to match the City Clerk schedule. All deviations are held.

Each eligible response passes public DNS, robots policy, exact HTTPS host/path, no redirect, HTML MIME and bounded-size checks. No arbitrary ID enumeration or iteration across meeting numbers is performed.

The adapter captures:

- City meeting date and exact original agenda item codes and headings
- Original official TMMIS source URL and HTML SHA-256
- Per-item local first-observed timestamp and stable title-change/first-observation ledger; existing history retained after source failures
- Explicit **review-only** fields: original publisher posting date, buyer, project and open procurement are **all unverified**
- Failure evidence for blocked TMMIS requests, date/meeting mismatch, 404, changed HTML or missing schedule CSV

Outputs: `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/TORONTO_PH_TMMIS_AGENDA_ITEMS/TORONTO_PH_AGENDA_ITEMS_REVIEW.csv`, status JSON and first-observed ledger. The existing dated ZIP captures CSV/JSON from that folder.

The existing **manual fresh Radar launcher** already triggers the official schedule stage. The new agenda verification executes right after it, with no separate user command. It will refuse to fetch if the schedule fetch failed on this run; a stale source CSV from a previous run cannot authorize a fetch.

## Important limits

1. This is a **single verified committee mapping (Planning and Housing Committee / PH)** to prevent accidentally using a different committee's meeting number. Other committees must be independently validated before expansion.
2. The published TMMIS *Agenda Item List* is not the full item history or associated original background PDFs. The separate TMMIS `report.do` / `agenda-item.do` adapters remain independent, and cross-source matching needs further work.
3. A parsed title is not automatically a new proposed development. Changes in meeting schedule, official agendas and actual applications are different events.
4. A valid CI test is not an owner-side live collection result; the next real manual-run ZIP is still needed to measure how many actual current PH meeting item lists were received.
5. This work adds no paid AI, scheduling, database mutation, auto outreach or silent customer-ready leads. The existing US$1/day AI cap remains unchanged.
