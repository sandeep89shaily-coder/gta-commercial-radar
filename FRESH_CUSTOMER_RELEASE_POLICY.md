# GTA Radar — genuinely fresh opportunity release policy (November 16, 2026)

The internal source-event-ranked file \`GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv\`
is an **investigation queue, not a customer-ready list**. A November permit
status update, file retrieval, AI research run, first Radar observation or
same-address company record is **not** proof of a newly announced project.

The one-click Monday pipeline now runs \`gta_fresh_customer_release_gate.py\`
and produces independent outputs, **without adding any paid calls**:

- \`GTA_RADAR_FRESH_EVIDENCE_WORKLIST.csv\`: permit/application research
  shortlist plus independently discovered industrial investment projects.
  Contains stable \`record_id\` and \`candidate_fingerprint\`.
- \`GTA_RADAR_FRESH_RELEASE_DECISIONS.csv\`: every case either reviewed
  or held with named reasons.
- \`GTA_RADAR_REVIEWED_FRESH_EARLY_WARNINGS.csv\`: **only** cases with
  recent original publisher evidence, material scope, project team, public
  business contact and documented procurement status, signed off by a reviewer.
  An \`UNKNOWN_CHECKED\` procurement state stays explicitly **unknown**.
- \`GTA_RADAR_REVIEWED_OPEN_PACKAGES.csv\`: additionally requires a
  current, explicitly dated tender listing with package ID, purchaser
  and a future closing date. These are still **reviewed listings needing
  an independent live recheck**, not verified unawarded contracts.
- \`GTA_RADAR_FRESH_RELEASE_STATUS.json\`: counts, blocked reasons and warnings.

**Do not advertise any of these as independently authenticated, current, unawarded
contracts without a live official-source confirmation.** Matching user-provided
source text and SHA-256 does not prove that its origin or timestamp is genuine.

## Operator review inputs — persistent outside the daily ZIP

Place \`GTA_RADAR_FRESH_RELEASE_REVIEWS.json\` in the established
\`--workspace\` directory. Put each captured public source snapshot under the
same workspace's \`GTA_RADAR_FRESH_SOURCE_SNAPSHOTS/\` folder. The pipeline
reads these evidence inputs but **never invents or overwrites them**. A corrupt
manifest blocks customer release, and missing evidence produces **zero**
reviewed early-warning rows; there is no forced quota of ten.

Use the worklist's *exact* \`record_id\`, \`candidate_fingerprint\`, city
and address. Source snapshots are UTF-8 JSON files of this form:

\`\`\`json
{
  "url": "https://publisher.example/project-specific-announcement",
  "retrieved_on": "2026-11-16",
  "text": "Full independently captured publisher excerpt including original date, named site, scope and team.",
  "sha256": "<SHA-256 of the exact UTF-8 text value>"
}
\`\`\`

The publisher/date quote must literally appear in the snapshot and show a
publisher-posted original date **within seven days**, not a permit's
\`DATE_RECEIVED\`, page fetch time or Radar first-seen timestamp. The
publisher's document must also identify the exact project/address (or, for
independent investment discoveries, both project name and city). Every
review includes an evidence citation for the work scope, project organization,
public contact channel and procurement status.

One case in the review manifest has these keys:

\`\`\`json
{
  "cases": [{
    "record_id": "<from worklist>",
    "city": "<from worklist>",
    "address": "<from worklist>",
    "candidate_fingerprint": "<from worklist>",
    "reviewer": "<real reviewer>",
    "reviewed_on": "2026-11-16",
    "decision": "APPROVE_FOR_EARLY_WARNING",
    "publication": {
      "snapshot": "original_post.json",
      "url": "https://publisher.example/project-specific-announcement",
      "quote": "November 16, 2026 ... original published project",
      "published_on": "2026-11-16",
      "date_basis": "PUBLISHER_DATED_PROJECT_ANNOUNCEMENT"
    },
    "scope_kind": "NEW_PROJECT",
    "scope": {
      "snapshot": "original_post.json",
      "url": "https://publisher.example/project-specific-announcement",
      "quote": "new industrial building and planned mechanical package"
    },
    "historical_review": {
      "reviewed_by": "<real reviewer>",
      "reviewed_on": "2026-11-16",
      "note": "Explain which earlier project versions, completion records and prior announcements were compared and what was established."
    },
    "organization": {
      "name": "<publicly named organization>",
      "role": "DEVELOPER",
      "snapshot": "original_post.json",
      "url": "https://publisher.example/project-specific-announcement",
      "quote": "Source quote naming the organization and role"
    },
    "contact": {
      "channel": "<published corporate email or business phone>",
      "role": "<publicly stated role; do not invent purchasing authority>",
      "snapshot": "project_contact.json",
      "url": "https://publisher.example/project-contact",
      "quote": "Published source text with the same contact channel"
    },
    "procurement": {
      "status": "UNKNOWN_CHECKED",
      "checked_on": "2026-11-16",
      "snapshot": "project_update.json",
      "url": "https://publisher.example/project-update",
      "quote": "Current status passage from official project update"
    }
  }]
}
\`\`\`

All example values above are schematic, **not real project evidence**.
Publication basis may also be \`OFFICIAL_POSTING_DATE_ON_ORIGINAL_NOTICE\`.
Project scope type may be \`MATERIAL_NEW_SCOPE\`, but then the case additionally
requires \`historical_review.prior_scope_evidence\` with a captured original
older-source quote and a substantive \`distinguishing_change\` explanation.

A project is **not** released merely because the review file exists: stale
snapshots (>2 days), invalid hashes, mismatched exact source URLs, unrelated
projects, unquoted dates, missing contact proof, closed projects, or absent
reviewer sign-off are all rejected. If an opportunity has already been
reported to customers, preserve the separate persistent client report-history
ledger; do not reset it to manufacture fresh opportunities.

## Commands

Normal daily launch (unchanged): \`RUN_GTA_RADAR_TODAY.bat\` or the established
\`gta_monday_full_run.py\` manual invocation.

Review just a saved archive and owner-supplied evidence without any paid or
network calls:

\`\`\`bash
python gta_fresh_customer_release_gate.py --results "GTA_RADAR_RESULTS" --workspace "<your Radar workspace>"
\`\`\`

**Acceptance target:** 10 independently date-verified recent project or
material-scope announcements with project identity, role, public business
contact, procurement status and original citations; at least two separately
confirmed real purchasers and current supplier opportunities before sales.
The pipeline must display **fewer than ten** when there are fewer than ten.
An empty customer-ready output is a legitimate, safer result.
