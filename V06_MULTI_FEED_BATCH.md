# v0.6 multi-feed source batch (staged)

## Strategy
Keep the working v0.6 integrated database and lead candidate exports running daily. In parallel, stage multiple verified-schema public-source adapters instead of serial one-source releases. Free access does not automatically establish permission to redistribute commercially.

## Three staged collectors
- `mississauga_site_plan_applications` — official Mississauga site-plan ArcGIS layer, applications active or approved since 2016. Site address, applicant, description, status, application dates and non-residential GFA fields.
- `mississauga_rezoning_applications` — official Mississauga rezoning ArcGIS layer, applications active or approved since 2016, similar site/application fields.
- `richmond_hill_active_development_applications` — official Richmond Hill ArcGIS layer, owner, address, description, status; application received date is a STRING, so incremental date retrieval is not yet safe.

All three are **configured and disabled** (`enabled=false`), use existing `arcgis` collection code and full monthly snapshots until live freshness/identity tests establish a safe more-efficient strategy. No claim of completed live collection or business-licence clearance is made. The original York regional collector remains unchanged, and its date anomaly remains unresolved.

## Desktop validation (from this version's directory)
1. `python -m unittest discover -s tests -v`
2. `python main.py doctor --source mississauga_site_plan_applications --source mississauga_rezoning_applications --source richmond_hill_active_development_applications`
3. If doctors pass, test individual source baselines in your EXISTING working data directory:
   `python main.py poll --source mississauga_site_plan_applications --source mississauga_rezoning_applications --source richmond_hill_active_development_applications`
4. `python main.py status`

Do not run adoption again if your v0.6 integrated data folder has already been adopted. This package contains no database. Back up your `data/radar.sqlite` before the new baselines. The three historical baselines do not prove three commercially qualified fresh lead sources. Do not enable unattended polling until data freshness, record IDs, duplicate overlap and licensing have been reviewed.

## Work still outstanding
Complete a broader York, Halton, Durham and federal free-source audit; integrate source families with reliable access in batches; normalize businesses and property identities; use stored records for historical prospect research separately from daily NEW/UPDATED event-based leads; qualify and sell leads to relevant service providers.
