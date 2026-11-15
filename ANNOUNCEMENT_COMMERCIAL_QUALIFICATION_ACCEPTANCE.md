# Independent industrial-investment qualification — commercial acceptance

## What this does

Convert a project previously found in the **generic city investment discovery**
into one research dossier for commercial suppliers. No new municipality/collector
is required and there is no invented municipal application ID.

**Input:** original source-linked, fully extracted, independent discovery JSON
under GTA_RADAR_INVESTMENT_DISCOVERY. The original source text and saved paid
model response are revalidated; manually adding a project name cannot force
qualification.

**Research:** four independently executed DeepSeek Search queries for a
developer's public business contact route, current design/construction stage,
procurement status, and possible municipal/parcel/applicant identity. At most
eight Fetch requests, plus ONE coherent model analysis of original source
passages, using the existing shared V5 and legacy daily spending ledger.

**Output:** standalone
GTA_RADAR_ANNOUNCEMENT_QUALIFICATION/<hash>.json/.md
and GTA_RADAR_EARLY_INVESTMENT_LEADS.csv. This is an early-investment
research worklist and does NOT masquerade as a verified municipality-backed
Top 10 project.

No source means no verified claim. A company contact (even on a public website)
is not a verified buyer. An inferred HVAC/electrical/security need is not a
documented unawarded package. The model's procurement opinion is forced to
UNKNOWN in published structured results unless an independent subsequent
verification process establishes contracting evidence. No automatic outreach.

## Existing Windows installation

From the repository folder:

    git pull --ff-only
    .\RUN_GTA_RADAR_QUALIFY_ACE.bat

That checks recovered ACE Brampton primary evidence and makes **no** provider
calls. For a single paid source-based qualification:

    .\RUN_GTA_RADAR_QUALIFY_ACE.bat PAID

This explicitly authorizes bounded searches/fetch and one synthesis. A
durable checkpoint prevents repeat API calls for the same project/date/profile
after any interrupted/uncertain request. Do not delete checkpoint or ledger
to repeat a charged call.

For another independently discovered project name, use:

    py -3 gta_announcement_commercial_qualification.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --project-name "EXACT DISCOVERED NAME" --city Brampton

Add --paid only when authorizing investigation.

## ACE Brampton customer-readiness acceptance

- Original company announcement preserved and named parties sourced:
  Storytime Developments and Fiera Real Estate.
- Public business contact route either sourced and labeled as such, or
  reported MISSING (not fabricated).
- Construction start Q3 2027 and completion Q3 2028 are reported targets,
  not verified actual construction start/completion.
- Supplier needs are hypotheses unless source specifies equipment/scope.
- No open procurement or purchasing authority is claimed without direct
  original evidence.
- Potential municipal application IDs have source quotes and remain
  UNVERIFIED until city/parcel/applicant matching is independently established.
- Research status is distinct from commercial outreach readiness.
- The next step after collecting evidence is manual commercial acceptance and
  a real pilot customer—not new municipalities or more disconnected AI stages.

## Important limitations

This implementation and its CI acceptance fixtures are NOT a live
DeepSeek/municipal application result. The user's saved production discovery is
on their local Windows system with their API key. The AI and Fetch requests
cannot be invoked from the GitHub CI environment.

For the first live report, review the JSON/Markdown and require a meaningful
developer contact and verified current procurement stage **or a clear HOLD**.
A model's decision alone is not a sale-ready lead.
