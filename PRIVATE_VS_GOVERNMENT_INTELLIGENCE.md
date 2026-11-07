# GTA Radar — Separate private-development and government-procurement intelligence

The November 6, 2026 review showed that a single top-ten list became heavily
dominated by public works, hiding source-backed private industrial, commercial,
hotel and mixed-use developments. The existing collector data is sufficient
to build separate evidence-aware rankings; no additional scraping or paid model
calls are required.

## What runs

After the regular municipal/region collection and the canonical collection
quality gate, `gta_opportunity_lanes.py` reads the existing official
application, permit and regional review CSVs.

It writes:

| File | Meaning |
| --- | --- |
| `GTA_RADAR_PRIVATE_TOP_10.csv` | 10 best private-development candidates **if at least 10 qualify** |
| `GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv` | Full private-development candidate queue |
| `GTA_RADAR_PRIVATE_CHANGES_TO_VERIFY.csv` | Changed/first-seen private candidates without independently verified original publication dates |
| `GTA_RADAR_PRIVATE_VERIFIED_FRESH.csv` | Only source-publication-dated projects from the last 7 days; may legitimately be empty |
| `GTA_RADAR_PRIVATE_EXCLUDED.csv` | Excluded closed projects that had reached candidate classification |
| `GTA_RADAR_GOVERNMENT_TOP_10.csv` | Separate government capital/procurement review (not confirmed open tenders) |
| `GTA_RADAR_GOVERNMENT_CHANGES_TO_VERIFY.csv` | Source-observed changed public projects |
| `GTA_RADAR_OPPORTUNITY_LANES.html` | Easy-to-read side-by-side rankings with original source links |
| `GTA_RADAR_OPPORTUNITY_LANES_STATUS.json` | Input counts, results, freshness/ownership warnings |

The normal integrated HTML dashboard links to all main outputs.

## Private rank factors

A clear industrial, warehouse, logistics, commercial, hotel, self-storage or
mixed-use development takes priority over an old generic application.
Project scope, explicit municipal application ID, official project detail
page, current planning/site-plan stage and explicitly named project firm
improve ranking. Appealed, older and issued-permit-stage projects rank lower.

The rankings use source-specific project records and the canonical municipal
inventory, but group related file numbers at the *same city and site* into
one opportunity. For example, 800 Burloak's OPA and ZBA file numbers
are one project, not two leads.

These are research hypotheses, not contract awards or claims of complete
private ownership. A planning consultant named on a title is **not**
automatically a developer, GC, purchaser or verified project-assigned
contact. Unknown names/emails/phones remain blank. A current record
in the public planning register isn't proof that work is still unawarded.

The initial private/Government Top 10 is an **active project ranking** (which
may include older active candidates). The daily change queue is separate.
`FIRST_OBSERVED` means first seen by Radar, NOT first published by the
municipality. Without an explicit verified publisher-date basis, it can
appear in `CHANGES_TO_VERIFY` but not `VERIFIED_FRESH`.

## Government lane

Includes only existing official planned-capital-contract and regional
project-detail records already screened by the independent procurement
gate. Awarded, completed, historical or deferred items in that gate
are not restored to the government top ten. No government row claims
an open tender without a separate official procurement verification.

## Running without repeating yesterday's collection

From the existing Windows code folder:

```powershell
python desktop_update.py
if ($LASTEXITCODE -eq 0) {
    python gta_opportunity_lanes.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"
}
```

This only re-reads existing CSVs; no network, model, source ledger reset,
or collector rerun. The next normal full run creates the outputs too.

## Developer acceptance

```powershell
python -m pytest -q tests/test_opportunity_lanes.py
```

A green test does not mean source-proven open work. Check source status,
original project, real developer, dated permit, current bid, assigned
purchaser and buyer contact before selling leads.
