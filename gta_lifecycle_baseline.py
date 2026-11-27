"""Load a private analyst baseline for the industrial lifecycle tracker."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

PROJECT_IDS = {f"LC-{index:03d}" for index in range(1, 101)}
BASELINE_FILE = Path(__file__).resolve().parent / "data/lifecycle/baseline.zip"
WORKBOOK = "GTA_Radar_100_Industrial_Projects.xlsx"
MAX_BYTES = 16 * 1024 * 1024


def read_baseline(path):
    """Validate and read an archive without extracting files."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Lifecycle archive exceeds the size limit")
    with ZipFile(path) as archive:
        files = archive.infolist()
        names = {member.filename for member in files}
        if len(files) > 250 or len(names) != len(files) or sum(f.file_size for f in files) > MAX_BYTES:
            raise ValueError("Invalid lifecycle archive member list")
        required = {WORKBOOK, "baseline.json", "investigation_tables.json", "START_HERE.md", "DeepSeek_Method.md"}
        required.update(f"reports/{project_id}.md" for project_id in PROJECT_IDS)
        if not required <= names:
            raise ValueError("Lifecycle archive is missing the baseline, workbook or project reports")
        manifest = json.loads(archive.read("baseline.json"))
        if archive.testzip() is not None:
            raise ValueError("Lifecycle archive has a damaged member")
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported lifecycle baseline schema")
    date.fromisoformat(manifest["reviewed_on"])
    rows = manifest.get("projects", [])
    projects = {row["project_id"]: row for row in rows}
    if len(rows) != len(PROJECT_IDS) or projects.keys() != PROJECT_IDS:
        raise ValueError("Baseline must contain exactly LC-001 through LC-100")
    for row in rows:
        for key in ("name", "search_name", "location", "scope_hint", "lifecycle", "equipment", "timing"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Missing {key} for {row['project_id']}")
    return manifest, projects


def install_baseline(source, destination=BASELINE_FILE):
    """Import an immutable snapshot and activate it using an atomic file replacement."""
    source, destination = Path(source), Path(destination)
    manifest, projects = read_baseline(source)
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    history = destination.parent / "snapshots" / f"{manifest['reviewed_on']}-{digest[:16]}.zip"
    history.parent.mkdir(parents=True, exist_ok=True)
    for target in (history, destination):
        if target.exists() and target.read_bytes() == content:
            continue
        with NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return {"baseline_file": str(destination), "snapshot_file": str(history),
            "baseline_sha256": digest, "baseline_date": manifest["reviewed_on"],
            "baseline_project_count": len(projects)}


def research_context(project, reviewed_on):
    """Send only historical lifecycle context, without contacts or full reports."""
    if not project:
        return {}
    return {"reviewed_on": reviewed_on, **{key: project[key][:450] for key in (
        "lifecycle", "equipment", "timing", "awards") if project.get(key)}}
