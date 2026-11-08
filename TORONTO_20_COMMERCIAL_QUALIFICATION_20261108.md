# Toronto 20 permit work packages — commercial research, 8 November 2026

**STATUS: INVESTIGATIVE. Zero verified project buyers, zero confirmed unawarded supplier contracts, zero authorized outreach.**

## Primary-source advancement

The City of Toronto Active Building Permits CKAN was queried using the exact permit and revision for **20 archived candidate records** from the previously uploaded Radar archive. [Live evidence run](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42498781230). All 20 exact keys and civic addresses matched, and all 20 permit descriptions were returned.

The official `EST_CONST_COST` field contained **14 genuine positive numeric estimated construction values**, totalling **CAD 6,525,090**, and **6 unparseable placeholder instruction strings**. The total includes a **Refusal Notice** permit for 29 Jutland Road valued at CAD 300,000; these are **individual permit estimates**, NOT tender values or available contract amounts. Date and status are snapshots.

The source-backed work descriptions and nullable numeric costs are saved in:
`research/toronto_20_city_exact_scope_20261108.json`.
The bounded replayable source checker is:
`gta_toronto_20_commercial_scope_recheck.py`.
`EST_CONST_COST` instruction text such as `DO NOT UPDATE OR DELETE THIS INFO FIELD` is now rejected instead of silently counted as an estimate.

## High-priority commercial investigation (NOT ranked by sale-ready status)

| Physical facility | Exact City permit scope | City estimate CAD | Stage | Evidence gap |
| --- | --- | ---: | --- | --- |
| 199 Bay St | Courtyard skylight removal/replacement; structural and drainage works | 1,500,000 | Application Acceptable | QuadReal / Commerce Court public property route; buyer and contractor unknown |
| 4711 Yonge St | Elevator lobbies, washrooms, corridors, interior common-area works | 700,000 | Application Acceptable | Menkes property route; purchasing authority not established |
| 250 The East Mall | Proposed Rexall pharmacy Unit 125 fit-out | 250,000 | Not Started | Mall management and Rexall real-estate channels; exact buyer not established |
| 568 Passmore Ave | Warehouse office, kitchenette and washroom partition fit-out | 500,000 | Not Started | Tenant, owner, GC and purchasing organization unknown |
| 220 Yonge St | Retail tenant interior alterations | 789,000 | Permit Issued | Cadillac Fairview property route; tenant and GC unknown, work may already be awarded |
| 300 Consilium Pl | Interior renovations floors 1–6 | 1,000,000 | Permit Issued | Leasing broker is not project buyer; contract timing unknown |
| 250 Front St W | Office + broadcasting studio conversion | 900,000 | Permit Issued | Public CBC supplier registration exists; this specific work not verified as open |
| 945 Middlefield Rd | Basketball training studio interior improvements | 40,000 | Application Acceptable | Medallion landlord route, not the studio operator/buyer |
| 29 Jutland Rd | Industrial office alterations, canopy removal | 300,000 | **Refusal Notice — HOLD** | Cannot treat as active without source status change |

**Correction:** 220 Yonge's exact permit estimate is CAD **789,000**, not CAD 2.5 million from a different address-level third-party record. Do not merge different projects by street address.

## Public business contact routes

`research/toronto_20_public_business_contact_routes_20261108.json` holds **12 company-published work channels spanning 11 exact project IDs**, including first-party documentation on Menkes, Commerce Court/QuadReal, Cloverdale/QuadReal, Rexall real estate, Medallion leasing, Cadillac Fairview, CBC supplier registration, Colliers leasing, GWL Realty Advisors and Brookfield property management. Three newly researched site-specific channels are Colliers/Beedie at **568 Passmore Ave**, Cadillac Fairview at **77 King St W**, and GWL Realty Advisors at **5160 Yonge St**. All three are leasing or property-service channels, **not** project purchasing-authority verification. Each entry links to original public corporate source and is explicitly **NOT** a verified buyer or unawarded contract. Generic phone/email channels and named professional real-estate/leasing staff are independent routes to research, not grounds for outreach or personal-contact claims.

### Contacts confirmed on business-published pages (8 November research)

| Facility | Public-facing role | Channel | Explicit uncertainty |
| --- | --- | --- | --- |
| 568 Passmore Ave | Colliers broker Newton Leung for Beedie Passworks | +1 416-791-7202; newton.leung@colliers.com; https://www.passworksbybeedie.com/ | Broker markets space, not proven buyer of the $500,000 proposed interior improvements |
| 77 King St W | Cadillac Fairview Tenant Projects Department | tdcprojects@cadillacfairview.com; +1 416-869-1144; https://assets.cadillacfairview.com/m/4ed6e2dbbf5194b6/original/TDC-Contruction-Manual-March-2025-1.pdf | Actual landlord tenant-improvement review route, **not** confirmed purchaser of the plumbing revision |
| 5160 Yonge St | GWL Realty Advisors, leasing contact Amanda Barker | +1 647-676-8035; Amanda.Barker@gwlra.com; https://gwlraleasing.com/building/5160-yonge-street/ | Office leasing agent, not verified purchaser of HVAC work |

The complete 12-route provenance file is machine-readable and tested in `tests/test_toronto_20_commercial_review.py`. It never fills buyer or open procurement flags from an address-level property or brokerage contact.

## Implemented offline production-safety research layer

`gta_toronto_20_commercial_review.py` joins official City exact-key/physical-site source records to only the specifically recorded public business routes. It produces:

- `GTA_RADAR_TORONTO_20_COMMERCIAL_QUALIFICATION.csv`: 20 ranked investigation records (priority for *research*, not open bids).
- `GTA_RADAR_TORONTO_PUBLIC_CONTACT_ROUTES_AUDIT.csv`: public company routes; exact project/site join; landlord, property manager, proposed tenant and broker clearly distinguished from actual purchasing authority.
- `GTA_RADAR_TORONTO_20_COMMERCIAL_STATUS.json`: source/cost coverage, contact count, stage categories, and **zero verified** buyers/GCs/unawarded contracts.

Non-existent/changed project ID, contradicting address or non-HTTPS contact source cannot auto-join. Refusals are held; issued or revised work is labelled award-risk; source value placeholders are null; no buyer is auto-promoted. Unit tests in `tests/test_toronto_20_commercial_review.py` cover these gates.

**Before client delivery:** independently verify the company controlling each work package, public procurement/GC contact route, current tender or subcontractor availability and timeline, and reconcile any source stage changes. A City-issued permit or a named landlord does not establish sales readiness.

Attribution: Contains information licensed under the Open Government Licence – Toronto.
https://open.toronto.ca/open-data-licence/
