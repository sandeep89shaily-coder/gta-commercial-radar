# v0.12 — Autonomous Web Investigator

New: Brave Search API discovery (up to four query variations per candidate), safe public-page visits with prior robots checks, extracted contact hints, cached results, optional OpenAI structured evidence reconciliation, auditable CSV exports, and hard per-run limits. Existing collectors and databases unchanged.

Local test suite: 95 tests passed, including mock search/caching/safety tests. **No live Brave/OpenAI calls were made in the release build.** It is incorrect to treat these as real-world source verification. Autonomous online research requires access to those external services.

No registry scraping; no guaranteed director/franchisee resolution; no auto-sales approval. See AUTONOMOUS_README.md.
