"""Bounded official HTML capture from existing V8 candidates, review only.

Only allow-listed official HTTPS URLs already present in a candidate's evidence
fields are fetched. Enforces pilot_evidence DNS/robots/no-redirect protections.
No search engine, no PDFs, no AI, no database or scheduler modifications.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from pilot_evidence import public_official_url, fetch_official_page

COLS = ["project_id","local_path","source_url","source_id","source_date","title"]
AUDIT = ["project_id","source_url","status","reason"]
FIELDS = ("official_record_url","record_source_url","evidence_url","source_evidence_urls")


def scan(results, limit=6, fetch=False, fetcher=None):
    results = Path(results).resolve()
    source = results / "CANDIDATES_V4_ALL_REVIEW_ONLY.csv"
    if not source.is_file():
        raise FileNotFoundError(str(source))
    with source.open(encoding="utf-8-sig",newline="") as f:
        candidates = list(csv.DictReader(f))
    manifest = results / "DOCUMENT_SOURCE_MANIFEST.csv"
    existing = []
    if manifest.exists():
        with manifest.open(encoding="utf-8-sig",newline="") as f:
            existing = list(csv.DictReader(f))
    seen = {(r.get("project_id",""),r.get("source_url","")) for r in existing}
    audit, added = [], []
    attempted_domains = set()
    blocked_hosts = {}
    selected_urls = set()
    accepted = 0
    if fetch and fetcher is None:
        import requests
        session = requests.Session()
        session.trust_env = False
        session.headers["User-Agent"] = "GTA Radar official evidence review/1.0"
        fetcher = lambda url: fetch_official_page(url,session)
    # Diversify the first bounded batch across cities/sources rather than
    # allowing the first six Brampton records to consume the whole budget.
    candidates.sort(key=lambda r: (str(r.get("city","")).lower(), str(r.get("project_id",""))))
    candidate_groups = {}
    for row in candidates:
        candidate_groups.setdefault(str(row.get("city","")).strip().lower(),[]).append(row)
    ordered = []
    while any(candidate_groups.values()):
        for city in list(candidate_groups):
            if candidate_groups[city]:
                ordered.append(candidate_groups[city].pop(0))
    for row in ordered:
        pid = (row.get("project_id") or "").strip()
        if not pid:
            continue
        urls = []
        for field in FIELDS:
            for candidate in str(row.get(field) or "").split(" | "):
                url = public_official_url(candidate.strip())
                if url and url not in urls:
                    urls.append(url)
        for url in urls:
            if (pid,url) in seen or url in selected_urls:
                continue
            if accepted >= max(0,limit):
                break
            selected_urls.add(url)
            accepted += 1
            domain = urlparse(url).hostname or "unknown"
            attempted_domains.add(domain)
            if domain in blocked_hosts:
                audit.append(dict(project_id=pid,source_url=url,status="SKIPPED",reason="Host previously blocked: "+blocked_hosts[domain]))
                continue
            if not fetch:
                audit.append(dict(project_id=pid,source_url=url,status="DRY_RUN",reason="No network request"))
                continue
            body, error = fetcher(url)
            if error or not body.strip():
                reason = error or "empty page"
                if reason in ("robots policy unavailable", "robots disallows page", "host is not publicly resolvable"):
                    blocked_hosts[domain] = reason
                audit.append(dict(project_id=pid,source_url=url,status="SKIPPED",reason=reason))
                print("[DOCUMENT FETCH FAILED] " + domain + " | " + reason[:220], flush=True)
                continue
            # Never treat today's retrieval date as the publisher's source date.
            digest = hashlib.sha256((pid+"\n"+url).encode()).hexdigest()[:24]
            relative = "DOCUMENT_REVIEW/source_text/" + digest + ".txt"
            destination = results / relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(body[:200000],encoding="utf-8")
            entry = dict(project_id=pid,local_path=relative,source_url=url,
                         source_id=row.get("source_id",""),source_date="",
                         title="Official linked source — publisher date unverified")
            added.append(entry)
            seen.add((pid,url))
            print("[DOCUMENT CAPTURED] " + domain + " | " + pid[:80], flush=True)
            audit.append(dict(project_id=pid,source_url=url,status="CAPTURED",
                              reason="HTML text; source date and relevance unverified"))
    if added:
        with manifest.open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=COLS,extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing+added)
    out = results / "DOCUMENT_REVIEW"
    out.mkdir(parents=True,exist_ok=True)
    with (out / "OFFICIAL_DOCUMENT_FETCH_AUDIT.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=AUDIT)
        writer.writeheader()
        writer.writerows(audit)
    print("[DOCUMENT AUDIT] " + str((out / "OFFICIAL_DOCUMENT_FETCH_AUDIT.csv").resolve()), flush=True)
    if accepted == 0:
        print("[DOCUMENT INFO] No eligible direct official links in candidate fields.", flush=True)
    return dict(distinct_domains_checked=len(attempted_domains),eligible_checked=accepted,captured=len(added),failures=sum(a["status"]=="SKIPPED" for a in audit),
                paid_ai_calls=0,mode="FETCH" if fetch else "DRY_RUN")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",type=Path,required=True)
    p.add_argument("--max-pages",type=int,default=6)
    p.add_argument("--fetch",action="store_true",help="Explicitly enable public official HTML requests")
    a=p.parse_args()
    print(json.dumps(scan(a.results,a.max_pages,a.fetch),indent=2))


if __name__=="__main__":
    main()
