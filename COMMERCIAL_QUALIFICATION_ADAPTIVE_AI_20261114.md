# Commercial qualification and adaptive AI priority — November 14, 2026

## The user problem addressed

Radar collected >1,500 municipal application files, integrated two newly completed DeepSeek reviews and linked one source-supported company role, but had zero independently verified purchasing authorities and zero open supplier packages. The next useful increment is to investigate **fresh, supplier-relevant projects**, rather than multiplying raw AI calls or implying companies are qualified leads.

## Changes in this increment

1. **Internal commercial research worklist:** `gta_commercial_qualification_review.py` composes three existing datasets: client freshness review, private development review, and V8 pending candidate queue. Reads the exact-ID AI company graph and AI lifecycle conflict report; no paid API calls or new collector. Output:
   - `GTA_RADAR_COMMERCIAL_QUALIFICATION_RESEARCH.csv` — research candidates with source provenance, sector, stage, company-role evidence and missing proof
   - `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` — internally prioritized ten records (or fewer), capped at four per municipality when candidates permit; **not client-ready verified leads**
   - `GTA_RADAR_COMMERCIAL_QUALIFICATION_STATUS.json` — source counts, freshness policy, missing buyer and procurement verification counts

2. **Exact project/role join:** A company is attached only when graph node project ID and municipality match exactly, never because of matching street address, applicant string or a municipality-wide role. All roles remain document-scoped, review-only and unverified for actual purchasing authority.

3. **Source-date and repeat controls:** Actual source-event and source-record dates are kept separate from the Radar first-seen timestamp. Client event dates are labelled **NOT PUBLICATION**; a first-seen date cannot make an old filing newly public. Previous IDs are penalized. Records are de-duplicated *only in the displayed worklist* when the city and unambiguous exact application ID match, or the specific source URL is identical. Their underlying source evidence and ledger are never modified.

4. **Freshness-first supplier relevance:** Industrial equipment, manufacturing, warehouse, data centre, cleanroom and expansion projects receive higher review priority, followed by commercial services. Pure residential proposals and post-approval/late-stage work are ranked lower. Project scale cannot outrank fresh industrial source evidence on its own. No undocumented buyer names, email addresses, active tenders or revenue estimates are fabricated.

5. **Adaptive source-backed AI invocation:** The existing `gta_execute_ai_project_research.select_projects` keeps candidate_scoring's exclusion/minimum eligibility gate, then prioritizes by `gta_freshness` **source-date category**, industrial/commercial scope and early lifecycle. The explicit full Windows manual workflow now permits up to **10** eligible projects instead of two. This is not an instruction to spend $1: every paid request still requires the existing source checks, per-request shared ledger reservation, recorded account key and **US$1/day** software ceiling. It stops when the guard refuses a call, a provider HTTP 402 is returned or no eligible sourced projects remain. Manual saved-data review stays free.

6. **Offline refresh integration:** `gta_ai_project_intelligence_refresh.py` updates the internal commercial analyst worklist as well as the project-company graph and supplier queues, with zero new DeepSeek requests. The normal full-run summary records worklist status while retaining the existing seven stages.

## Use today, without rerunning collectors or paid AI

    cd "C:\Users\sande\Desktop\GTA_RADAR_INSTALL\GTA_RADAR_MONDAY"
    git pull --ff-only
    py -3 .\gta_ai_project_intelligence_refresh.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"

Read `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` and `GTA_RADAR_COMMERCIAL_QUALIFICATION_STATUS.json` in the existing results folder.

## Grounded limitations

- The worklist uses existing stored review records only. It does not verify the official URLs again and does not establish that any supplier package is currently available.
- A first observed date is **not** a first publication date. Some project sources lack usable event dates and are explicitly labelled unknown, not filled by inference.
- A proposed planning project is not automatically a source for actual contractor awards, or a role for sourcing private numbers. Original buyer/GC/tender/award evidence must still be independently checked.
- Existing AI research runs only on sourced V8 candidate rows, not every private development project. The new triage worklist highlights private candidates for further human/connector work; a private-project DeepSeek adapter requires separate schema, source and price verification.
- No expansion of AI budget, no rerun of all collectors, no automatic emailing or verified-lead claim.
