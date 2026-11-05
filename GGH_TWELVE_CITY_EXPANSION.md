# GTA Radar — GGH 12-municipality expansion

The existing GGH early-planning collector now has twelve configured municipal
source indexes. The original six remain unchanged:
Niagara Falls, County of Brant, Peterborough, Pickering, Orillia and Barrie.

New official planning sources:

| Municipality | Official source | Current extraction |
| --- | --- | --- |
| Richmond Hill | https://www.richmondhill.ca/en/learn-more/Planning-Development.aspx | Exact labelled file IDs, if present; GIS/map portal is otherwise index-only |
| Newmarket | https://www.newmarket.ca/business-development/development-planning/development-applications/current-applications | Exact labelled file IDs, if present; map and FTP links are not applications |
| Innisfil | https://www.innisfil.ca/building-development/planning-development/proposed-developments | Index only unless an explicit file number is published |
| New Tecumseth | https://www.newtecumseth.ca/build-here/development/proposed-developments/ | Up to 6 official planning notice detail pages, with explicitly labelled file IDs |
| Bradford West Gwillimbury | https://www.townofbwg.com/news/statutoryplanning-notices/ | Up to 6 official planning notice detail pages, with explicitly labelled file IDs |
| Thorold | https://www.thorold.ca/building-business-development/planning-and-development/development-applications/ | Application section with explicitly labelled City File No. |

The daily integrated stage is `ggh_early_planning_twelve_city_pilot`.
There is **no additional launcher** and **no extra database**.

## Output and control policy

- `GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv`: official-number candidate
  records for manual verification, including original notice URLs, extracted
  applicant names only where explicitly published, and original date basis.
- `GTA_RADAR_GGH_EXPANSION_NEW_OR_CHANGED.csv`: first observed after baseline
  or materially changed records. Initial ingestion is never a new lead.
- `GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json`: per-city source status,
  detail-page attempt counts and reasons for access/parse failures.
- `GTA_RADAR_GGH_EXPANSION_SEEN.json`: persistent first-seen ledger.

Public-facing application portals, JS-based maps and broad news indexes **do
not count as application-level coverage**. No application number is inferred
from a map feature ID, address, notice date, proposal title or arbitrary phone
number. A published meeting date is not proof of first municipal publication.
No restricted robots endpoints are bypassed.

## Validation

```powershell
python -m pytest -q tests/test_ggh_early_planning.py tests/test_ggh_six_city_expansion.py
```

Run the normal total-intelligence launcher after updating from `main`.
Review the per-city source-status JSON and candidate CSV; do not add the six
cities to the measured 16-city application success denominator. It remains
separate as a GGH expansion pilot until actual application-level collection,
coverage and source dates are verified.

In particular, a zero count for Richmond Hill, Newmarket or Innisfil means
**index connected / application source not yet recovered**, not successful
coverage. Tomorrow's first live collection must check this distinction.


## New Tecumseth notice PDFs and Thorold supporting-file labels

Live source acceptance showed that New Tecumseth's official HTML notice
summaries do not display file numbers; some contain a same-host link labeled
"view the full notice" which points to a PDF containing the municipal
`File No.`. The collector now follows at most six PDFs in total across the
bounded notices, subject to public DNS, robots permissions, HTTPS,
no-redirect validation, strict PDF signature, a 2 MB file limit and five
pages. Scanned PDFs report unavailable text; no OCR or bypass is attempted.

Thorold's official active-applications page occasionally publishes an exact
file number in the supporting-document link *label*, e.g.
`D14-09-2026 - Development Approvals Application`. That label can become a
review candidate tied to the official city index. Historic IDs mentioned
in unrelated background paragraphs do not qualify.

The live acceptance counts must be inspected again on the final commit;
no citywide completeness or verified commercial procurement is claimed.
