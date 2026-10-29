# Unified PDF / meeting DeepSeek intelligence — integrated pilot

## What works in code
One entrypoint: `RUN_UNIFIED_PDF_VIDEO_AI_REVIEW.bat`. Accepts:

1. An existing *text-readable* local PDF — `pypdf` extracts each page, retains
   page markers and hashes the source.
2. A timestamped local transcript CSV — preserves all text segments.
3. An authorized local audio/video recording — `faster-whisper` transcribes
   it locally, then DeepSeek can interpret the resulting transcript.
4. A scanned PDF — optional `municipal_pdf_vision_ocr.py` renders unreadable
   pages using PyMuPDF and calls DeepSeek Vision after separate authorization.
   OCR text then enters the same page-marked DeepSeek understanding stage.
   Requires `py -3 -m pip install pymupdf`.

All paths converge on `municipal_unified_intelligence.py`: chunked inputs
with source markers → DeepSeek JSON interpretation → literal quote and
page/timestamp checks → review-only outputs.

## DeepSeek division of labour
DeepSeek **interprets** the extracted text (project mentions, event type,
organizations and quoted evidence). Whisper, **not DeepSeek**, converts raw
audio/video to words. Pypdf, **not DeepSeek**, extracts text from digital
PDFs. DeepSeek Vision is used for scanned PDF pages only when separately authorized;
video still goes through local Whisper and not through a native DeepSeek audio
transcription API. Vision OCR has only mocked API tests, not a verified live
scanned-PDF result. No claims about reliable PDF/OCR/video
processing without tests.

## First-run requirements
- Python and installed project dependencies (`pypdf`).
- For local recording transcription:
  `py -3 -m pip install faster-whisper`.
- An existing local recording obtained with permission. The tool does not
  fetch or bypass restrictions on streamed municipal videos.
- Existing Windows DPAPI DeepSeek key and the original
  `GTA_RADAR_RESULTS/v5_ai_budget.sqlite` ledger.

The launcher performs a free coverage preflight first. An opt-in authorization
then permits up to 3 bounded paid chunks and applies the repository North
Star's **US$0.25/day** cap in addition to existing shared V8 reservations.

## What the outputs mean
- `UNIFIED_COVERAGE.json`: source hash, total chunks, processed/unprocessed
  chunks, unreadable pages and conservative status.
- `UNIFIED_EVIDENCE.json`: literal quote existence and marker match. A quote
  match is **NOT semantic entailment** or proof of buyers, new construction,
  supplier stage or sales-ready opportunity.
- `MEETING_TRANSCRIPT.csv`: timestamped speech-to-text **UNVERIFIED**.
- `MEETING_TRANSCRIPT_MANIFEST.json`: provenance and transcriber info.

## Important limitations (do not misstate)
- A long document may have many chunks. The opt-in launcher analyzes only
  the next 3 unprocessed chunks per run and saves progress after each successful
  chunk; it **cannot claim full-document understanding** until all chunks have
  been processed. The coverage JSON reports the remaining chunks.
- No cross-document knowledge graph or semantic fact verification is yet
  performed by this unified pilot.
- Scanned/image-only PDF pages are detected, and optional DeepSeek Vision OCR
  can process up to two pages by default. It has not yet been tested on a real
  source using Windows credentials; OCR may misread names, layout or numbers.
- Audio transcription can misspell addresses, numbers and names; speaker
  identity is unknown.
- Timestamped transcript segments are batched to reduce paid API calls, with
  each original segment timestamp retained for evidence checks.
- Meeting transcripts can contain statements absent from a staff report.
  This is only a *candidate signal* until checked against the original
  recording and associated documents.
- AI reservations hold conservatively if provider usage cannot be accounted.
  The module does not circumvent existing unknown holds.
- No automated capture of videos, no paid transcription provider, no
  unattended processing, and no change to production V8.

## Evaluation gate
Before a city-wide rollout, test an authorized Toronto committee recording
against its matching agenda/staff report, and a varied set of PDFs including
five-property tax/exemption reports, industrial construction, existing
operations, awards, unrelated topics and unreadable scans. Verify project
recall, semantic evidence validity, buyer roles, procurement stage and
incremental facts from speech. Source originality, date provenance and
lead-time advantage matter more than transcription count.

## APIs and references (verified 2026-10-28)
- DeepSeek Chat Completions (text/structured outputs and optional image or
  file content): https://api-docs.deepseek.com/api/create-chat-completion/
- DeepSeek JSON output: https://api-docs.deepseek.com/guides/json_mode/
- DeepSeek vision: https://api-docs.deepseek.com/guides/vision/
- Local Whisper: https://github.com/SYSTRAN/faster-whisper
