# City Clerk TMMIS-derived meeting schedule source audit — 13 November 2026

## Source checked

Official City dataset: https://open.toronto.ca/dataset/3bfab808-105b-45ab-8d92-cf1916594653/

The City explicitly says this dataset is **meeting schedule data extracted from TMMIS**, with dates/times and committee names. It is not a list of published agendas, agenda URLs, commercial construction applications or permissions to bid. The 2022–2026 resource has columns `Term`, `Committee`, `MTG #`, `Date`, `Start Time`, `End Time` and `Location`. Its public data resource ID is `08c8aedb-afba-41f5-830e-bbfb305ebbc7` (2022–2026, CSV). The open data catalogue page lists its refresh as September 17, 2026; resource portals may report more recent updates. Therefore **source freshness requires rechecking the official resource**.

## Implementation and constraints

`gta_toronto_official_schedule.py` resolves one official CSV resource through exact CKAN resource metadata and checks the exact resource ID, declared CSV format, allowed official publisher domain, public DNS, robots policy and redirect denial. It reads at most one CSV (2 MB and 5,000 rows), validates the original source columns, and writes near-term meeting-date/committee inventory to `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/TORONTO_OFFICIAL_MEETING_SCHEDULE`. The source manifest and output preserve original ID and content SHA256.

The existing `RUN_GTA_RADAR_TODAY.bat` triggers this additional check as part of its established manual fresh-run council review stage. It is **not** scheduled or invoked during historical `--skip-collection` review. If the publisher blocks or changes the API, the collector reports `OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD`, retaining the last valid saved review CSV. No retry, endpoint probing or access-control bypass.

The output explicitly reports zero agenda URLs and zero verified projects, buyers and publication dates. It can guide which actual committee meetings need original agenda URL discovery; that next phase still needs original TMMIS meeting links, which are not in this CSV.

This change does **not** modify original Radar project DB, automatic outreach, private source data, or any paid DeepSeek budget.

## Next source gate

A permitted TMMIS schedule/profile adapter must retrieve **exact** original meeting agenda links before a meeting schedule can become agenda item extraction. Source rows alone cannot justify constructing/guessing meeting URLs from `Committee` and `MTG #` fields. The Toronto exact-URL agenda parser remains available when such links are known.
