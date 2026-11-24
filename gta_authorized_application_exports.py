"""Opt-in, offline municipal CSV import for permitted City exports.

No endpoints are fetched or bypassed here. Operators must supply official CSV
bytes plus a SHA-matched provenance manifest confirming permitted use.
Unknown/missing file IDs never become application records. Original publication
dates and current citywide coverage are never inferred from local imports.
"""
import csv
import io
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from gta_arcgis_hub_exports import csv_date

CITIES = ("Burlington", "Vaughan", "Kitchener", "Brampton", "Mississauga")
MAX_SIZE = 30_000_000
OUTPUT = "GTA_RADAR_AUTHORIZED_EXPORT_IMPORT_STATUS.json"
KITCHENER_GEOHUB = "https://open-kitchenergis.opendata.arcgis.com/datasets/KitchenerGIS::planning-applications-active"
KITCHENER_LICENCE = "https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data-licence/"
KITCHENER_COLUMNS = {
    "application_id": "Application Number",
    "address": "Address",
    "scope": "Application Summary",
    "category": "Application Type",
    "status": "Status",
    "application_date": "In Date",
}

def _official(city, url):
    try:
        p = urlsplit(str(url))
        host = (p.hostname or "").lower()
        allowed = {
            "Kitchener": ("kitchener.ca", "open-kitchenergis.opendata.arcgis.com"),
            "Vaughan": ("vaughan.ca",),
            "Burlington": ("burlington.ca",),
            "Brampton": ("brampton.ca",),
            "Mississauga": ("mississauga.ca",),
        }[city]
        return (p.scheme == "https" and not p.username and not p.password and
                any(host == domain or host.endswith("." + domain)
                    for domain in allowed))
    except (ValueError, KeyError):
        return False

def load(root):
    root = Path(root)
    folder = root / "GTA_RADAR_AUTHORIZED_EXPORTS"
    manifest_path = folder / "manifest.json"
    exported = []
    details = []
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            if manifest_path.stat().st_size > 100_000:
                raise ValueError("OVERSIZE_MANIFEST")
            config = json.loads(manifest_path.read_text(encoding="utf-8"))
            sources = config.get("exports", []) if isinstance(config, dict) else []
            if not isinstance(sources, list) or len(sources) > 5:
                raise ValueError("INVALID_EXPORT_MANIFEST")
        except (ValueError, OSError, UnicodeError):
            sources = []
            details.append({"status": "INVALID_MANIFEST_NO_IMPORT"})
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            city = str(entry.get("city") or "")
            path = folder / (city.lower() + ".csv")
            item = {"city": city, "status": "HELD_INVALID_OR_UNPERMITTED",
                    "application_id_rows": 0}
            details.append(item)
            if (city not in CITIES or not entry.get("permitted_public_export") or
                    not _official(city, entry.get("official_source_url")) or
                    not isinstance(entry.get("columns"), dict) or
                    not path.is_file() or path.is_symlink() or
                    not 0 < path.stat().st_size <= MAX_SIZE):
                continue
            # Both City datasets may be publicly viewable while their terms
            # differ. Do not use an operator-supplied file for commercial
            # intelligence until the dataset-specific reuse authorization is
            # affirmatively documented; a checked checkbox alone is not proof.
            if city in ("Brampton", "Mississauga"):
                licence=str(entry.get("dataset_licence") or "").strip()
                proof=str(entry.get("licence_or_permission_url") or "").strip()
                if (not entry.get("commercial_reuse_permission_confirmed")
                        or not licence or not _official(city,proof)):
                    item["status"]="HELD_DATASET_SPECIFIC_REUSE_NOT_DOCUMENTED"
                    continue
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                item["status"] = "HELD_FILE_HASH_MISMATCH"
                continue
            fields = entry["columns"]
            if not all(fields.get(x) for x in ("application_id", "address", "scope")):
                item["status"] = "HELD_REQUIRED_COLUMN_MAPPING_MISSING"
                continue
            try:
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if not all(fields[x] in (reader.fieldnames or [])
                               for x in ("application_id", "address", "scope")):
                        item["status"] = "HELD_MAPPED_COLUMNS_NOT_IN_FILE"
                        continue
                    accepted = []
                    for n,row in enumerate(reader):
                        if n >= 15000:
                            break
                        ident = str(row.get(fields["application_id"]) or "").strip()
                        address = str(row.get(fields["address"]) or "").strip()
                        scope = str(row.get(fields["scope"]) or row.get(fields.get("category", "")) or "").strip()
                        if not ident or not address or not scope:
                            continue
                        optional = lambda key: str(
                            row.get(fields.get(key) or "") or "").strip()
                        application_date = optional("application_date")
                        if entry["official_source_url"] == KITCHENER_GEOHUB:
                            application_date = csv_date(application_date)
                        accepted.append({
                            "city": city, "application_id": ident[:120],
                            "address": address[:200], "scope": scope[:1200],
                            "status": optional("status")[:120],
                            "applicant": optional("applicant")[:180],
                            "date": application_date[:30],
                            "url": entry["official_source_url"],
                            "source_date_basis":
                                "CITY_APPLICATION_DATE_NOT_FIRST_PUBLICATION",
                        })
                exported.extend(accepted)
                item["application_id_rows"] = len(accepted)
                item["status"] = "PERMITTED_LOCAL_EXPORT_IMPORTED_NOT_LIVE"
            except (OSError, UnicodeError, csv.Error):
                item["status"] = "HELD_CSV_READ_ERROR"
    summary = {
        "status": "OFFLINE_AUTHORIZED_EXPORT_PROVENANCE_ONLY",
        "sources": details, "rows": len(exported),
        "no_network_requests": True,
        "no_verified_original_publication": True,
        "no_verified_citywide_current_coverage": True,
    }
    (root / OUTPUT).write_text(json.dumps(summary, indent=2),
                                encoding="utf-8")
    return exported, summary


def stage_kitchener_export(source, results):
    """Register the City GeoHub's browser-downloaded CSV for the next run."""
    source = Path(source)
    if not 0 < source.stat().st_size <= MAX_SIZE:
        raise ValueError("KITCHENER_EXPORT_SIZE_INVALID")
    content = source.read_bytes()
    with io.StringIO(content.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not set(KITCHENER_COLUMNS.values()).issubset(reader.fieldnames or ()):
            raise ValueError("KITCHENER_GEOHUB_CSV_HEADERS_REQUIRED")
        if not any(
            row["Application Number"] and row["Address"]
            and (row["Application Summary"] or row["Application Type"])
            for row in reader
        ):
            raise ValueError("KITCHENER_EXPORT_HAS_NO_APPLICATION_FILES")

    folder = Path(results) / "GTA_RADAR_AUTHORIZED_EXPORTS"
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    exports = [entry for entry in manifest.get("exports", []) if entry["city"] != "Kitchener"]
    exports.append({
        "city": "Kitchener",
        "official_source_url": KITCHENER_GEOHUB,
        "dataset_licence": "Open Government Licence - The Corporation of the City of Kitchener",
        "licence_or_permission_url": KITCHENER_LICENCE,
        "permitted_public_export": True,
        "commercial_reuse_permission_confirmed": True,
        "sha256": hashlib.sha256(content).hexdigest(),
        "columns": KITCHENER_COLUMNS,
    })
    (folder / "kitchener.csv").write_bytes(content)
    manifest_path.write_text(json.dumps({**manifest, "exports": exports}, indent=2), encoding="utf-8")
    return manifest_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=stage_kitchener_export.__doc__)
    parser.add_argument("--kitchener-csv", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(stage_kitchener_export(args.kitchener_csv, args.results))
