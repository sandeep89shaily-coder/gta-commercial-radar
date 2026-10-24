# GTA Commercial Radar — North Star and Unfinished Work
_Last reviewed: 2026-10-24. Durable decision log for future AI work; keep this file visible in every major Radar review._

## ONE business objective — do not lose sight of this

**Discover credible GTA / Southern Ontario commercial and industrial investments before suppliers are selected, identify the real buying organization and a lawful public contact path, and sell evidence-backed opportunities to relevant service providers.** Examples: commercial HVAC/refrigeration, industrial equipment, security/fire systems and other specialist vendors. This is a **qualified lead-intelligence business**, not a subscription search engine or a contest to accumulate permit rows.

Success benchmarks:
1. **10 individually validated, currently actionable opportunities** with original-source evidence, project identity, commercial scope, buyer/operator/developer relationship, public business contact/procurement path, procurement-stage assessment, and honest confidence labels.
2. **Two paying pilot customers** who find the intelligence timely and worthwhile.
3. Measure **lead-time advantage**, i.e. actual first public disclosure and first observed-by-Radar timestamps vs later planning/permit milestones. Never substitute an application submission date for publication date.

Hard operating principles:
- Start with Brampton, Mississauga and Toronto; expand to other GTA/Southern Ontario areas only when a feed demonstrates unique early value.
- **Earlier and more actionable beats larger datasets.** Favor pre-application investment clues over late-stage building permits where justified.
- Existing V8 desktop runner must remain unchanged until proven pilot value. Keep pilots isolated, manual and review-only.
- Use public free data and deterministic screening first; DeepSeek only for high-value questions, with a **US$0.25/day budget ceiling**, not on every row.
- Keep stable collectors; do not "upgrade in the name of upgrading." Never report candidate records as verified unique projects, genuine demand, an open contract or a qualified buyer.
- Avoid scraping that breaches terms; inspect public information, access methods and reuse restrictions.

## Existing baseline / implemented work (NOT evidence of sales readiness)

**October 24, 2026 early-signals pilot branch:** `feature/gta-early-signals-pilot-20261024`; GitHub PR #74; separate `data/early_signals_review.sqlite`; V8 not merged/changed.

Seven public ArcGIS sources: Brampton pre-consultations, Brampton rezoning/OPA, Brampton site plans, Mississauga site plans, Mississauga rezonings, York Region development applications, Toronto development applications.

Last *user-uploaded* V3 audit (2026-10-24): **32,269 GIS/source records**, **94.2% valid source dates**, **795 commercially plausible research candidates**; 165 research-first under pilot heuristic; **53 applications within 90 days**; 567 over a year old. These are historical application dates, not verified public notice timestamps. **No verified sales-ready opportunities or paying pilot customers shown.** The numbers are a snapshot, not live dashboard.

Date epoch parsing and source-date provenance, commercial-text tagging, conservative application grouping, source-quality audits, possible cross-stage address links, and evidence-gated buyer research queues are in pilot code. Brampton site plan still had **1,542 undated GIS features** in last audit; don't invent missing dates. York source record count was **6,773 features** with **6,756 published-reference/feature groups**, **not** 6,756 proven projects. Toronto 15,695 GIS features grouped to about 7,517 application groups; grouping is not proof of one project per group.

## Highest-value **unbuilt** earlier public cue feeds to investigate/pilot

Prioritized source discoveries from October 24 research (links are starting points, not guarantees of APIs or permissible bulk access):

1. **Municipal pre-application / public consultation meeting announcements and planning/council agendas**. First pilot: Burlington pre-application meeting notices; Brampton planning and development committee agenda items with developer and project PDFs. Could precede formal application and capture named investors and technical reports. Need determine stable feed/HTML/PDF access, publication timestamp, reuse rules, overlap vs existing permits.
   - Burlington planning process: https://www.burlington.ca/en/planning-and-development/burlington-planning-process.aspx
   - Existing Brampton council/public agenda portal needs current source endpoint verification.
2. **IESO connection application / assessment status** for new high-load users, plant expansions, substations and electricity infrastructure. High potential relevance for industrial HVAC/cooling, electrical and equipment suppliers. Need test whether actual project identity and first public disclosure are available; projects may already have suppliers.
   - https://www.ieso.ca/en/Sector-Participants/Connection-Process/Application-Status
