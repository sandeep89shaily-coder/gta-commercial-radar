GTA RADAR — EVENT INTELLIGENCE & SMART PRIORITY

RUN: Double-click START_RADAR.bat. Keep older installations unchanged.

CHANGED IN THIS RELEASE:
- Classifies inspection, development, permit, licensing, environmental and company events separately.
- An inspection is NOT automatically called a new business opening.
- Groups compatible same-location events, but avoids merging different named establishments at a shared site.
- Commercial/industrial descriptions rank above routine inspections and apparent residential activities.
- Does not discard source observations when opportunity priority is low.
- Keeps possible operator matches marked unverified.
- Writes research_priority_queue.csv, matured_opportunities_REVIEW_ONLY.csv and investigation_dashboard.html with event type and evidence URL field.
- Keeps DeepSeek safety limits from previous release; this change does NOT authorize new paid calls.

LIMITATIONS: Source export may omit application/permit IDs, and this release cannot recover IDs that were never exported. Address-derived matches are provisional. No autonomous identity verification or verified contacts are claimed. No user database was available for live 383-event validation. Original installations remain untouched.

VALIDATION: 117 local automated tests pass (including 5 additional regression tests).
