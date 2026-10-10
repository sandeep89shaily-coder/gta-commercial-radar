# v0.7 Southern Ontario Expanded Stage (not production-ready)

## Implemented additions in this stage
- Hamilton building and demolition permits, official ArcGIS table layer 6, with published permit/date/address/description fields.
- Kitchener active planning applications, official ArcGIS FeatureServer layer 0. Generic key OBJECTID only until live schema acceptance.

These are **staged, disabled collector configurations**, not validated production feeds. The previous 7 staged Southern Ontario collectors remain disabled, as do York and Mississauga staged feeds. All original enabled feeds and source code are copied unchanged.

## Safety
- Existing working v06_easy_setup database stays untouched.
- No `adopt` or `poll` in this staging folder.
- No claim that inaccessible portal-only candidates are implemented.
- Source-specific licence, freshest dates, record identity and live query must be verified before enabling.
- Full-snapshot behavior must be sized before use.

## Product purpose
Create qualified, evidence-backed commercial leads for resale to insurance brokers and other service providers. Historical government rows are NOT fresh leads.

## Testing
Run `python -m unittest discover -s tests -v`.
