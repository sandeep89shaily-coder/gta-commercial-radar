# Toronto TMMIS agenda item evidence extraction — manual pilot

This source-bound parser reads a **locally saved HTML snapshot of an actual official Toronto TMMIS agenda** and separates agenda item headings by exact item code (e.g. `PH30.1`). It associates background PDF links only when they match Toronto's official `backgroundfile-<id>.pdf` attachment pattern. It does **not** make network calls, read PDFs, spend DeepSeek, or change the production Radar database.

Toronto explains that agenda items have an item number, recommendations/summary sections and Background Information links: https://www.toronto.ca/legdocs/tmmis/help/help1.htm . The exact accepted meeting URL format is already enforced by `toronto_tmmis_documents.py`, reused here.

## Manual research use

From the repository checkout:

```powershell
python gta_toronto_agenda_item_extraction.py --saved-html "C:\Research\saved_toronto_agenda.html" --meeting-url "https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda" --out "C:\Research\review"
```

Outputs:
- `TORONTO_AGENDA_ITEMS_REVIEW.csv`: per-item code/title and exact background links.
- `TORONTO_AGENDA_ITEMS_EVIDENCE.json`: evidence-level tags, HTML SHA-256, separate source fields and explicit zero-verified-project counters.

A candidate with `RESEARCH_CANDIDATE_TITLE_ONLY` merely has construction-relevant words in its **agenda item title**. This does not prove a new development, buyer, project age or contract. The saved HTML must have been obtained through permitted official access. We do not automatically fetch arbitrary external pages.

## Acceptance and next work

1. Compare extracted item codes and PDF associations with at least 10 actual TMMIS agenda entries; treat missing/changed HTML heading structures as parser limitations, not "no items".
2. Use the existing official, robots-checked PDF capture layer on authorized direct attachments, and extract cited page text using existing PDF tooling.
3. Extend eSCRIBE/Granicus or other platform adapters for Brampton and Mississauga only after official source format and access permissions are verified. Do not guess their item IDs from Toronto conventions.
4. Match exactly documented application IDs/addresses to historical permits; separately track observed date, agenda meeting date, original publication evidence.
5. Keep all AI analysis review-only and subject to the US$1/day integrated DeepSeek cap; do not add extra paid calls or a scheduled run in this pilot.
