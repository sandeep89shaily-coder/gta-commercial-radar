# Collector consolidation register — 2026-10-24

Owner direction: integrate all independent operating collectors and reconsider all 14 disabled main sources. Do not build additional unrelated functionality.

## Existing main pipeline
- Core collection: municipal and business collectors using config/sources.json and config/business_sources.json.
- Nine independent collection groups now wired into V8 development pipeline: early_signal_watch, early_cue_watch, early_discovery_watch, early_hamilton_watch, early_public_notices, early_ajax_watch, early_oakville_watch, early_markham_circulation, early_investment_tenders.
- Integration into **collection execution does not equal verified promotion to the commercial selector**. The bridge currently ingests five groups; Ajax/Oakville/Markham/investment remain review-only.
- Independent early_ajax_arcgis.py must be assessed against early_ajax_watch.py for duplicated Ajax coverage **before** adding a second run.
- early_* buyer, quality, dossier, lead-time, scope, summary and publisher probes are downstream analyses/diagnostics, not additional network collectors. They need assigned stages and automated reporting rather than being counted as separate feeds.

## Disabled source disposition (all 14)
- Priority planning: york_region_active_development_applications; mississauga_site_plan_applications; mississauga_rezoning_applications; richmond_hill_active_development_applications; hamilton_development_applications; kitchener_active_planning_applications.
- Planning adjuncts: durham_planit_consents; durham_planit_opa; durham_capital_projects.
- Permits: waterloo_city_building_permits; st_catharines_building_permits; hamilton_building_demolition_permits.
- Historic/enrichment: toronto_cleared_building_permits; durham_business_sites.

## Actual status and activation gate
13/13 disabled ArcGIS metadata and three-record samples responded, with stable IDs in those small samples. Kitchener has populated application and public-status dates; Hamilton has no identified date fields; three Durham feeds have sampled missing dates. Toronto CKAN historical permits not checked by ArcGIS probe.

**None of these facts proves reliable full ingestion.** All 14 remain disabled in production. To integrate into the main collector, require validated pagination, source-field meaning, non-residential filtering, stable IDs, safe first baseline, incremental changes and source availability. Keep any failed source represented explicitly as BLOCKED; never label it as zero commercial opportunities. For feeds with missing publisher dates, carry first-observed and publication date separately.

## Release criteria
1. One unified daily inventory and execution status for all core/independent/staged feeds.
2. Each early feed's confirmed post-baseline change mapped to canonical opportunity input (otherwise explicitly review-only).
3. One cross-feed project identity/deduplication path; no historic baselines as fresh cues.
4. Downstream buyer/contract investigation uses validated signals only, within US$0.25/day.
5. CI and isolated live checks pass before enabling disabled sources or altering user's Windows installation.

No changes to enabled source flags in this document.
