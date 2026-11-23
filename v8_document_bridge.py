"""Read-only V8 document review bridge; no collectors, AI, scheduler, or DB writes."""
from __future__ import annotations
import argparse
import csv
import html
import json
from pathlib import Path
from document_evidence_review import build

CANDIDATES = "CANDIDATES_V4_ALL_REVIEW_ONLY.csv"
INVESTIGATIONS = "GTA_RADAR_V8_INVESTIGATIONS.csv"
MANIFEST = "DOCUMENT_SOURCE_MANIFEST.csv"


def ids(path):
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as h:
        return {str(row.get("project_id") or "").strip()
                for row in csv.DictReader(h) if row.get("project_id")}


def bridge(results):
    results = Path(results).resolve()
    candidates = results / CANDIDATES
    if not candidates.is_file():
        raise FileNotFoundError("Existing V8 candidates missing: " + str(candidates))
    # This manifest is a documented opt-in list, not an invitation to scrape or
    # claim that a source document exists when only an investigation URL exists.
    manifest = results / MANIFEST
    if not manifest.exists():
        with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerow(
                ["project_id", "local_path", "source_url", "source_id", "source_date", "title"])
    out = results / "DOCUMENT_REVIEW"
    summary = build(candidates, manifest, out)
    current = ids(candidates)
    prior = ids(results / INVESTIGATIONS)
    summary.update(current_candidates=len(current),
                   investigations_matched=len(current & prior),
                   investigations_unmatched=len(current - prior),
                   live_document_manifest_count=summary["documents"],
                   production_database_modified=False)
    # Standalone operations landing page; no rewriting the V8 dashboard.
    target = results / "GTA_RADAR_DOCUMENT_OPERATIONS.html"
    page = """<!doctype html><html><head><meta charset='utf-8'>
<title>GTA Radar | Document Intelligence</title></head><body>
<h1>GTA Radar — document intelligence</h1>
<p>This review does not modify V8 collection, investigation results or paid AI.
Document evidence remains UNVERIFIED until manually checked.</p>
<ul>
<li>Current candidates: {c}</li>
<li>With V8 investigation ID: {m}</li>
<li>Source documents processed: {d}</li>
<li>Document mentions for review: {n}</li>
<li>Possible identity links requiring review: {l}</li>
<li>Sale-ready leads established by this module: 0</li>
</ul><p><a href="DOCUMENT_REVIEW/DOCUMENT_INTELLIGENCE_REVIEW.html">Open evidence review</a></p>
<p>Document manifest: DOCUMENT_SOURCE_MANIFEST.csv (relative document paths are
resolved from GTA_RADAR_RESULTS). No PDFs are parsed directly.</p></body></html>"""
    target.write_text(page.format(c=summary["current_candidates"],
                                  m=summary["investigations_matched"],
                                  d=summary["documents"],n=summary["mentions"],
                                  l=summary["identity_links_for_review"]),encoding="utf-8")
    (out / "V8_BRIDGE_SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(bridge(a.results),indent=2))


if __name__ == "__main__":
    main()
