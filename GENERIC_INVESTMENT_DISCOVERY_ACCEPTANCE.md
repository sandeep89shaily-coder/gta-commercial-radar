# Generic industrial-investment discovery: blind project acceptance

## Purpose

The existing exact-project investigator works only after Radar already knows
the project ID. This independent pilot discovers industrial investment
announcements with NO known company name, project name, street or municipal ID
in the search query, before trying to associate them with municipal records.

This is not an ACE-specific implementation: the code contains no brand, company
or road from the proposed benchmark. Offline tests use invented entities.

## Controlled pilot workflow

1. **Zero-cost preflight:** count existing city-level records and display two
   generic industry/city search queries. No Search/Fetch or model calls.
2. **Opt-in paid discovery:** two DeepSeek Search calls, up to five independent
   Fetch calls, and one structured DeepSeek analysis. Shared daily V5 and
   legacy spending limits apply.
3. **Original citations:** reject hallucinated project/company names and
   quotations absent from fetched source passages.
4. **Municipal identity:** compare the announcement street to existing
   municipal records (all recorded commercial research + current V8 pending,
   not just the current Top 10). Same-street applications are displayed as
   UNVERIFIED candidate matches, never merged automatically.
5. **Output:** GTA_RADAR_INVESTMENT_DISCOVERY/INVESTMENT_*.json, preserving
   all citations, search/fetch status, candidate links, unknown buyer and
   procurement state, and billed-request checkpoints. No automatic outreach.

### Windows commands

In the existing Radar installation:

    git pull --ff-only
    py -3 gta_investment_announcement_discovery.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --city Brampton

Above is zero cost. For exactly one fresh live discovery run, explicitly add
--paid (requires the user's existing local DeepSeek key). Do not delete
checkpoint/ledger files to get a different result.

### Acceptance gates

- Generic Brampton industrial queries do not include the candidate's name,
  developer, partner, or street address.
- Source-independent company announcement is recovered with verbatim quotes.
- A site plan merely on the same road is NEVER claimed to be the same project.
- A source's publication date is not the date Radar first observed it.
- A developer or capital partner does not constitute an open supplier package.
- No existing manual collector or main workflow is reset.
- A successful generic discovery is research progress, not evidence the
  opportunity is ready for paid customer outreach.

## Real-world external benchmark, outside the source-free CI fixture

The latest user-selected independent benchmark is an industrial condominium
investment announced in Brampton in 2026. **Its name, developer, partner and
street are deliberately not in the implementation or offline fixtures.**
After one local generic search, audit whether the model independently
found the announcement, documented its capital/developer relationships,
and correctly marked the plausible nearby municipal planning file as
UNVERIFIED until application/parcel evidence links them.

Passing CI does not establish that the provider's live ranked searches return
this real-world benchmark. Explicitly report success or failure from the
captured local JSON; never backfill a missed result manually and call it AI
discovery.
