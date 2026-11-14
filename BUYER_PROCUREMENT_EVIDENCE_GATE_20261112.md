# Buyer and procurement evidence gate — November 12, 2026

## Why this exists
Fresh municipal events are not proof of a live procurement opportunity. A leasing representative, building owner in an old brochure, or municipal planning agent is not automatically the purchasing decision-maker. The daily shortlist must be a **research queue**, not a guaranteed sales list.

## Manual integrated output
The existing `gta_client_freshness.run(results)` also writes:
- `GTA_RADAR_BUYER_PROCUREMENT_REVIEW.csv`: one row per fresh, non-repeating client research candidate.
- `GTA_RADAR_BUYER_PROCUREMENT_STATUS.json`: counts and explicit HOLD reasons.

No independent verification, live original municipal source recheck or confirmation of an unawarded package occurs merely because a row appears.

## Optional analyst evidence
A researcher can place `GTA_RADAR_BUYER_EVIDENCE.csv` in the existing results folder. Header:

```csv
opportunity_id,city,address,buyer_organization,buyer_role,buyer_evidence_url,public_business_contact,contact_role,contact_evidence_url,procurement_stage,procurement_evidence_url
```

Matching requires **exact opportunity_id + city + address**; repeated IDs, missing or conflicting civic sites fail closed. Include one row per opportunity only. Use source URLs tied to a specific project or company, not AI guesses. Buyer role is one of OWNER, DEVELOPER, TENANT, OPERATOR, GENERAL_CONTRACTOR, PROCUREMENT_TEAM. Procurement stage is OPEN, AWARDED or UNKNOWN. An unsupported stage is UNKNOWN, not OPEN.

- `buyer_evidence_url` must publicly support the claimed organization *and its actual project role*.
- `contact_evidence_url` must show the business channel and why it is relevant to the stated role.
- `procurement_evidence_url` must show the actual dated procurement condition, not just an issued building permit.
- Published URLs are syntactically checked, **not network-verified**. A fully populated analyst row becomes `EVIDENCE_READY_FOR_INDEPENDENT_RECHECK`, never a completed sale-ready verification.

The separate output deliberately reports zero *independently verified* packages and zero *customer-ready* claims from this automated step. An independent analyst must inspect the source dates, organization authority, correct physical facility/unit, active package, vendor-selection stage and lawful contact channel before anything is offered to customers.

## Safety and operations
Existing raw source records, Radar database, reported-site ledger, regional private review, manual launcher, and US$0.25/day paid-AI ceiling remain unchanged. The evidence stage does not send emails, crawl sites or access protected municipal sources.

Run `python -m unittest discover -s tests -v` in the normal CI matrix. Follow with a fresh owner-side one-click Windows run to confirm the new output is packaged and review the first ten actual candidate cases. Do not call this a verified buyer database until the independent original-source checks are complete.
