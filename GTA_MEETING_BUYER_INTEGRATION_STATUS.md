# GTA Radar Meeting + Buyer Pipeline — Implementation Audit (October 28, 2026)

Status: REVIEW-ONLY development branch; production V8 unchanged.

## Business objective
Discover Southern Ontario commercial/industrial projects early, identify the true purchasing organization and lawful public business contact route, check vendor selection, validate ten actionable opportunities and two paid pilots. This is not merely a transcript or a permit database.

## Completed code
- municipal_meeting_capture.py: bounded official Toronto/Brampton HTML discovery; video links retain official source and unresolved agenda identity.
- municipal_youtube_api.py: official YouTube Data API v3 metadata discovery with supplied YOUTUBE_DATA_API_KEY; no unauthorized download.
- municipal_agenda_video_link.py: exact recording link on official municipal agenda is the only verified agenda match.
- municipal_captions_to_transcript.py and municipal_meeting_transcription.py: timestamped authorized local captions or local Whisper media.
- municipal_unified_intelligence.py: budgeted, resumable DeepSeek interpretation; preserves page/timestamp evidence; not verified sales leads.
- municipal_official_buyer_research.py: official public website checks by whole street address, not isolated street words.
- municipal_deepseek_buyer_research.py: bounded AI proposals of organizational roles from sourced excerpts, exact quote checked.
- municipal_buyer_procurement.py: buyer/award assertions remain UNKNOWN absent independently checked official evidence.
- municipal_evidence_graph.py and municipal_cross_source_synthesis.py: source-linked candidate identities and contradictions; no false confirmed project merger.
- RUN_MEETING_BUYER_ONE_CLICK.bat: Windows discovery, authorized local caption import, optional budgeted DeepSeek and official buyer source checks.
- All work remains on draft PR #79.

## Public sources checked
- Toronto meeting video index: https://www.toronto.ca/city-government/council/council-committee-meetings/watch-toronto-city-council-live/
- Brampton agendas and videos: https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/
- Toronto procurement portal (open, pending, awarded, cancelled): https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/
- Toronto award notices: https://www.toronto.ca/business-economy/doing-business-with-the-city/follow-up-on-city-contracts/
- YouTube terms: https://www.youtube.com/t/terms

## Boundaries
The public visibility of a video does not authorize YouTube scraping/downloading for a commercial product. Official YouTube Data API supports channel/video metadata but not arbitrary public caption downloads. The pilot therefore uses authorized local captions/media, and fails closed on unauthorized content downloading. Toronto indexing may be restricted and Brampton feeds may require dynamic pages; no bypass is implemented.

Official procurement portals can load records via JavaScript. Checking only static HTML does NOT prove no tender exists. Merely naming an architect, site developer, or agent does not verify a purchasing decision-maker. AI-suggested roles and vendor status remain unverified.

## What is still NOT completed
- No live full meeting transcription, real authorized caption capture, and timestamp/agenda matching audit has passed in this turn.
- No live end-to-end demonstration of actual buyer/contact validation or specific unawarded commercial supplier contract.
- No verified first-publication discovery advantage or ten qualified leads.
- No legal permission established for bulk YouTube video/caption capture.
- No automatic connection to the existing V8 production schedule, deliberately.
- No proof of two paying pilot customers.

## Acceptance gates
1. Pair 3 original official municipal meeting recordings (with permitted content access) with agenda source, PDF, timestamps and complete transcript.
2. Measure new correctly attributed commercial claims obtained uniquely from speech versus written sources.
3. Individually verify purchasing entity, lawful public contact route, exact supplier work package, and independent current tender/award status on 10 candidate projects.
4. Record immutable first observed timestamp and independently evidenced publication/permit dates to quantify lead-time advantage.
5. Keep shared DeepSeek budget at or under USD 0.25/day and production V8 unchanged until these gates pass.

Use RUN_MEETING_BUYER_ONE_CLICK.bat from the branch for a review-only local run. A completed GitHub test proves code correctness, not commercial lead quality.
