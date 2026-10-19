# GTA Radar V8 — DeepSeek native Search, Fetch and Flash

**Architecture:** Keep municipal and business collectors, 48-hour opportunity export and V4 grouping. The existing V6 daily runner calls `v8_deepseek_native.run`, rather than the earlier DeepSeek paid search-plan module or Bing/Google RSS. Uses the existing DPAPI DeepSeek API key and existing V5 SQLite spending ledger.

**New API endpoints:** `POST /v1/tools/search` (`query`, `count`, `need_content: true`), `POST /v1/tools/fetch` (`url`), and `POST /chat/completions` with model `deepseek-flash`, JSON output and thinking disabled. Authoritative docs: https://api-docs.deepseek.com/guides/search/ and https://api-docs.deepseek.com/quick_start/pricing/ .

**Cost controls:** Each request is reserved atomically **before** dispatch against the same US$1.00/day local allowance and includes spending already reserved by prior Radar versions. Successful Search or Fetch requests cost $0.00075 each; incomplete/network-failed calls retain reserved budget for safety until checked. Flash has an input-byte limit, output-token limit, and $0.008 conservative per-call reservation. Provider billing is independent and the application cannot impose a provider-side cap. Pricing may change; update bounds if official prices increase.

**Qualification:** Search snippets and result titles alone are not facts. DeepSeek-provided page content or fetched Markdown must explicitly match the source address, source identifier or company. Unverified results stay marked `AI_SOURCE_RECORD_REVIEW`. AI cannot invent company names, contacts, procurement intent or URLs. No automatic sales contacts or marketing are performed.

**Outputs:** `GTA_RADAR_RESULTS/GTA_RADAR_V8_INVESTIGATIONS.csv`, `GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv`, `GTA_RADAR_V6_DASHBOARD.html`, and the existing collector logs. The dashboard reports separate native Search, Fetch and Flash analysis metrics. A `SUCCESS` pipeline result is a successful data-processing run, not verification of sales leads.

**Installation:** `GTA_RADAR_V8_ONE_CLICK.bat` downloads the latest main GitHub code into `%LOCALAPPDATA%\GTACommercialRadar\V8` without overwriting existing desktop collector databases, then runs the existing V6 orchestrator with V8 investigation. Existing Windows task is replaced with the V8 runner at 8:30 AM if Windows scheduling succeeds.

**Validation:** Unit tests mock the DeepSeek API: no actual paid DeepSeek requests were executed during development. Live confirmation requires a configured key, account balance, a budget with room remaining, and internet connectivity. The old 2026-10-18 reservation history may prevent additional paid calls until the next local calendar day.