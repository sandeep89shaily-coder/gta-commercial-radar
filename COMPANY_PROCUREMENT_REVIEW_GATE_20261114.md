# Company Role and Procurement Review Gate — November 14, 2026

The new `gta_supplier_verification_gate.py` builds **an actionable analyst worklist**, not merely another count of application files. It attaches existing PR #209 company-role mentions to a bounded review process, requiring evidence for each project-specific company role and open public supplier package.

## What today's one-click Radar run produces

Inside `GTA_RADAR_RESULTS`:

- `GTA_RADAR_COMPANY_ROLE_REVIEW_QUEUE.csv`: project, city, named organization, role claimed, source URL, stable graph edge ID and what to verify.
- `GTA_RADAR_SUPPLIER_PACKAGE_REVIEW.csv`: rank-ready procurement research tasks for each existing project with an explicit UNKNOWN supplier sector and no invented tender, followed by reviewed package observations (where supplied). No row is an automatically verified contract.
- `GTA_RADAR_COMPANY_PROCUREMENT_REVIEW_STATUS.json`: audit summary, review holds, reviewer-attested roles, deadlines and clearly labelled unverified claims.

These are included in the normal dated ZIP because they are root `GTA_RADAR_*.csv/json` reports. The original collector SQLite, first-observed ledger, source files, current DeepSeek budget and seven-stage launcher are untouched.

## How reviewers add project-specific proof

An *optional* file lives at the existing workspace root, **not** inside the export directory:

`GTA_RADAR_REVIEW_DECISIONS_V1.json`

It must be a JSON object with `version: 1`, and lists `role_reviews` and `procurement_reviews`. If absent, Radar simply emits the queue with **zero accepted reviews**. Example starting file:

```json
{
  "version": 1,
  "role_reviews": [],
  "procurement_reviews": []
}
```

For each `role_reviews` entry the reviewer must supply:
- `edge_id`, `project_node_id`, `role` and `organization_name` **exactly matching the current graph**;
- `decision`: `CONFIRM_ROLE` or `REJECT_ROLE`;
- `reviewer_id` and offset-aware `reviewed_at_utc` (within 30 days, not in the future);
- `evidence_url` (exact public HTTPS original), a project-specific `evidence_quote` naming the organization, `evidence_locator` (PDF page or official record ID), and the 64-character `source_document_sha256`.

A matching company name or address alone is **not evidence of ownership, procurement or purchasing authority**.

Each `procurement_reviews` entry additionally supplies:
- `project_node_id`, exact `tender_id`, `decision` (`OPEN_PUBLIC_TENDER`, `AWARDED`, or `CLOSED`), `sector`, `work_scope`, `reviewer_id`, `reviewed_at_utc`, `tender_url`, `evidence_quote`, and `source_document_sha256`.
- Supported sector codes: `HVAC`, `INDUSTRIAL_EQUIPMENT`, `ELECTRICAL`, `SECURITY`, `INSURANCE`, `FACILITY_SERVICES`, `OTHER`.
- For `OPEN_PUBLIC_TENDER`: `closing_date` (`YYYY-MM-DD`), `buyer_role_edge_id` referencing a previously reviewed, project-specific role, `authority_evidence_url` and `authority_evidence_quote`.
- Expired deadlines, missing buyer-role review, missing authority evidence, conflicting/duplicate tender decisions and unknown project IDs are explicitly held. Awarded/closed packages cannot be classified as open.

**Crucial limitation:** A reviewer-supplied source URL, quote and document hash are **attestations, not independent live source verification by Radar**. Even a well-formed `OPEN_PUBLIC_TENDER` is labelled `REVIEWER_ATTESTED_OPEN_TENDER_LIVE_RECHECK_REQUIRED`. The system currently reports **0 independently verified buyers and 0 independently verified open packages**. It does not authorize sales outreach. This is the necessary auditable handoff toward real original-source checking, not commercial launch acceptance.

## Architecture and integration

This code consumes the role graph's exact project/edge identifiers only. It does not auto-merge organization names or treat an applicant, planning reviewer, owner or regulatory proponent as the purchaser. Optional reviewed evidence cannot mutate the existing source records or fabricate first publication timestamps.

CLI for direct offline review, without a fresh collection:

```powershell
python gta_supplier_verification_gate.py --results "C:\path\to\new data\GTA_RADAR_RESULTS" --workspace "C:\path\to\new data"
```

Normal one-click run uses the same gate as post-run analysis (not an eighth stage). Existing fail-closed source, export and AI controls remain in place.

## Real-world acceptance criteria

1. Run the existing Windows launcher and inspect at least 20 original project sources.
2. Check named organizations against the exact original source quotation or PDF page/record ID; preserve the source hash, project role and review timestamp.
3. Independently confirm buyer identity, sourcing authority, current tender status and closing deadline before treating a public opportunity as actionable.
4. Identify at least 10 project-specific, dated and sector-relevant dossiers and test them with prospective customers; do not count reviewer entries as proof of commercial readiness.

This work is additive to the North American architectural tracks; live municipal retrieval and client conversion still require separate independent evidence.
