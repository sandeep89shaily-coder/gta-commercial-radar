# Permanent GTA Radar — V8 migration, scheduled collection, operations dashboard

Development branch implementation. No desktop machine or Task Scheduler
was modified by this GitHub change.

### First-time migration (do once, with your existing source database)

Install Python 3.11 dependencies in a stable repository checkout, then:

    python radar_workspace.py --home "C:\GTA_Radar" init
    python radar_workspace.py --home "C:\GTA_Radar" adopt-v8 "C:\OLD_RADAR\data\radar.sqlite"

The one-time migration copies a consistent SQLite snapshot into
\`C:\GTA_Radar\Data\radar.sqlite\`. It refuses overwrites. The historical
V8 \`records_current\`, \`record_versions\`, \`changes\` and source \`runs\`
are indexed into \`radar_master.sqlite\` and existing original data remains
unchanged. Extra pilot histories can be imported read-only with
\`radar_workspace.py --home ... import OLD_FOLDER\`.

### Run and verify

    python radar_production.py --home "C:\GTA_Radar" run
    python radar_production.py --home "C:\GTA_Radar" dashboard

The runner calls the existing V8 collector's smart poll, then the ten
committed early investment runner groups, imports evidence history into the
same master database, and writes:

    C:\GTA_Radar\Results\GTA_RADAR_OPERATIONS.html

The dashboard shows V8/early source health, recent source change events,
historical counts and early-research candidates. It is a local HTML file,
**not** a public live web service. An open browser reloads it every five
minutes, and the run regenerates it after each poll. A failed source is not
represented as zero projects.

### Schedule only after local validation

    python radar_production.py --home "C:\GTA_Radar" install-schedule --daily-at 08:30

On Windows this installs a single task \`GTA_Radar_Consolidated\`, writing
a stable launcher in the permanent workspace. After collection reliably
finishes within a shorter cycle, optional \`--every-hours 2\` can replace
the daily cadence. The PC and Windows account must be available.

**Disable the old V8 scheduled task manually before enabling the new task.**
The installer never changes unrelated existing tasks. It refuses to run if
another consolidated collection holds \`production.lock\`. In the event of
a crash, inspect the lock and log before manually clearing it.

### Scope and safeguards

- Existing V8 collector history is copied, not rebaselined or dropped.
- Scheduled collection uses **zero DeepSeek calls**; previous US$0.25/day
  experimental budget is unchanged. AI can be integrated after stable
  collection is validated, without auto-enabling expense.
- The newer Business Openings and uncommitted unified-engine ZIP patches
  are not on this GitHub development branch. Do not mistake this step for
  full migration of those local experiments.
- Raw delta files in legacy installations are not copied automatically.
  They remain available in the old source folder.
- Historical import is not evidence of newly available purchasing contracts.
- Success in offline tests doesn't prove the scheduled collector runs on
  the user's Windows hardware. The desktop migration and scheduled task
  must be tested locally before a production switch.
