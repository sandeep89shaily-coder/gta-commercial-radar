# Real-world municipal document validation — 2026-10-27

Case: Toronto City Council supplementary decision report on Ookwemin Minising.

Official PDF: https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf

## Actually observed
- Public web reader successfully retrieved a **5-page real municipal PDF** and extracted page-labelled text.
- Its page 1 was visually inspected. Actual report date: **May 19, 2026**; Toronto planning application: **26 132130 STE 14 OZ**; Ward **14 — Toronto–Danforth**.
- This is a **city-initiated planning and zoning amendment supplementary report**, not evidence of an open HVAC/security/insurance contract. Related Planning and Housing Committee discussion happened **May 7, 2026**.
- Page 2 mentions owner discussions concerning **65 Ookwemin Street**, but DOES NOT provide a verified purchasing decision-maker.
- Source-linked ground facts in `validation/real_toronto_report_20261027.json`.

## What failed / is NOT evidenced
- Attempt to retrieve the same PDF using a separate direct-file download tool failed. Do not infer the production Python downloader will work.
- The municipal document adapter was not run end-to-end on locally acquired PDF bytes.
- **No live DeepSeek model request was executed**: this environment has no validated access to the user's Windows DPAPI-stored DeepSeek API key / shared budget ledger.
- There is no empirical AI precision/recall result on this document.
- No link to existing V8 candidate was established; no lead generated.
- No website publication timestamp or commercial reuse approval was verified.

## Go/no-go conclusion
**PARTIAL PASS: live source and human-inspected claim grounding.**
**BLOCKED: direct retrieval, live paid model invocation, independent model-output comparison, V8 project merge, commercial validation.**

Do NOT classify this as completed live AI validation, or merge the AI adapter into V8 production. Only proceed to a budgeted pilot with the user's Windows environment or a connector providing an authorized key and data access; no secrets should be copied into GitHub.
