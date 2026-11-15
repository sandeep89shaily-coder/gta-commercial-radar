# Coordinated investigator — fixed commercial acceptance contract

## Objective

Given ONE exact Radar project ID, discover and investigate the project as a
whole. Produce source-backed company/site relationships, public corporate
contact leads where supported, current-stage caveats, candidate supplier
categories, procurement uncertainty and a concise decision to PURSUE, HOLD,
REJECT or investigate again. No invented buying authorities or open bids.

This is an integrated path, not ten isolated LLM passes. Existing municipal
collectors and the evidence graph remain the source of truth. The old
ten-capability path is retained for compatibility but not used here.

## How to run

Existing Windows installation:

    cd "C:\Users\sande\Desktop\GTA_RADAR_INSTALL\GTA_RADAR_MONDAY"
    git pull --ff-only
    .\RUN_GTA_RADAR_COORDINATED.bat "toronto_development_applications:25249692ESC21CD"

The above is a **zero-token preflight** using existing saved sources.

To explicitly authorize paid model research:

    .\RUN_GTA_RADAR_COORDINATED.bat "toronto_development_applications:25249692ESC21CD" PAID

The launch selects ONE exact current Top 10 record. It never substitutes a
different application sharing the same address. The local $/day account
ledger applies. Source Search/Fetch is bounded by at most FOUR research
stages (each stage at most one search and two fetch operations); the AI
planner and synthesis use at most TWO model requests. Failed/uncertain
paid calls are checkpointed and never retried automatically.

Results are under GTA_RADAR_COORDINATED_CASES as same-stem .json/.md and
joined to canonical commercial qualification via
GTA_RADAR_COORDINATED_PROJECT_OVERLAY.json, with exact record ID/city/
address/application ID/description verification.

## Five immutable regression cases (offline)

1. 1430 Birchmount, Toronto: official 2025 condo file; Business Point
   grounded site-level company discovery. The model may NOT call Business
   Point applicant on that exact city application without further evidence.
2. 611 Keele: distinguish a historical storage proposal from subsequent
   development, without automatically treating same-site proposals as
   legally superseding one another.
3. 75 Advance Blvd: 175 Advance Blvd must not be accepted as the same
   address, even in an old cached source.
4. 8380 Highway 50: one permit alone does not prove contractor, equipment,
   supplier package or buyer.
5. 238 Glidden Rd: industrial site context must not be promoted to an
   exact-permit purchasing authority without a source-backed role.

These tests use local documented snippets and simulated model/provider
responses. They are NOT five successful live sales dossiers.

## Pass/fail criteria

A project passes research completion only if its report identifies the exact
project, distinguishes same-site from exact-application roles, contains
source-quoted company/contact evidence where available, never invents
procurement, cites accepted facts, and clearly distinguishes UNKNOWN from
confirmed facts. Model response completion alone is not acceptance.

For commercial readiness require 10 independently audited current
opportunities and actual feedback, followed by two paid pilot customers.
Do NOT claim the milestone has been reached from passing CI. If research
cannot produce contact or commercial relevance, the correct output is HOLD
or REJECT, not a false sale-ready lead.

## Evidence and compliance

No source-backed site company is automatically a verified applicant, owner,
purchasing authority or open subcontract. No automatic outreach. The LLM
can recommend research directions, but only independently fetched pages
can ground claims. An absence of public tenders does NOT prove a contract
is unawarded. The application filing date is not the public announcement
date; a recent condominium filing may follow a groundbreaking.

A crash after an API request may leave a durable STARTED checkpoint. This
is retained (safe, no automatic repeat); it requires deliberate diagnosis,
not deletion/reset of the daily billing ledger. Contact details from public
sites are research leads and must be checked for lawful outreach use.
