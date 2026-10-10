# v0.10 Lead Research — first implementation

This package preserves v0.9 and adds a **candidate-driven investigation queue**, not a finished automated decision-maker search engine. Run `RESEARCH_LEADS.bat` after exporting business leads. It reads `data/business_leads_REVIEW_ONLY.csv` (fallback `data/lead_candidates.csv`) and generates `data/lead_research_REVIEW_ONLY.csv`, `data/lead_research_dashboard.html`, a research evidence template and URL search shortcuts.

To attach evidence, copy `data/research_sources_TEMPLATE.csv` to `data/research_sources.csv`, add the stable `candidate_id` from research output, official evidence URL, source type and verified details; rerun. Optional `python lead_research.py --fetch-official-pages` checks **explicitly provided** company URLs (max 20 default) and extracts published emails/phones when robots.txt allows. It does **not** infer which person owns a franchise, scrape web search results, query Ontario registry automatically, or guess emails. Conflicts are flagged, contacts remain `SOURCE_ATTACHED_UNVERIFIED` until human review.

The current business export contains recent events only; if no events exist, research queue can be empty. This is **not** a full automatic cross-source discovery implementation; automated company/brand/entity resolution and consent-aware outreach workflows are next.
