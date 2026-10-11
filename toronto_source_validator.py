"""Non-destructive Toronto CKAN candidate schema validator.

Reads prioritized unconfigured datasets from toronto_gap_queue.csv.
Queries only Toronto's CKAN metadata and at most ONE sample record per DataStore resource;
persists field names, never the record's values. Does not enable any feed.
Run: python toronto_source_validator.py [--force]
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
API = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action'
FAMILIES = ('construction_development', 'procurement_finance',
            'business_licensing', 'infrastructure_transport',
            'council_governance', 'land_property')
FORMATS = ('CSV', 'JSON', 'GEOJSON', 'ZIP', 'XLSX', 'XLS')


def choose_candidates(queue, limit=8):
    """Represent different commercial source families before filling by score."""
    ordered = sorted(queue, key=lambda r: (-int(r.get('priority_score') or 0),
                                           str(r.get('package_id') or '')))
    selected = []
    seen = set()
    for family in FAMILIES:
        for row in ordered:
            pid = row.get('package_id')
            if pid and pid not in seen and family in (row.get('priority_families') or '').split(','):
                selected.append(row)
                seen.add(pid)
                break
            if len(selected) >= limit:
                break
    for row in ordered:
        pid = row.get('package_id')
        if pid and pid not in seen and len(selected) < limit:
            selected.append(row)
            seen.add(pid)
    return selected[:limit]


def check_package(session, candidate):
    pid = str(candidate.get('package_id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{5,100}', pid):
        raise ValueError('Invalid CKAN package identifier')
    response = session.get(API + '/package_show', params={'id': pid}, timeout=(10, 45))
    response.raise_for_status()
    body = response.json()
    if not body.get('success') or not isinstance(body.get('result'), dict):
        raise ValueError('CKAN package metadata unavailable')
    package = body['result']
    if package.get('id') != pid:
        raise ValueError('CKAN returned unexpected package identifier')
    resources = [r for r in package.get('resources', []) if isinstance(r, dict) and r.get('id')]
    resources.sort(key=lambda r: (FORMATS.index(str(r.get('format') or '').upper())
                                  if str(r.get('format') or '').upper() in FORMATS else len(FORMATS),
                                  0 if r.get('datastore_active') else 1))
    selected = resources[0] if resources else {}
    fields = []
    schema_status = 'NO_RESOURCE' if not selected else 'METADATA_ONLY'
    if selected.get('datastore_active'):
        try:
            result = session.get(API + '/datastore_search',
                                 params={'resource_id': selected['id'], 'limit': 1},
                                 timeout=(10, 45))
            result.raise_for_status()
            data = result.json()
            if data.get('success') and isinstance(data.get('result'), dict):
                fields = [f.get('id') for f in data['result'].get('fields', [])
                          if isinstance(f, dict) and f.get('id')]
                schema_status = 'DATASTORE_FIELDS_OBSERVED' if fields else 'DATASTORE_EMPTY_FIELDS'
            else:
                schema_status = 'DATASTORE_PROBE_UNAVAILABLE'
        except (requests.RequestException, ValueError, TypeError):
            schema_status = 'DATASTORE_PROBE_UNAVAILABLE'
    return {
        'package_id': pid, 'title': package.get('title', ''),
        'publisher': (package.get('organization') or {}).get('title', ''),
        'source_page': 'https://open.toronto.ca/dataset/' + str(package.get('name') or '') + '/',
        'licence_id': package.get('license_id', ''),
        'resource_id': selected.get('id', ''),
        'resource_name': selected.get('name', ''),
        'format': selected.get('format', ''),
        'resource_count': len(resources),
        'datastore_active': bool(selected.get('datastore_active')),
        'schema_status': schema_status,
        'field_names': fields,
        'note': 'Field names are discovery evidence; no uniqueness, completeness, commercial relevance or licence conclusion made.',
    }


def should_run(existing_path, catalogue_date):
    if not existing_path.is_file():
        return True
    try:
        old = json.loads(existing_path.read_text(encoding='utf-8'))
        return old.get('catalog_observed_at') != catalogue_date
    except (OSError, ValueError, TypeError):
        return True


def run(*, force=False):
    catalogue = json.loads((DATA / 'toronto_catalog_inventory.json').read_text(encoding='utf-8'))
    stamp = catalogue['observed_at']
    destination = DATA / 'toronto_candidate_validation.json'
    if not force and not should_run(destination, stamp):
        print('Toronto source schema validation: no new catalogue scan; skipped')
        return
    with (DATA / 'toronto_gap_queue.csv').open(encoding='utf-8', newline='') as stream:
        candidates = choose_candidates(list(csv.DictReader(stream)))
    session = requests.Session()
    results = []
    for candidate in candidates:
        try:
            row = check_package(session, candidate)
        except (requests.RequestException, ValueError, TypeError) as error:
            row = {'package_id': candidate.get('package_id', ''),
                   'title': candidate.get('title', ''),
                   'schema_status': 'ERROR',
                   'note': type(error).__name__ + ': ' + str(error)[:250],
                   'field_names': []}
        results.append(row)
    output = {
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'catalog_observed_at': stamp,
        'candidate_count': len(results),
        'results': results,
        'notice': 'Metadata/schema preview only; no full records ingested, no supplier identities confirmed, no source automatically enabled.',
    }
    text = json.dumps(output, indent=2, ensure_ascii=False)
    temporary = destination.with_suffix('.json.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(destination)
    print('Toronto schema validation:', len(results), 'priority candidates checked;',
          sum(x.get('schema_status') == 'DATASTORE_FIELDS_OBSERVED' for x in results),
          'with observable DataStore field names')


if __name__ == '__main__':
    run(force='--force' in sys.argv[1:])
