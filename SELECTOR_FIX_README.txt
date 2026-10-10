GTA Radar - Corrected Event Selection
====================================
This full package fixes the 578,538-record queue explosion.

What changed:
* A historical business directory listing is reference/enrichment data, not a new lead.
* An observation/download timestamp is not accepted as an event date.
* Only explicitly dated federal incorporation and business licence records can
  become standalone business-source opportunities.
* Every active municipal record with a qualifying source event date remains
  eligible even if company name/address are unknown or its relevance is LOW.
* Municipal candidates are placed ahead of business-only events in the queue.
* Only 500 new top-priority opportunities are admitted to the research queue
  per run. All qualifying dated events are retained in the review-only CSV.
* Collector audit includes all sources, including zero-selection sources.
* Nothing automatically certifies a lead as sales-ready.

IMPORTANT:
The two-day window uses calendar source dates (today plus the preceding two
calendar days), since many government feeds provide dates without times.
Publication/date semantics vary by source. We do not invent fresh dates.

INSTALL:
1. Extract this ZIP into the same 'new data' parent as older versions.
2. Open GTA_RADAR_EVENT_DATE_CORRECTED.
3. Double-click START_RADAR.bat.

Old versions and their databases are not modified. This makes a fresh copy.
Keep automated paid AI off until the queue is reviewed. If using daily runs,
install the task explicitly via INSTALL_DAILY.bat AFTER verifying output.

Limitations: We cannot verify actual Windows feeds with your local database here;
the test suite exercises the logic using representative sample records.
