# GTA Radar AI harness — evidence-first pilot

The North Star (GTA_RADAR_NORTH_STAR.md) and Research Register (GTA_RADAR_RESEARCH_REGISTER.md) remain authoritative. This pilot **does not replace** the current collector, integrated daily launcher, review gates, source registry or desktop database. It does not claim newly verified buying authorities, supplier availability, direct contacts or time-to-discovery advantage.

## What is actually implemented

The new gta_agent_harness.py introduces a bounded orchestration layer over existing tested code:

1. Read the **existing** canonical V8 queue; refuse missing or unsourced input instead of inventing prospects.
2. Reuse deterministic commercial ranking and the evidence-first work allocator to form human-review tasks for the ten highest-ranked eligible projects.
3. **Default: free preflight.** No model calls, API-key reads, network research or DeepSeek spend.
4. **Explicit --paid:** acquire Radar's normal process-owned run lock, then call the existing gta_execute_ai_project_research executor with its approved tool policy, per-day ledger and shared cap from radar_config.py (**US$0.25/day**). No second budget or agent-side model call is introduced.
5. Reconcile saved results against the exact input hash, ignoring stale versions. Only fetched pages with recognized identity labels count as research coverage; even an exact-ID page is **review-only**, not a confirmed commercial lead.
6. Save AI_HARNESS_STATUS.json (atomic status snapshot), AI_HARNESS_EVENTS.jsonl (append-only execution events) and separate PROJECT_RESEARCH/ results. Never auto-promote leads or contact buyers.

This is a bounded orchestration harness, **not yet a fully autonomous agent**. Its reasoning and approved source-search actions come from the existing DeepSeek research implementation. Accuracy must be proven before any production integration.

## Windows use

Double-click **RUN_GTA_AGENT_HARNESS.bat** to perform a zero-cost preflight using the established Desktop/new data/GTA_RADAR_RESULTS workspace. This remains separate from RUN_TOTAL_INTELLIGENCE_TODAY.bat.

From a terminal in the installed repository:

- RUN_GTA_AGENT_HARNESS.bat
- RUN_GTA_AGENT_HARNESS.bat --paid --max-projects 2
- py -3 gta_agent_harness.py --workspace "C:\Users\YOU\Desktop\new data"
- py -3 gta_agent_harness.py --results "C:\path\to\GTA_RADAR_RESULTS" --paid --max-projects 2

Paid mode can incur charges even if no reviews finish. Earlier daily spending and ledger reservations count against the same shared US$0.25 ceiling. Do not run concurrently with the daily scheduled collector; the existing OS lock blocks supported simultaneous processes.

## Outputs and acceptance

- AI_HARNESS_STATUS.json: work plan, checkpoint status, executor result, budget state, and exact-ID versus context-only evidence counts.
- AI_HARNESS_EVENTS.jsonl: execution audit history.
- PROJECT_RESEARCH/: immutable source evidence and AI review saved by the existing research executor.
- Verified leads created is **always zero** by design: human review remains mandatory.

Before production merge: pass CI on Windows and Linux, inspect a real-data free preview, explicitly authorize any paid source-backed experiment, verify clear distinction among exact-ID/context-only source evidence, deferred tasks, and unsupported model claims. No proof of commercial acceptance is implied.

## Tests

python -m unittest discover -s tests

The new offline tests mock paid execution and cover no-spend defaults, resume with current inputs, evidence gates, and interruption safety.
