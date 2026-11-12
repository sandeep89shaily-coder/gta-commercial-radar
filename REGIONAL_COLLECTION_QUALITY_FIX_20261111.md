# Regional source quality and commercially relevant investigation — November 11

## Measured problem in owner's November 11 archive

- The V6 daily event CSV had 148 new/changed source rows: 146 Toronto and 2 labelled "Peel" despite containing Brampton addresses.
- The separate 16-city application collection had 1,523 canonical application files from 14 municipalities and 71 new/changed commercial review candidates. The municipal publication dates were not independently verified.
- The private top ten was 8 Toronto / 2 Burlington, while the V6 qualified review queue already contained 37 Brampton, 11 Mississauga, 2 Peel-labelled Brampton and 2 Waterloo source records.
- Some City collectors failed, including Toronto AIC, Brampton OPA/ZBA and site-plan feeds, and restricted Vaughan/Kitchener GIS access. Retained records do not prove completeness.

## New source-backed investigation path

The existing gta_opportunity_lanes.py private review queue now incorporates original IDs, project scope, address and official stage from GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv. It never imports AI buyer identities, contact hints, sale-ready flags or unverified publisher dates. Region-only "Peel" source records are normalized from a known Brampton/Mississauga address, and postal-city address suffixes are reconciled when identifying a site.

The private top ten is selected from a minimum source-backed investigation score and distributed across credible regions; per-city and per-region caps relax only if few eligible independent projects remain. The full private evidence queue is preserved. All remain investigation candidates, NOT sale-ready contracts.

A new read-only gta_municipal_recovery_scorecard.py stage, AFTER same-run canonical source acceptance, joins the measured original sixteen-city source diagnostics and the experimental GGH/new-four stages without inflating coverage. Outputs:
- GTA_RADAR_MUNICIPAL_RECOVERY_SCORECARD.csv
- GTA_RADAR_MUNICIPAL_RECOVERY_STATUS.json

The stage does not run extra collectors, paid AI, send emails, schedule anything, modify the original database or bypass source policy.

## Acceptance still required

1. Cross-platform pytest CI must pass.
2. Run the owner Windows manual launcher on an updated clean install; existing November 11 archive predates this change.
3. Inspect full and top-ten private review queues against exact municipal source links and addresses, including corrected Peel vs Brampton and Toronto/non-Toronto mix.
4. Individually verify 20 original project records, their application/status ages, company roles, and whether any unawarded supplier package actually exists.
5. Await authorized Vaughan/Kitchener exports; other blocked sources require permission/alternate published exports, not bypasses.
6. Keep the $0.25/day shared DeepSeek budget, and prevent automated outreach.

A higher-quality geographic research queue does NOT mean a verified new project publication, an identified purchaser or a contract currently open for bidding.
