# Brampton PDC Featured Applications — Source collector acceptance (November 13, 2026)

## Why this matters

The owner's November 13 ZIP showed the public Brampton council index counting a complaint-protocol URL and an at-a-glance annual calendar as agenda documents, instead of retrieving actual PDC agenda applications. PR #191 corrected those false positives and now flags source gaps.

A separate publicly accessible, City-linked resource exists: [Your City Plans — Planning and Development Committee](https://letsconnect.brampton.ca/yourcityplans). It contains **selected featured application** details, including City application IDs, named applicants/agents, ward, location and proposal purpose. The City links from its official PDC/council participation pages. It is **not** the complete OPA/ZBA or site-plan application inventory.

A public sample visible on November 13 lists:
- City file `OZS-2025-0038`, Humberwest Parkway RDP 1724 Inc. / Weston Consulting, June 8, 2026 meeting, west of Humberwest Parkway, residential townhouses
- City file `OZS-2025-0048`, Upper Mayfield Estates / Caliber Homes, June 15, 2026 meeting, 5875 Mayfield Road, residential and mixed-use including ground-floor office space

These are historical source cases, **not new November projects**, not supplier contracts or verified buyers. City meeting dates must never be presented as publisher first-posting dates. Evidence source: https://letsconnect.brampton.ca/yourcityplans

## Actual implementation

`gta_brampton_featured_pdc.py` has a bounded, policy-checked source fetch and deterministic card parser. The new source adapter runs inside **the existing manual seven-stage full daily run** via `gta_council_integrated_manual.py --fetch-brampton-featured`, only during fresh collection (not `--skip-collection`). It does not depend on the optional locally registered agenda PDFs. No paid DeepSeek calls are added and the existing US$1 integrated AI cap is unchanged.

Each run:
1. Validates public DNS and checks the site robots.txt before attempting one exact `https://letsconnect.brampton.ca/yourcityplans` HTML document; refuses redirects, errors, oversized responses or a changed MIME type
2. Extracts **only** complete featured application cards with official application file IDs, location and purpose; missing or conflicting fields are held
3. Maintains `BRAMPTON_PDC_FEATURED_APPLICATION_LEDGER.json` keyed by exact City application ID and card-content hash
4. Marks newly *observed* or changed source cards as **review only**, not new municipal publications/projects, and retains history if the publisher blocks the request
5. Produces `BRAMPTON_PDC_FEATURED_APPLICATIONS_REVIEW.csv` and `BRAMPTON_PDC_FEATURED_APPLICATION_STATUS.json` under `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_FEATURED_PDC`; archive policy includes the reports but excludes SQLite and credentials.

## Limits

- The public portal may prohibit automated collection through robots.txt or otherwise refuse the request. On that condition the collector reports a blocked/held source; it **does not bypass access controls or claim zero applications**.
- The webpage's HTML can change, and a no-cards parse is explicitly reported as a parser/source-structure failure without deleting the prior ledger.
- Keyword matches do not establish commercial use, contracts, actual construction, active project status or business contacts.
- This deliberately does not auto-enroll cards as buyers, verified leads, or real first-publication events in the primary radar database.
- The test suite uses synthetic HTML shaped like the source, not a claim of successful live access on the owner's Windows installation.

## Acceptance before broader promotion

Inspect the next owner-side dated ZIP for the Brampton featured source status, card hashes, exact application IDs, the source server response result and all blocked states. Independently compare extracted City file numbers and proposal locations against official planning applications. Only then consider adding verified source-backed planning application records to the investigation queue.

The remaining top collectors to repair: Brampton OPA/ZBA/site-plan feed completeness, the City eSCRIBE meeting-document discovery path, Toronto TMMIS agenda links, Mississauga eSCRIBE agenda capture and official permit joins; each requires permitted original-source evidence.
