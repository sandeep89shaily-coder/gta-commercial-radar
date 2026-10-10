# Expansion after v0.5

Public sources → adapters → incremental/snapshot ingestion → normalization → SQLite versions/change history → commercial-change feed. v0.5 adds AGCO cannabis and seven Peel categories while preserving existing feeds.

## Coverage next

1. YorkSafe + Vaughan / Markham / Richmond Hill planning and permits.
2. Peel municipal business licensing and Caledon permits alongside the working health feeds.
3. Halton health + Burlington / Oakville / Milton.
4. Durham Check&GO + Pickering / Ajax / Whitby / Oshawa.
5. AGCO liquor when a dependable public machine interface is verified.

Every adapter must support incremental retrieval, metadata before download, or a deliberate low-frequency snapshot. Keep daily polling separate from backfill.

## Product work alongside coverage

Preserve evidence and first-seen/change history now. Next add normalized addresses, unit-aware entity matching, and project/operator timelines. Keep ambiguous matches reviewable. An inspection corroborates activity but does not establish a new opening or design spend on its own.

Measure fresh unique events, identifiable operators, address completeness, failures/publication freshness, corroboration and lead time. Add buyer-specific scoring only after the buyer and useful lead criteria are defined.
