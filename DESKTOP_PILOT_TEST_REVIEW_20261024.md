# GTA Radar — Desktop pilot test diagnosis (October 24, 2026)

Source: user ran the isolated manual Windows pilot and shared `GTA_RADAR_RESULTS.zip`. This is an actual desktop-run result, not an offline fixture or an imagined live test. No V8 production data/scheduler changes were made.

## Outcomes

| Source group | State | Verified scope / limitation |
|---|---|---|
| Seven original GIS collectors | All SUCCESS | 32,269 features across Brampton, Mississauga, Toronto, York; repeat scan produced zero NEW/UPDATED. |
| Hamilton | Two SUCCESS | 5,237 GIS features; 14 dated city planning notices on this Windows run (prior GitHub one-shot parsed five in a smaller 8-article sample). All first-run baseline. |
| Oakville | SUCCESS_INDEX_ONLY | Seven wards, 146 application links, 6 scoped project details complete. This is not a complete permit list or a real buying decision-maker list. |
| Markham | SUCCESS_REPORT_INDEX | 63 PDF report links, 14 with '2026' label; no individual application auto-extraction. |
| Pickering | SUCCESS | 27 proposed projects, six possibly commercial/mixed. |
| Milton | SUCCESS | Ten first-page notices, two possibly commercial/mixed. |
| ERO | SUCCESS | 20 recent proposals, seven commercial/industrial keyword matches; locations often unverified. |
| Burlington original 3 project seeds | SUCCESS | Only three known pages, NOT citywide coverage. |
| Burlington citywide ward discovery | FAILED | One official project detail page inaccessible: `better-life-living-4103-palladium-way.aspx`. Because the source fails closed, it did not commit a citywide baseline; source is not empty. |
| Brampton eSCRIBE planning committee | FAILED | Agenda HTML did not meet planning/agenda schema; requires publisher-specific HTML/access investigation before production. |
| IESO project connection table | FAILED | Expected project table absent in returned HTML, likely client-side JS/changed source; do not claim a completed IESO feed. |
| Ajax public application index | FAILED | Expected heading absent; likely changed/JS layout; do not claim 0 applications. |
| Ontario all-news government RSS | SUCCESS | Fifteen feed entries, not all relevant commercial. |
| CanadaBuys federal open tender CSV | SUCCESS | 891 open notices in snapshot, including 47 keyword matches but **none had a verified GTA delivery address in the filtered queue**; federal procurement should not crowd local private construction results. |
| Toronto AIC email import | NO_EMAIL_INPUT | Optional, expected without user's separately subscribed City update emails. |

## Critical problem discovered and fixed from real data

**Old top-50 research preview was wrong.** All 50 records were Brampton preconsultation. Some were 2019 applications. The original score gave no penalty to stale applications, so old highly specific warehouse descriptions overwhelmed recent notices.

The revised `early_pilot_summary.py` requires either an **original attributable public posted date in past 180 days** or a **recorded application RECEIPT date in past 180 days** (flagged `RECENT_APPLICATION_RECEIPT_NOT_PUBLICATION_DATE`). GIS collection first-seen is never conflated with published date. Undated old files are retained in historical database but excluded from 'current' top-50, as are unlocated Ontario-wide ERO or unlocalized federal tenders.

Applied to the desktop ZIP without network requests, the updated date-aware rules yield **179 freshness-eligible research records**, and a corrected top 50 with Brampton 18, Toronto 18, Hamilton 7, Mississauga 4, Milton 2, Pickering 1. **All remain NOT SALE READY** until buyer/work-package/vendor checks are documented. A truly earlier disclosure has not been measured.

The previous buyer worksheet held **9,428 unqualified records**, with no populated user annotations in reviewer/buyer/work-package/contact/evidence fields. Updated `early_buyer_evidence.py` uses the latest top-100 date-and-location-scored research cases for active manual investigations. Existing manually edited research is preserved even if it falls off the top 100. This avoids a 4.6-MB checklist that practically cannot be reviewed.

## Business proof remains missing

- 9,428 possible commercial/mixed or federal keyword-matched items in the broad audit are **not** individual verified business opportunities.
- 2,381 same-address comparisons are **not** evidence of the same project or lead-time advantage.
- Reviewer-attested comparable publication date pairs: **0**.
- Complete buyer evidence records: **0**.
- Verified open private supplier packages: **0**.
- Two paying pilot customers: **NOT MEASURED**.
- No customer outreach performed; no DeepSeek used.

## Next live fixes, ordered

1. Investigate the single blocked/unavailable Burlington project URL; leave citywide source FAILED until a meaningful accessible official record strategy exists.
2. Diagnose eSCRIBE Planning & Development agenda HTML/JS and source date separately, without bypassing headless restrictions.
3. Investigate exact IESO public connections data source (HTML JS table vs official downloadable publication) and Ajax official planning application's published endpoint, without inventing a URL.
4. For validated feeds, measure 2nd-run NEW events only after real publisher changes and prove buyer/unawarded status for 5–10 specific projects.
5. Quantify outstanding Brampton 1,542 undated site plans, York Region 319 undated GIS features without substituting observation date for source date.

**Automated tests:** the date-aware shortlist changes are covered by `tests/test_early_freshness_ranking.py` and buyer workbench fixtures; GitHub Actions run `40131733699` PASSED on both Windows and Linux after fixture corrections. Not merged to production.
