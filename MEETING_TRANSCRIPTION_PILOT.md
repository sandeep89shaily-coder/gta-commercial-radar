# Meeting video transcript pilot — GTA Radar

**Review-only feature:** local timestamped speech-to-text from a file already
obtained with appropriate permission. No automated YouTube download, no
DeepSeek charge, no production updates and no sale-ready leads.

Toronto posts live/archived meetings and searchable video indexes:
https://www.toronto.ca/city-government/council/council-committee-meetings/watch-toronto-city-council-live/

Model: [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper),
running locally. CPU int8 is the default for broad compatibility; CUDA is an
optional future configuration and depends on local supported libraries.

## Windows setup
Run once: `py -3 -m pip install faster-whisper`
Use `RUN_MEETING_TRANSCRIPTION_REVIEW.bat`, supply an **existing local**
recording path (or drag a local media file onto the batch file), paste original
HTTPS meeting URL, confirm. On first use the model may download. Transcription
can take substantial local compute resources. It does not fetch videos.

Outputs in `MEETING_REVIEW`:
- `MEETING_TRANSCRIPT.csv`: timestamps, transcript, keyword triage flags,
  original source URL and file checksum; **unverified speech-to-text**.
- `MEETING_TRANSCRIPT_MANIFEST.json`: provenance, counts and zero API charges.

Optional comparison against an already verified downloaded municipal report:
```
py -3 municipal_meeting_pdf_comparison.py --transcript MEETING_REVIEW/MEETING_TRANSCRIPT.csv --pdf PATH_TO_REPORT.pdf --out MEETING_REVIEW/WRITTEN_COMPARISON.json
```
Overlap is a review hint, **not** confirmation of speaker identity, meeting
decision, actual project, developer, supplier status or contract timing.
A reviewer must listen to segments, verify exact location in the source recording
and reconcile with written council documents before publishing.

## Limitations
- Does not collect or download streams; recording must be available locally.
- Keyword triage may miss synonyms and generate false alarms.
- Does not diarize or confidently attribute speakers. Never invent speaker roles.
- Speech transcription may mishear names, addresses, dates and quantities.
- No automatic project identity graph or supplier research integration yet.
- Requires source access and reuse rights checked per municipality.
- Video indexing/captions may already be adequate; prefer existing accessible
  transcript when available, before consuming local CPU.
- Live evaluation must establish whether audio discovers **new corroborated
  early/commercial facts not in agenda PDFs**. If not, do not scale.
