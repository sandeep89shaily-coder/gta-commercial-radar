"""Package one manual Radar execution for dated review without altering source records.

No collection, database writes, paid AI, outreach, external requests or scheduling.
An archive of saved outputs is NOT validation of original official source facts.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
import zipfile
from pathlib import Path

EXTENSIONS={".csv",".json",".html",".pdf",".txt"}
FOLDERS={
    "MONDAY_FULL_RADAR",
    "COUNCIL_INTELLIGENCE_REVIEW",
    "INDUSTRIAL_PILOT",
    "COMMERCIAL_ACTIVATION_PILOT",
    "PRIORITY_3_4_ACCEPTANCE_PACK",
    "TORONTO_20_COMMERCIAL_REVIEW",
    "FACILITY_EVIDENCE_REVIEW",
    "TOTAL_INTELLIGENCE_REVIEW",
}
MAX_FILE_BYTES=55_000_000
MAX_TOTAL_BYTES=250_000_000
SOURCE_PREFIX="GTA_RADAR_RESULTS/"
MANIFEST="RUN_ARCHIVE_MANIFEST.json"
REDACT=re.compile(r"(?:password|secret|credential|api[_-]?key|token|private[_-]?key|auth[_-]?cookie)",re.I)


def _source_files(results):
    root=Path(results).resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            rel=path.resolve().relative_to(root)
        except ValueError:
            continue
        parts=rel.parts
        if not parts or len(parts)>7 or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(REDACT.search(part) for part in parts):
            continue
        if any(part.lower() in ("logs","cache","secrets",".git",".venv","venv")
               for part in parts):
            continue
        if len(parts)==1:
            if not (path.name.startswith("GTA_RADAR_") or
                    path.name in ("INSTALLED_COMMIT.json","GTA_RADAR_DISCOVERY_RUN_STATUS.json")):
                continue
        elif parts[0] not in FOLDERS:
            continue
        yield path,rel


def create(results, *, output=None, now=None):
    results=Path(results)
    if not results.is_dir():
        raise FileNotFoundError("MISSING_GTA_RADAR_RESULTS")
    report_file=results/"MONDAY_FULL_RADAR"/"MONDAY_FULL_RADAR_STATUS.json"
    if not report_file.is_file():
        raise ValueError("NO_FULL_INTEGRATED_RUN_MANIFEST")
    status=json.loads(report_file.read_text(encoding="utf-8"))
    if not isinstance(status,dict) or status.get("mode")!="MANUAL_COMPLETE_RADAR_REVIEW":
        raise ValueError("WRONG_RUN_MANIFEST_TYPE")
    instant=now or dt.datetime.now().astimezone()
    stamp=instant.strftime("%Y-%m-%d_%H%M%S")
    outdir=Path(output) if output else results.parent/"GTA_RADAR_EXPORTS"
    outdir.mkdir(parents=True,exist_ok=True)
    destination=outdir/("GTA_RADAR_RESULTS_"+stamp+".zip")
    if destination.exists():
        raise FileExistsError("ARCHIVE_ALREADY_EXISTS:"+str(destination))
    collected=[]
    skipped=[]
    size=0
    for path,relative in _source_files(results):
        file_size=path.stat().st_size
        name=relative.as_posix()
        if file_size>MAX_FILE_BYTES or size+file_size>MAX_TOTAL_BYTES:
            skipped.append({"file":name,"reason":"SIZE_LIMIT"})
            continue
        collected.append((path,name,file_size))
        size+=file_size
    if not collected:
        raise ValueError("NO_REVIEW_OUTPUTS_TO_ARCHIVE")
    execution_passed=(status.get("fresh_collection_verified")
                      and status.get("collection_performed")
                      and not status.get("failed_stages"))
    source_warnings=status.get("optional_source_warnings") or {}
    warning_only=bool(source_warnings.get("optional_failed_stages")
                      or source_warnings.get("blocked_sources"))
    mode=("FRESH_COLLECTION_EXECUTION_WITH_PARTIAL_SOURCES_NOT_VERIFIED"
          if execution_passed and warning_only
          else "FRESH_COLLECTION_EXECUTION_REPORTED_NOT_SOURCE_VERIFICATION"
          if execution_passed else
          "PARTIAL_OR_SAVED_EVIDENCE_ONLY_NOT_FRESH_VERIFIED")
    metadata={
        "archive_type":"GTA_RADAR_SOURCE_OUTPUTS_REVIEW_ONLY",
        "created_at":instant.isoformat(),
        "run_started_utc":status.get("started_utc",""),
        "integrated_run_status":status.get("status","UNKNOWN"),
        "freshness_gate":mode,
        "stage_failures":status.get("failed_stages",[]),
        "optional_source_warnings":source_warnings,
        "accepted_commercial_leads":0,
        "buyer_verified":False,
        "open_supplier_package_verified":False,
        "actual_business_openings_verified":False,
        "file_count":len(collected),
        "excluded_due_to_size":skipped,
        "file_inventory":[],
        "note":"Source CSVs and hash continuity do not independently prove public posting dates or buyer/opening/procurement status. Keep original radar.sqlite and source files untouched.",
    }
    try:
        with zipfile.ZipFile(destination,"x",compression=zipfile.ZIP_DEFLATED,
                             compresslevel=5,allowZip64=True) as archive:
            for path,name,file_size in collected:
                data=path.read_bytes()
                # Recheck size: fail closed on in-progress files, never publish
                # an inconsistent package as a completed manual execution.
                if len(data)!=file_size:
                    raise ValueError("SOURCE_FILE_CHANGED_DURING_ARCHIVE:"+name)
                archive.writestr(SOURCE_PREFIX+name,data)
                metadata["file_inventory"].append({
                    "path":SOURCE_PREFIX+name,"bytes":len(data),
                    "sha256":hashlib.sha256(data).hexdigest()})
            archive.writestr(MANIFEST,json.dumps(metadata,indent=2))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"archive":str(destination),"file_count":len(collected),
            "freshness_gate":mode,"source_bytes":size,
            "excluded_due_to_size":len(skipped),
            "buyer_verified":False,"actual_opening_verified":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    print(json.dumps(create(args.results,output=args.output),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
