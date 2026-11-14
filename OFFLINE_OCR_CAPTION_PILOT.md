# Optional local OCR and timestamped caption review

These modules extend the North American document intelligence architecture without changing the primary Radar database, historical ledgers, paid AI cap, source collectors, or manual seven-stage launcher.

## What is implemented

- `gta_local_pdf_ocr.py`: Bounded, offline OCR of a specifically selected PDF already inside the operator's workspace. Skips pages containing substantial selectable text, attempts a maximum of three pages, labels OCR-extracted excerpts `UNVERIFIED_OCR_TEXT`, records source SHA-256 and page numbers.
- `gta_local_caption_evidence.py`: Offline WebVTT parser using a versioned `GTA_RADAR_MEDIA_INPUTS.json` manifest. Captures source hash, recording URL, timestamp intervals, bounded commercial-keyword excerpts. No audio download or transcription is performed.
- The ordinary full-run report invokes only the caption review, and only on already registered local files; absence of a caption manifest reports `NO_EXPLICIT_CAPTION_MANIFEST`. OCR remains explicitly selected, to avoid automatically running external programs on potentially untrusted PDFs.

## OCR Windows prerequisites

Optional local executables `pdftoppm` (Poppler) and `tesseract` (Tesseract OCR) must be installed separately and available on PATH. Neither dependency is automatically downloaded by Radar. `pypdf` is already in standard requirements.

Example with an authorized, already downloaded local PDF:

```powershell
python gta_local_pdf_ocr.py --workspace "C:\Users\sande\Desktop\new data" --pdf "my_saved_council_agenda.pdf" --out "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS\GTA_RADAR_LOCAL_OCR_REVIEW.json"
```

PDF must be inside the workspace. If dependencies are missing or the text has no relevant content, the status records that limitation. A test-generated PDF is not evidence of live municipal extraction.

## Captions manifest

Create a version-1 JSON file at `<workspace>/GTA_RADAR_MEDIA_INPUTS.json` to process operator-supplied WebVTT captions on the next manual run:

```json
{
  "version": 1,
  "captions": [
    {
      "city": "Brampton",
      "file": "saved_council_meeting.vtt",
      "recording_url": "https://www.brampton.ca/"
    }
  ]
}
```

Replace the placeholder recording URL with the **exact original meeting recording URL**, and use only recordings/captions you are authorized to access and process. The file must be locally saved inside your workspace. For standalone review:

```powershell
python gta_local_caption_evidence.py --workspace "C:\Users\sande\Desktop\new data" --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"
```

Output: `GTA_RADAR_CAPTION_EVIDENCE_REVIEW.json` (included by the existing safe archive filename convention).

## Remaining gaps

Actual audio/video speech-to-text, speaker diarization, transcript/minutes reconciliation, source permission verification, and automated OCR fallback from live provider documents are **not** implemented by this PR. They need additional opt-in architecture and independently checked sample recordings.

No OCR snippet or VTT cue is sufficient to establish an approval, first public publication date, exact project, buyer, open contract, or procurement opportunity. Source-file dates and Radar first-observed timestamps remain separate.
