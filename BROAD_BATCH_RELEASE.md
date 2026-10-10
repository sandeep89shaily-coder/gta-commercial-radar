# v0.7 Southern Ontario broad collector batch

Preserves all existing v0.6 and 3 staged v0.7 collectors. Adds 4 newly documented Durham GIS collectors, for 7 staged v0.7 collector additions in total (3 previous + 4 Durham). All disabled and need real network validation.

**Do not replace the daily-running v06_easy_setup installation with this development package.** No database included. No federal feeds.

## New Durham feeds
- PLANit consents: planning records with regional file/status fields but no structured address or last-modified date.
- PLANit regional official plan applications: same limitation.
- Durham business sites: reference directory with business name, street components, NAICS and updated date; do not label historical businesses as newly opened.
- Durham capital projects: project names, stages, status and DATEUPDATED; not automatically private commercial buying intent.

All potential feeds across Hamilton, Niagara, Waterloo, Halton, York and Durham are tracked in SOUTHERN_ONTARIO_ALL_SOURCE_AUDIT.md. Feed integration is an iterative evidence process; sources with no verified automated endpoint are not represented as built.

## Validation
Run python -m unittest discover -s tests -v. For source availability use python main.py doctor --source <id> in a disposable environment before adopting any production database.
