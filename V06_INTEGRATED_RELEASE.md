# GTA Commercial Radar v0.6 integrated foundation

## Business objective
Identify new commercial buying opportunities using free, appropriately licensed public data and sell verified, service-provider-specific leads to relevant providers. A permit or registry row is **not** itself a qualified lead; a possible service requirement is **not** confirmed intent to buy.

## Implemented in this package
- Preserves all v0.5 collectors and smart polling and the preview's York candidate source (still disabled pending freshness and licensing validation).
- Adds `commercial_engine.py` for conservative grouping of **recent change events** by jurisdiction + normalized full address (units retained). Does not rewrite the observation SQLite schema.
- Emits `data/opportunities_REVIEW_ONLY.csv` and eight service-provider-category CSVs in `data/buyer_leads_REVIEW_ONLY/`.
- Each buyer row preserves source ID and key references, number of supporting change signals, timing, and mandatory manual qualification notes.
- Adds `python main.py leads --hours 720` to refresh review-only leads without contacting remote collectors. `poll` and `status` also refresh the review exports.
- Adds `config/free_feed_pipeline.csv` tracking 20 multi-region source research targets without falsely enabling unverified connectors.

## Important limitations and safeguards
- Grouping by normalized address **is not verified entity resolution**. Different businesses can share a location, and slight address spelling differences may fragment the same project. Review-only output is intentionally NOT_FOR_SALE.
- Candidate generation only uses non-LOW `NEW`/`UPDATED` observations within the selected lookback window. The long history and baseline records are not automatically converted to current leads. A baseline can still produce log-level NEW counts; it is not evidence of a market opening.
- Buyer categories are text-matched hypotheses and require checking stage, buyers, contact methods, location, and legal permission before selling.
- York GIS is still disabled in normal polling pending date/freshness research. Its first baseline and repeat-poll behavior were demonstrated by the user, but the reported latest source date in 2018 is unresolved.
- This release is an integrated *foundation*, not the complete multi-region collection network or live commercial sales operation.

## Upgrade steps
1. Keep the current `gta_commercial_radar_v06_preview` and `gta_commercial_radar_v05` folders as backups.
2. Extract this ZIP into a separate `gta_commercial_radar_v06_integrated` folder.
3. `python -m pip install -r requirements.txt`
4. `python -m unittest discover -s tests -v`
5. Adopt the **most current** persistent data directory ONCE (your v0.6 preview already includes the York baseline):
   `python main.py adopt --from-data "..\gta_commercial_radar_v06_preview\data"`
6. Generate current candidate exports WITHOUT polling: `python main.py leads --hours 720`.
7. Check data source status: `python main.py status`.
8. Continue normal scheduled poll separately once data and source selection are checked.

## Next release workstreams
A. Verify available York/Peel/Halton/Durham and federal source schemas, licence, and freshness, then batch-enable validated collectors.
B. Add unit-safe address canonicalization, jurisdiction/city disambiguation, and persistent business/property/project entities with human-review matches.
C. Add qualification and freshness verification, contact provenance, buyer-specific product rules, lawful outreach process and conversion feedback.
D. Track sales outcomes and revenue by buyer industry; prioritize sources by *sellable lead yield*, not record counts.
