GTA RADAR — DEEPSEEK DAILY EDITION

ONE-TIME WINDOWS INSTALL
1. Keep all old folders. Extract this new GTA_RADAR_DAILY folder in your existing "new data" directory.
2. Double-click START_RADAR.bat once to import a safe COPY of the old database (if none already exists).
3. Double-click INSTALL_DAILY.bat; paste your DeepSeek API key once when asked.

DAILY OPERATION
- Windows Task Scheduler runs DAILY_RUN.bat at 6:00 AM LOCAL PC TIME while the PC is running.
- No OpenAI or Brave API key is needed for this edition; DeepSeek is the only paid API.
- Data collectors and candidate preparation run without AI.
- DeepSeek analyzes only already-collected, non-search-snippet evidence; it does NOT conduct live web searching by itself.
- Daily allowance: at most 50 requests/leads and USD $0.50 in conservative prepaid reservations.
- Spend ledger: data/deepseek_budget.sqlite, never removes reservations after errors.
- At most 3600 input / 850 output tokens and conservative rates of $1/million input, $4/million output for model deepseek-flash; re-check these assumptions before use if pricing increases. If actual provider prices exceed these ceilings or billing changes, local cap is not a guaranteed provider-account cap.
- Outputs: data/deepseek_results_REVIEW_ONLY.csv, data/daily_run.log.
- No automatic sales approval or contact guessing.
- The current initial historical baseline may produce 0 candidates; this package DOES NOT yet implement backfill discovery or free autonomous web search. Those are separate remaining work.
- A task missed because the PC is off may not run until next scheduled time. The task uses the same Windows account that installed it.

The DeepSeek key is encrypted using Windows DPAPI for the current Windows user, and the application never stores it as plain text on disk.
Do not share your key or screenshots containing it.
