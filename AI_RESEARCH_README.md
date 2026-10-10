# v0.11 — AI investigation module (first stage)

This package contains the complete v0.10 application plus optional AI investigation. It does **not** include your live SQLite databases, and it does not overwrite v0.10.

## Windows setup
1. Extract alongside the existing v0.10 folder. Keep that folder and its databases.
2. Copy your existing `data` directory into the new release if needed; never replace the original.
3. Run `RESEARCH_LEADS.bat` to create candidate IDs. Use `research_sources_TEMPLATE.csv` to create `data/research_sources.csv`, putting at least one verified public URL and factual evidence for each candidate ID.
4. Run `AI_PREVIEW_NO_COST.bat` to see which candidates have evidence.
5. To enable AI, create `OPENAI_API_KEY` as a Windows user environment variable (never put it in a CSV or share screenshots of it), restart the terminal, then run `AI_INVESTIGATE.bat`. API usage is billed separately from ChatGPT. You can change model with `RADAR_AI_MODEL`.

## Outputs
`data/ai_investigations_REVIEW_ONLY.csv` and `data/ai_investigation_audit.csv`. The analyst uses only evidence supplied for each lead; the API does **not** browse the internet. Evidence IDs support its proposed extraction and all claims remain REVIEW_ONLY. Unsupported names, email addresses and phone numbers are blanked out. If no evidence exists, the result is `NO_EVIDENCE`.

## Scope and limitations
This is a working, opt-in evidence-analysis module, **not** an autonomous internet-investigation agent. Automated web discovery, licensed search APIs, additional live feeds, Ontario registry authorization, source-specific provenance for each field, CASL/privacy compliance workflow and sales-ready approvals remain future work. AI result must not be used for automatic marketing, and the key must never be committed or stored with program data. First test on a small batch to estimate cost.
