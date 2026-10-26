# GTA Radar: Early investment + planning cues — desktop pilot

## What changed

The **nine existing early-collector groups** (21 feed definitions, 17 distinct
additional to old V8) are retained. One **new runner** monitors four new,
independently baselined streams:

- FedDev Ontario public Atom news and a bounded scan for official recipient
  backgrounder tables. Recipients are project announcements, **not unawarded
  purchases**. Official feeds have finite rolling windows; this is not all grants.
- Invest Ontario public press-release listing and limited article details.
- Maple Leaf Foods published company announcements. **Only this one company is
  seeded for corporate capex**, not all public or private manufacturers.
- Altus Group's public weekly commercial-real-estate review. This is
  **market/transaction context**, not an exhaustive leasing or relocation feed;
  it is blocked from automatic paid buyer research.

These are 4 *source definitions*, not proof of GTA-wide completeness or four
complete markets. The older Ontario government news RSS continues separately.

## One-click desktop operation

Extract the ZIP. Keep its `radar` folder next to the start BAT files.

**START_EARLY_CUES_FREE.bat**: runs public collection only, no DeepSeek.

**START_EARLY_CUES_DEEPSEEK.bat**: also permits DeepSeek research of **fresh,
qualified** new/updated observations within a **USD 0.25 per local day software
ledger ceiling**. The provider's account-level charges and other installations
are independent of this software cap. An existing configured DeepSeek key and
provider service access are required. It will not purchase unbounded research
or analyze the entire historical archive.

Neither BAT installs a task, changes original V8 settings, or runs the old V8
permit/business collectors. Both reuse the isolated, persistent
`Desktop/new data/GTA_RADAR_V8_EARLY_PREVIEW` database history established in
our previous desktop run. The original Radar database and existing scheduled
task are unchanged. **Do not delete the preview data folder between runs.**

One main report appears automatically after each run:

    Desktop/new data/GTA_RADAR_V8_EARLY_PREVIEW/GTA_RADAR_RESULTS/GTA_RADAR_EARLY_INVESTMENT.html

The main report links to the per-source status table, new qualified observations,
unqualified records, investment-index review and retained DeepSeek results.
A source failure/partial feed is not an absence of projects.

## Research and safeguards

- The first successful collection creates a baseline; historical public
  releases are *not* falsely labeled today's new opportunities.
- A new or changed record requires source evidence, commercial context, and a
  sufficiently specific project. Generic reports, residential records, and
  funding announcements with no identified company or location are held.
- The DeepSeek research request asks about possible purchase categories, the
  company, buyer roles, buying windows and whether vendors have already been
  selected. When evidence is insufficient, each is left unverified.
- Research output is **not** an automatic verified lead, evidence of an
  unawarded contract, or permission to contact people.
- The live source endpoints have been checked in public search. Automated tests
  cover parsers, baselines and the paid gating, but a live Windows collection
  is still needed to confirm complete feed health.

## Priority gaps

1. Expand corporate capex coverage beyond the Maple Leaf Foods pilot;
   add more company-approved public investor/news sources one at a time.
2. Expand industrial leasing discovery beyond Altus market/transaction context.
3. Repair the existing Burlington ward and Brampton agenda pilots.
4. Verify buyer/procurement states and actual lead-time for the first 10 cases.

This is a source-backed, conservative prototype—not a verified lead marketplace.
