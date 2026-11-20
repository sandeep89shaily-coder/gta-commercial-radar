# Industrial federal funding qualification — operational handoff

Existing full CSV **already downloaded** on the owner's other Windows copy:
`C:\\Users\\sande\\GTA_RADAR\\GTA_RADAR_RESULTS\\OFFICIAL_FEDERAL_GRANTS\\grants.csv`

New daily stage `gta_federal_capex_qualification.py` consumes the derived `GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_CANDIDATES.csv`; no additional dataset download and zero paid AI. It runs after the existing `gta_federal_industrial_funding.py` importer through `gta_equipment_commercial_daily.py`.

For an immediate rerun without re-reading the 2.3 GB original:
```powershell
Set-Location "C:\Users\sande\GTA_RADAR"
git pull --ff-only origin main
python gta_federal_capex_qualification.py --results "C:\Users\sande\GTA_RADAR\GTA_RADAR_RESULTS"
```

Outputs in the original GTA_RADAR_RESULTS directory:
- `GTA_RADAR_FEDERAL_CAPEX_QUALIFIED_RESEARCH.csv`
- `GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv`
- `GTA_RADAR_FEDERAL_CAPEX_QUALIFICATION_STATUS.json`

The process excludes pre-2025, generic educational/employment/agricultural funding and extracts industrial projects with explicit capital-equipment/plant expansion language. The *recipient city is not assumed project site*. The *federal agreement date is not verified first publication*. A company-name match is not a project match; if there are no local Radar exports in this separate checkout, status is `NOT_CHECKED_NO_LOCAL_RADAR_EXPORTS`. The Top20 is a research handoff for independently fetching project-specific source and procurement evidence. It makes no DeepSeek calls or outreach and never asserts RFQs or buyers. The current module does not invoke paid investigation automatically.

Acceptance next: compare against the original existing Radar workspace's saved outputs and manually assess the first 20; any true new projects require exact site and stage/source checks. This stage does **not** claim that process is complete.
