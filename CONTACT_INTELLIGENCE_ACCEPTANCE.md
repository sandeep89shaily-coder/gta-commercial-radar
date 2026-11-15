# Priority B2B contact intelligence — commercial acceptance

## Goal and differentiation

Radar must find legitimate business contact paths as well as identifying
projects. This implementation takes any independently discovered, source-backed
project (ACE Brampton is an example), investigates each documented company
across different public-source strategies and preserves named people, exact
roles, publicly displayed business emails and office telephones with their
original source quotes. The source-backed company inventory comes from the
already-paid generic investment discovery, not hardcoded to ACE.

## Research workflow

1. Require exact named project in the existing original discovery file. The
   original fetched announcement must support the name and companies.
2. Four targeted queries PER documented company (up to 3): office contact,
   business telephone/email, publicly listed leadership, project management/
   procurement, and company-plus-project involvement. Up to 12 Search calls.
3. Rank only business/company/project-relevant results and independently
   fetch up to 20 public webpages. HTTP 403 or unavailable pages are recorded;
   continue with other pages without retrying the failed request.
4. Extract published business emails and business telephone numbers
   deterministically from independently fetched pages identifying ONE company.
   A company's official general inbox is NOT a project buyer.
5. One structured AI extraction of named staff/roles/contact data. Each named
   person and title must be supported by a contiguous verbatim source quote.
   A person's direct email or telephone is included only if it is explicitly
   present in the same quote. Inferred formats are not generated.
6. Rank by source-backed purchasing/development/project-management relevance,
   named staff availability and published contact channels, without
   inventing project procurement authority.
7. Save JSON and readable Markdown in GTA_RADAR_CONTACT_INTELLIGENCE.
   Update existing GTA_RADAR_EARLY_INVESTMENT_LEADS.csv with contact fields
   for the exact project/city. Other rows and their data are preserved;
   buyer_verified, open_contract and outreach_authorized remain FALSE.

## Local Windows commands

Pull the latest repository once.

Free, zero-cost preflight:

    .\RUN_GTA_RADAR_CONTACTS_ACE.bat

One authorized paid investigation:

    .\RUN_GTA_RADAR_CONTACTS_ACE.bat PAID

For another SOURCE-BACKED discovered project:

    py -3 gta_contact_intelligence.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --project-name "EXACT DISCOVERED NAME" --city Brampton --paid

The shared DeepSeek V5/legacy ledger is authoritative. Search and Fetch
cost reservations preserve unknown/failed charges. Completed and uncertain
investigations use a durable checkpoint and do not automatically reissue
requests. Do not delete checkpoints to force an expensive repetition.

## Fixed commercial quality gates

- Company sourced from announcement: required.
- Named individual and title: require published verbatim original quote.
- Published corporate email/phone: require fetched page source quote, no
  guessed formats, no personal account/private phone harvesting.
- A general corporate inbox is a useful business route, but not a verified
  construction procurement contact.
- Search failures and source HTTP errors do not silently become "no company".
- All names, addresses and numbers remain unverified for live outreach
  until checked for current accuracy and lawful business solicitation.
- No public listing alone proves an unawarded supplier contract.
- Vendor-specific suitability and direct procurement authority remain
  UNKNOWN unless separately verified.
- The outcome is measured by actual verified public contact paths and
  sourced people, not by number of successful AI calls.

## Limits

The offline fixtures use synthetic business names, contacts and simulated
DeepSeek responses. CI cannot establish that live third-party search tools
will return accessible pages, true staff listings or procurement personnel.
No paid API call is made by this GitHub change. The user must authorize
the live run from the local installation that holds DeepSeek credentials.
