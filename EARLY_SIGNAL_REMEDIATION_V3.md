# GTA Radar Early Signals: measured remediation (v3)

This change stays in the **isolated early-signals pilot**; the V8 daily pipeline,
DeepSeek budget, original main database and Windows scheduled task are untouched.

## Deficiencies corrected in code

1. **Brampton dates:** ArcGIS epoch milliseconds are now parsed correctly.
   Site-plan rows with absent/invalid official DATE_RECEIVED remain undated.
   \`EARLY_SIGNALS_MISSING_DATES_REVIEW.csv\` explicitly preserves these
   records; no application-number year is fabricated as a submission date.
   \`EARLY_SIGNALS_QUALITY_AUDIT.csv\` separates valid dates and missing
   source dates. Earlier 1,542 missing site-plan dates were *observed* from the
   preceding live run; current counts must come from a new live refresh.

2. **York identities:** \`APPL_GISID\` remains a GIS identity. The new collector
   preserves municipality \`MUN_NAME\`, the first usable \`REG_FILE_NUM\` or
   \`EXT_REF_NUM\`, and original field provenance. \`app_key()\` groups records
   only when a specific alphanumeric published reference and known municipality
   are present; otherwise each feature remains an explicitly unverified
   feature group. A published shared reference is **not proof that several
   features are the same procuring project**.

3. **Toronto duplicates:** the existing application-number grouping and
   multi-feature uncertainty flags are preserved. One planning application
   can involve multiple sites or components; a grouped application is **not
   necessarily one unique construction project**.

4. **Commercial review ranking:** a free, deterministic
   \`EARLY_SIGNALS_BUYER_RESEARCH_QUEUE.csv\` scores research priority by source
   application recency, early stage, concrete industrial scope, and published
   organizational information. It excludes inactive and clearly residential
   records and never labels anything sale-ready.

5. **Buyer and vendor status:** the queue has explicit fields for
   \`purchasing_decision_maker\`, \`vendor_selection_status\`,
   \`procurement_status\`, \`verified_business_contact\`, source evidence,
   and specific next verification actions. All unverified values remain
   \`UNKNOWN\` or \`NOT_FOUND\`. Buyer contacts and open procurement
   **cannot be recovered from planning data alone**. A contact/contract becomes
   verified only after exact, independently attributable business or
   procurement evidence is found. No public-contact enrichment is falsely
   treated as proof of purchasing authority.

## Preservation and safety

- Initial baselines never generate "NEW" sales signals.
- Parser v3 upgrades preserve the original observation first-seen dates and
  suppress interpretation-only fake "UPDATED" source events.
- False updates are suppressed during the first v3 conversion. Real municipal
  changes coinciding with that conversion require separate source-history
  review; never claim they were detected as live NEW events.
- Failed source fetches do not write incomplete snapshots or clear history.
- No AI calls, no unsolicited outreach, no user data is sold or copied.
- The source-date is an application/receipt date, **not** a verified date of
  public posting; both differ from the Radar first-seen timestamp.

## New files emitted on refresh

- \`EARLY_SIGNALS_SOURCES_STATUS.csv\`
- \`EARLY_SIGNALS_QUALITY_AUDIT.csv\`
- \`EARLY_SIGNALS_MISSING_DATES_REVIEW.csv\`
- \`EARLY_SIGNALS_PROJECTS_REVIEW_ONLY.csv\`
- \`EARLY_SIGNALS_POSSIBLE_STAGE_LINKS_REVIEW.csv\`
- \`EARLY_SIGNALS_BUYER_RESEARCH_QUEUE.csv\`

## Remaining evidence gates before production

- Validate that all 7 live GIS sources still respond after refresh.
- Review whether official Brampton site-plan records genuinely have no
  \`DATE_RECEIVED\` or an alternate explicitly equivalent date field.
- Quantify York published reference coverage and suspicious duplicates
  using the new quality report; do not force unrelated features to merge.
- Check 10–15 high-priority early-stage projects against exact official
  applications, actual project companies and independently sourced public
  business/procurement channels.
- Obtain two paying pilot customers before expanding scope.
- Do not merge into V8 or enable unattended schedules merely because tests pass.
