# GTA Radar — public notices expansion pilot (Milton, Pickering, ERO)

**Status: code and offline fixtures added. Live publisher response and source completeness NOT validated.** Manual preview only; no V8 edits, automatic tasks, paid AI or automated outreach.

## New research sources

1. **Milton development notices — official dated posts**
   - Listing: https://www.milton.ca/news/development-notices/
   - Read the *visible first listing page* and follow a bounded number of linked detailed posts.
   - Store official posting dates where printed by Milton, individual notice URL, site in post title, details on scope, and review classification. Do not infer first-seen from application number.
   - Limitation: news listing is paginated; this adapter only monitors the first visible page until a tested page traversal is available. Post details may be unstructured or residential. Not proof of new development on first run.
2. **Pickering active development proposals — official applicant, site and date posted**
   - Listing: https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/
   - Group each published table row by the linked official project page; capture municipality's exact *Date Posted*, published applicant, address, ward, and fetch up to twelve newest project proposals for scope identification.
   - Limitations: published page covers specific active Planning Act applications, not all site plans, minor variances, or pending building permits; an applicant is not a purchasing decision-maker.
3. **ERO proposal-stage industrial/environmental notices — separate free pilot review**
   - Search: https://ero.ontario.ca/search
   - Reuse the existing Radar \`radar._parse_ero_search_cards\` parser in **read-only** mode and filter explicit \`Notice stage = Proposal\`, with industrial/ECA/waste/sewage/air/water keywords.
   - Examine at most three recent public search pages by default. Proposal **posted** dates are retained when parsed, but city is \`ONTARIO_LOCATION_UNVERIFIED\` unless explicitly stated in source text.
   - Limitation: ERO notice search cards may omit location; eligible proposal projects require manual original-notice verification. This DOES NOT change or duplicate the V8 scheduler's ERO collector. We test the proposal-stage idea separately before deciding whether a lightweight V8 selector enhancement is justified.

## Files / execution (when back at PC; no need to do anything now)

From the latest **pilot branch folder**, double-click \`RUN_PUBLIC_NOTICES_PREVIEW.bat\` once. Or:

\`\`\`shell
python -m unittest tests.test_early_public_notices
python early_public_notices.py --data-dir data --output-dir GTA_RADAR_RESULTS
\`\`\`

Requires the existing Python dependencies \`requests\`, \`beautifulsoup4\` and \`pandas\` already declared in the repository \`requirements.txt\`.

Outputs:

- \`data/early_public_notices_review.sqlite\` — **separate from V8's \`radar.sqlite\`, existing \`early_signals_review.sqlite\`, and existing \`early_cues_review.sqlite\`**.
- \`GTA_RADAR_RESULTS/EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv\` — per-feed fetched, source posting date coverage, valid commercially relevant scope, request errors.
- \`GTA_RADAR_RESULTS/EARLY_PUBLIC_NOTICES_RESEARCH_QUEUE.csv\` — reviewed/possibly commercial current/historical public information, **NOT** qualified leads.
- \`GTA_RADAR_RESULTS/EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv\` — changes **only after a successful source baseline**.

The first snapshot of each source is intentionally treated as a baseline. A new project/notice **after** a successful baseline can produce a NEW event, and changed published facts can produce UPDATED. Publisher deletion from a partial listing is not interpreted as project cancellation. When a feed is inaccessible or malformed, return FAILED without replacing its historical snapshot. When none of the bounded ERO pages contain an eligible proposal, explicitly report \`NO_MATCHES_REVIEW\`, not a proved province-wide zero.

## Acceptance checklist before unattended monitoring

1. Confirm source list and detail page structures via live Windows run. If any collector FAILS, investigate before enabling.
2. Verify Milton first-page notices vs pagination; Pickering applicant/project links and proposal extraction; ERO exact Proposal-stage filter and location evidence.
3. Check publisher robots/terms and attribution for commercial-use collection; keep request volume respectful (default max 12 detail pages).
4. Link source events to existing seven GIS layers and later permits using published address/file number **without merging unrelated projects**.
5. Measure first PUBLIC posting date vs earliest GIS availability for the same project, not application receipt date alone. Record time gained.
6. Verify responsible operator/developer, work packages, lawful business contact route, and whether tenders/suppliers are still available. Unknown stays UNKNOWN.
7. Keep US$0.25/day DeepSeek cap, source pilot manual, and V8 unchanged. Sell 10 verified opportunities to two paying pilot customers before adding more broad feeds.

## Research backlog intentionally NOT forgotten

- Brampton Planning and Development eSCRIBE new-agenda discovery — municipal HTML currently 403 from some environments. Do not bypass restrictions. Official agenda publishing about two weeks before meeting can still matter; next test permitted access/reuse or official PDF distribution.
- Burlington *city-wide* new pre-application project discovery — current IESO/Burlington pilot watches only three verified pages.
- Toronto AIC daily alerts, AGCO licensing, utility intentions, land deals/commercial leasing, investment announcements, Ontario environmental assessments, Milton/Pickering further pages, Oakville/Markham/Vaughan/Richmond Hill/Hamilton and procurement bid/award signals.
- Master list: \`GTA_RADAR_RESEARCH_REGISTER.md\` on the repository default branch, with north star in \`GTA_RADAR_NORTH_STAR.md\`.

**No part of this code asserts that any applicant needs new suppliers or has an open contract.**