3. **Improve the EXISTING ERO pipeline** rather than duplicate it; focus on *proposal-stage* ECA/EASR/industrial environmental approvals, plus Ontario environmental assessment commencement notices and Access Environment. Need operator/address matching with planning.
   - https://ero.ontario.ca/search
4. **Toronto Application Information Centre daily updates, public notice subscriptions**, check if earlier/different than already collected official Toronto ArcGIS feed, not a redundant collector.
   - https://www.toronto.ca/city-government/planning-development/application-information-centre/
5. **Milton, Pickering and Ajax** initial public planning notices, public posting dates, open documents and applicant contacts; Burlington/Oakville/Markham/Vaughan/Richmond Hill for later staged geographic expansion, **only after demonstrating unique lead time**.
   - https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/
   - https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/
   - https://ajax.ca/build-invest/for-developers-builders/planning-development-applications/
6. **Investment and business expansion announcements, land purchases/commercial leases, corporate relocations, AGCO public applications**. May precede planning or point to fit-outs; these are *research hypotheses*, not confirmed feeds. Watch noisy/consumer/residential signals and contact privacy.
7. **Actionability lane**: CanadaBuys and municipal early tenders/RFQs and contractor expressions of interest, useful for identifiable buying signals, although often later than preconsultation.
   - https://canadabuys.canada.ca/en

## Critical unmet gaps (not solved by installing another ZIP)

1. **Evidence-backed buyer/operator discovery**: planning file can list an agent, architect or named tenant, **not necessarily the person who buys**. Verify legal organization, developer, operator, work-package decision-maker and their lawful public business contact separately.
2. **Contract/vendor status**: determine whether relevant trades/consultants/contractors are already engaged, whether the project is active, and which supplier categories could actually bid. Mark UNKNOWN if unverified.
3. **Signal freshness**: distinguish application dates vs public *first-posted* dates vs Radar's *first-seen* dates; verify new notices independently and quantify advantage over permit-stage discovery.
4. **Commercial-fit precision**: exclude routine minor variances and residential-only projects; prioritize substantial equipment/building investment with concrete trade scope.
5. **History joins**: conservative same-project linking over pre-consultation, rezoning, site plan, permits and procurement using address, official file number, operator, description; never silently merge at the same address.
6. **Source economics and quality**: official URL/source event, source availability, duplicate rate, incremental new relevant projects/day, dates, collection rights, and AI dollars used.

## Near-term order of work

**Phase A — VERIFY source advantage (next):** Pilot only the top 2–3 early sources (Burlington/Brampton pre-application and agendas; IESO; existing ERO enhancement). Snapshot new items with first-seen history. Test source overlap with today's 7 feeds. Document actual early-versus-late disclosure for a small matched cohort. Avoid indiscriminate expansion.

**Phase B — VALIDATE 10 opportunities:** Investigate top recent industrial candidates plus compelling older projects; capture municipal evidence and current state, identifiable likely work packages, organization roles, contact path, procurement status and independent corroboration. Explicitly distinguish 'lead', 'research candidate' and 'sale-ready verified opportunity'.

**Phase C — SELL and learn:** Present a sample to targeted GTA suppliers, get **2 paid pilots**, track whether recipients found timely unawarded business and adjust selection criteria. Only automate/release into the daily production system after value is demonstrated.

## Reminder/review checklist

At each periodic review report:
- **North star** in one sentence; no technical detour.
- **What materially changed** (confirmed proof only, and since when).
- **What remains**, ranked by business impact, especially new early sources, buyer identity, vendor availability, 10-lead and 2-pilot targets.
- **Top three concrete next actions**, owner/blocker, and source-evidence links.
- **Avoid busywork:** Is there a demonstrated new lead-time or contact-quality advantage? If not, do not build more.
- Respect **US$0.25/day DeepSeek**, free public data, V8 isolation, no fake first-seen dates, no fabricated buyer data.

**Status on 2026-10-24: source research completed, free early-feed pilot *not yet built*, 10 sale-ready verified leads *not yet established*, 2 paying pilots *not yet achieved*.**
