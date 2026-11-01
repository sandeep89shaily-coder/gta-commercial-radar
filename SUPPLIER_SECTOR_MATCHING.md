# GTA Radar: all-sector supplier matching (manual review only)

**Purpose:** One real project can be relevant to several potential *customers of lead intelligence*. Do not restrict Radar to HVAC, contractors, or any one profession. Include material/equipment suppliers, specialty trades, engineering, energy, insurance, security, fire protection, cleaning, maintenance, facility services, and other relevant sectors.

**Not automatic sales:** Matching a category does **not** prove a purchasing authority, a supplier bid package, a need for a new vendor, a contract that remains unawarded, or an invitation to solicit. The user checks the project, timing, contact and availability using their own methods. There is no outreach, new contact scraping, or buyer/supplier-award verification stage.

## How matching works

- Read only the first-observed / changed project record's original `description`, not an AI-generated company or contact claim.
- Produce zero-cost deterministic suggestions in three groups:
  1. `SCOPE_LINKED`: category associated with an explicitly mentioned project work type (solar, paint booth, flooring, heritage, cold storage, loading doors, HVAC, etc.). This is **not** verified procurement.
  2. `POSSIBLE_PROJECT_SERVICE`: related design, engineering, construction support, insurance, fire/security, electrical, etc. Not established as required by the specific permit.
  3. `POSSIBLE_OPERATIONS_SERVICE`: cleaning, security, maintenance, IT, equipment and other post-completion / recurring services. Not an identified replacement or supplier contract.
- Each match has its `scope_phrase` from the original description, a broad `likely_service_phase`, and a fixed `SUGGESTION_ONLY_NO_AWARD_OR_BUYER_VERIFIED` label.
- Sparse/vague descriptions produce **no** generic guesses. Existing DeepSeek company/contact hints and their source links remain unchanged, as do date/status evidence.

## Daily output

The ordinary discovery runner `RUN_GTA_RADAR_DISCOVERY.bat` already generates the manual review files. After this change it adds supplier fields to the dated `GTA_RADAR_PROJECTS_TO_VERIFY_*.csv` and its HTML cards, and additionally exports `GTA_RADAR_SUPPLIER_MATCHES_<UTC timestamp>.csv`.

That **second CSV is filterable by supplier_family, supplier_category, match_tier, likely_service_phase and city**. One source project may appear in multiple rows, one per possible supplier category. `project_id` ties all rows back to the same project and its original source URL; this is *not* additional unique projects.

To regenerate the list from an existing `GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv` without polling, API calls, or altering the originals:

```powershell
py -3 gta_manual_project_list.py --results "C:\path\to\GTA_RADAR_RESULTS"
```

It writes new **timestamped** CSV and HTML files and a small status JSON in that results folder. Previous dated reports and manually edited notes are preserved. To match the exact ten-project November 1 group, filter the new CSV by the ten frozen project IDs in `config/google_pilot_reviewed_projects_20261101.txt`; this matching module itself does not switch the original project cohort.

No effect on DeepSeek (US$0.25/day), Gemini pilot (US$5/month), collectors, scheduling, procurement research, or source history.
