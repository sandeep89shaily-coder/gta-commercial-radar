"""Offline, review-only document-to-project evidence workbench.

Reads existing GTA Radar candidate CSV plus explicitly supplied local document
manifest. Never fetches websites, calls AI, writes the collection database,
changes the scheduler or declares a lead sale-ready.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

FACT_FIELDS = ("project_id", "source_id", "source_url", "source_date",
               "document_title", "document_path", "fact_type", "fact_value",
               "excerpt", "verification_status")
LINK_FIELDS = ("left_project_id", "right_project_id", "link_type", "basis",
               "review_status")
QUEUE_FIELDS = ("project_id", "address", "city", "document_count",
                "evidence_count", "buyer_verified", "supplier_status",
                "sale_ready", "review_reason")
SIGNALS = {
    "planning": r"\\b(?:rezoning|site.plan|official.plan.amendment|pre.consultation)\\b",
    "development": r"\\b(?:industrial.development|warehouse|distribution.centre|commercial.development)\\b",
    "procurement": r"\\b(?:request.for.proposal|request.for.tender|invitation.to.bid)\\b",
    "award_mention": r"\\b(?:contract.awarded|successful.bidder|award.of.contract)\\b",
}
MAX_DOCUMENT = 1_000_000
MAX_EXCERPT = 230


def rows(path):
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, columns, data):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def source_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return value


def normalize(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def load_document(entry, base):
    """Reject manifest path escapes. HTML content is stripped, not executed."""
    relative = str(entry.get("local_path") or "").strip()
    if not relative:
        return "", "missing local_path"
    p = (base / relative).resolve()
    if not p.is_relative_to(base.resolve()) or p.suffix.lower() not in {".txt", ".html", ".htm"}:
        return "", "unsupported or outside manifest directory"
    try:
        if p.stat().st_size > MAX_DOCUMENT:
            return "", "document over limit"
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix.lower() in {".html", ".htm"}:
            text = re.sub(r"(?is)<(script|style)\\b.*?</\\1\\s*>", " ", text)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
            text = html.unescape(text)
        return re.sub(r"\\s+", " ", text).strip(), ""
    except OSError as exc:
        return "", type(exc).__name__


def extract(project_id, doc, text):
    """Regex mentions are leads for review, never verified statements."""
    facts = []
    for typ, pattern in SIGNALS.items():
        for match in list(re.finditer(pattern, text, flags=re.I))[:4]:
            begin = max(0, match.start() - 90)
            end = min(len(text), match.end() + 110)
            facts.append({
                "project_id": project_id,
                "source_id": str(doc.get("source_id") or ""),
                "source_url": source_url(doc.get("source_url")),
                "source_date": str(doc.get("source_date") or ""),
                "document_title": str(doc.get("title") or ""),
                "document_path": str(doc.get("local_path") or ""),
                "fact_type": typ + "_mention",
                "fact_value": match.group(0),
                "excerpt": text[begin:end][:MAX_EXCERPT],
                "verification_status": "UNVERIFIED_TEXT_MENTION",
            })
    return facts


def build(candidates_csv, manifest_csv, output_dir):
    candidates = rows(candidates_csv)
    documents = rows(manifest_csv)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    known = {str(r.get("project_id") or "").strip(): r
             for r in candidates if str(r.get("project_id") or "").strip()}
    facts, audits = [], []
    document_count = defaultdict(int)
    for doc in documents:
        pid = str(doc.get("project_id") or "").strip()
        if pid not in known:
            audits.append({"project_id": pid, "local_path": doc.get("local_path", ""),
                           "status": "SKIPPED", "reason": "project_id not in candidates"})
            continue
        content, problem = load_document(doc, Path(manifest_csv).resolve().parent)
        if problem:
            audits.append({"project_id": pid, "local_path": doc.get("local_path", ""),
                           "status": "SKIPPED", "reason": problem})
            continue
        if not source_url(doc.get("source_url")):
            audits.append({"project_id": pid, "local_path": doc.get("local_path", ""),
                           "status": "REVIEW", "reason": "missing official HTTPS source URL"})
        else:
            audits.append({"project_id": pid, "local_path": doc.get("local_path", ""),
                           "status": "EXTRACTED", "reason": "unverified text mentions only"})
        document_count[pid] += 1
        facts.extend(extract(pid, doc, content))
    links = []
    entries = sorted(known.items())
    for i, (left_id, left) in enumerate(entries):
        for right_id, right in entries[i+1:]:
            city = normalize(left.get("city"))
            other_city = normalize(right.get("city"))
            if not city or city != other_city:
                continue
            id_left = normalize(left.get("official_permit_id") or left.get("application_id"))
            id_right = normalize(right.get("official_permit_id") or right.get("application_id"))
            addr_left = normalize(left.get("address"))
            addr_right = normalize(right.get("address"))
            if id_left and id_left == id_right and normalize(left.get("source_id")) == normalize(right.get("source_id")) and left.get("source_id"):
                kind, basis = "EXACT_SOURCE_APPLICATION_ID", "same city, collector and explicit application ID"
            elif addr_left and addr_left == addr_right:
                kind, basis = "SAME_ADDRESS_REVIEW_ONLY", "same civic address and city; different projects may coexist"
            else:
                continue
            links.append({"left_project_id": left_id, "right_project_id": right_id,
                          "link_type": kind, "basis": basis,
                          "review_status": "HUMAN_REVIEW_REQUIRED"})
    counts = defaultdict(int)
    for f in facts:
        counts[f["project_id"]] += 1
    queue = []
    for pid, row in entries:
        queue.append({"project_id": pid, "address": row.get("address", ""),
                      "city": row.get("city", ""), "document_count": document_count[pid],
                      "evidence_count": counts[pid], "buyer_verified": "NO",
                      "supplier_status": "UNKNOWN", "sale_ready": "NO",
                      "review_reason": "Document mentions do not prove a buyer, unawarded package or right to contact"})
    write_csv(output_dir / "DOCUMENT_EVIDENCE_REVIEW.csv", FACT_FIELDS, facts)
    write_csv(output_dir / "PROJECT_IDENTITY_LINKS_REVIEW.csv", LINK_FIELDS, links)
    write_csv(output_dir / "PROJECT_QUALITY_QUEUE_REVIEW.csv", QUEUE_FIELDS, queue)
    write_csv(output_dir / "DOCUMENT_EXTRACTION_AUDIT.csv",
              ("project_id", "local_path", "status", "reason"), audits)
    body = ["<!doctype html><html><head><meta charset='utf-8'><title>GTA Radar document review</title></head><body>",
            "<h1>GTA Radar — document review only</h1>",
            "<p>Text matches are not validated projects, buyers, awards or sale-ready opportunities. No AI calls.</p>",
            "<table border='1'><tr><th>Project</th><th>Location</th><th>Documents</th><th>Mentions</th><th>Sale ready</th></tr>"]
    for item in queue:
        cells = [item["project_id"], (item["address"] + ", " + item["city"]).strip(", "),
                 str(item["document_count"]), str(item["evidence_count"]), "NO"]
        body.append("<tr>" + "".join("<td>" + html.escape(value) + "</td>" for value in cells) + "</tr>")
    body.append("</table></body></html>")
    (output_dir / "DOCUMENT_INTELLIGENCE_REVIEW.html").write_text("\n".join(body), encoding="utf-8")
    return {"projects": len(queue), "documents": sum(document_count.values()),
            "mentions": len(facts), "identity_links_for_review": len(links),
            "sale_ready": 0, "ai_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.manifest, args.out), indent=2))


if __name__ == "__main__":
    main()
