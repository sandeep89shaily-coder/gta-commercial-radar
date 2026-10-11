"""Toronto feed coverage and collector-gap report. No remote calls or DB writes.

Inputs: Toronto CKAN inventory, configured sources, latest poll status CSV.
Outputs: data/toronto_department_coverage.html, data/toronto_gap_queue.csv.
"""
from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
SCORE = {
    'construction_development': 100,
    'procurement_finance': 95,
    'business_licensing': 90,
    'infrastructure_transport': 85,
    'council_governance': 80,
    'land_property': 75,
}
PORTALS = [
    ('Development Review', 'Application Information Centre', 'planning',
     'https://www.toronto.ca/city-government/planning-development/application-information-centre/'),
    ('City Clerk', 'Council and committees (TMMIS)', 'council',
     'https://secure.toronto.ca/council/'),
    ('Purchasing & Finance', 'Toronto Bids / SAP Ariba', 'procurement',
     'https://www.toronto.ca/business-economy/doing-business-with-the-city/understanding-the-procurement-process/'),
]


def read_poll_status(path):
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return {row['source_id']: row for row in csv.DictReader(stream)
                if row.get('source_id')}


def priority(row):
    families = str(row.get('priority_families') or '').split(',')
    return max((SCORE.get(x, 0) for x in families), default=0)


def candidates(rows):
    """An unconfigured package is an investigation candidate, not an ingestible feed."""
    out = []
    for row in rows:
        score = priority(row)
        if not score or row.get('collector_alignment') == 'EXACT_CONFIGURED':
            continue
        x = {k: str(row.get(k) or '') for k in
             ('package_id', 'title', 'organization', 'url', 'resource_count',
              'resource_formats', 'resource_ids', 'priority_families',
              'collector_alignment', 'possible_query_matches', 'licence_id')}
        x['priority_score'] = str(score)
        x['next_action'] = ('Confirm that title-search collector targets this exact dataset'
                            if row.get('collector_alignment') == 'TITLE_SEARCH_POSSIBLE'
                            else 'Validate schema, record IDs, publication cadence and licence before enabling')
        out.append(x)
    return sorted(out, key=lambda r: (-int(r['priority_score']),
                                      r['organization'].lower(), r['title'].lower()))


def summarize(packages, sources, status):
    toronto = [s for s in sources if str(s.get('jurisdiction') or '').lower() == 'toronto']
    represented = set()
    for p in packages:
        represented.update(filter(None, str(p.get('configured_exact_ids') or '').split(',')))
    departments = Counter((p.get('organization') or 'Unassigned')
                          for p in packages)
    high_value = Counter()
    for p in packages:
        for family in filter(None, str(p.get('priority_families') or '').split(',')):
            high_value[family] += 1
    feeds = [{
        'id': s['id'],
        'name': s.get('name', s['id']),
        'collector': s.get('collector', ''),
        'enabled': bool(s.get('enabled')),
        'mode': s.get('mode', ''),
        'catalog_match': 'EXACT_CONFIGURED' if s['id'] in represented
                         else 'NON_CKAN_OR_UNRESOLVED',
        'poll_health': status.get(s['id'], {}).get('poll_health', 'NOT_VERIFIED'),
        'last_run': status.get(s['id'], {}).get('last_run', ''),
        'current_count': status.get(s['id'], {}).get('current_count', ''),
    } for s in toronto]
    return {'published_packages': len(packages), 'publishing_divisions': dict(departments),
            'families': dict(high_value), 'configured_feeds': feeds,
            'exact_matched_feeds': len(represented & {s['id'] for s in toronto}),
            'priority_gaps': candidates(packages)}


def render(report, observed_at):
    esc = lambda value: html.escape(str(value if value is not None else ''), quote=True)
    counts = ''.join('<tr><td>%s</td><td>%s</td></tr>' % (esc(k), esc(v))
                     for k, v in sorted(report['publishing_divisions'].items(),
                                        key=lambda kv: (-kv[1], kv[0])))
    feeds = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
                    (esc(f['name']), esc(f['collector']), esc(f['mode']),
                     esc('enabled' if f['enabled'] else 'disabled'),
                     esc(f['catalog_match']), esc(f['poll_health']))
                    for f in report['configured_feeds'])
    gaps = ''.join('<tr><td>%s</td><td>%s</td><td><a href="%s" rel="noopener noreferrer">%s</a></td><td>%s</td><td>%s</td></tr>' %
                   (esc(g['priority_score']), esc(g['organization']), esc(g['url']),
                    esc(g['title']), esc(g['resource_formats']), esc(g['next_action']))
                   for g in report['priority_gaps'][:100])
    portals = ''.join('<tr><td>%s</td><td><a href="%s">%s</a></td><td>%s</td></tr>' %
                      (esc(div), esc(url), esc(name), esc('Separate portal; machine access and coverage must be verified'))
                      for div, name, family, url in PORTALS)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Toronto — Municipal Source Coverage</title><style>
body{{font:15px Segoe UI,Arial,sans-serif;color:#253344;max-width:1200px;margin:30px auto;padding:0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:14px 0 24px}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
th{{background:#edf2f6}}.note{{background:#f1f4f7;padding:14px;border-radius:8px}}
</style></head><body>
<h1>Toronto — Department and Source Coverage</h1>
<p>Catalogued {esc(observed_at)} · {report['published_packages']} CKAN packages ·
{len(report['configured_feeds'])} Toronto feed configurations · {len(report['priority_gaps'])} priority gap candidates</p>
<p class="note">Coverage states are deliberately conservative: EXACT_CONFIGURED confirms
a code-level dataset identity, not that data was successfully downloaded.
NOT_VERIFIED means local poll status was not available. CKAN does not include all City portals.
Unconfigured datasets are research leads, not verified usable feeds. No deletions or new business events inferred.</p>
<h2>Configured Toronto feeds and local poll status</h2>
<table><tr><th>Feed</th><th>Adapter</th><th>Mode</th><th>Config</th><th>Catalogue identity</th><th>Latest poll</th></tr>{feeds}</table>
<h2>High-priority missing or unconfirmed CKAN datasets</h2>
<p>Top 100 by commercial research relevance; full queue: toronto_gap_queue.csv.</p>
<table><tr><th>Score</th><th>Publisher</th><th>Dataset</th><th>Formats</th><th>Validation task</th></tr>{gaps}</table>
<h2>Toronto publisher / division inventory</h2>
<table><tr><th>Publishing organization</th><th>Datasets</th></tr>{counts}</table>
<h2>Key public portals outside the CKAN feed audit</h2>
<table><tr><th>Function</th><th>Official portal</th><th>State</th></tr>{portals}</table>
</body></html>"""


def run():
    inventory_path = DATA / 'toronto_catalog_inventory.json'
    if not inventory_path.is_file():
        raise RuntimeError('Toronto CKAN inventory missing; run toronto_catalog_audit.py first')
    source = json.loads(inventory_path.read_text(encoding='utf-8'))
    packages = source['packages']
    if len(packages) != source['package_count']:
        raise RuntimeError('Incomplete Toronto inventory; report not replaced')
    sources = json.loads((ROOT / 'config/sources.json').read_text(encoding='utf-8'))
    state = read_poll_status(DATA / 'source_status.csv')
    report = summarize(packages, sources, state)
    queue = report['priority_gaps']
    keys = ['priority_score', 'organization', 'title', 'url', 'package_id',
            'resource_count', 'resource_formats', 'resource_ids', 'priority_families',
            'collector_alignment', 'possible_query_matches', 'licence_id', 'next_action']
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=keys)
    writer.writeheader()
    writer.writerows(queue)
    outputs = [('toronto_gap_queue.csv', buffer.getvalue()),
               ('toronto_department_coverage.html', render(report, source['observed_at']))]
    for name, value in outputs:
        path = DATA / name
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(value, encoding='utf-8')
        tmp.replace(path)
    print('Toronto coverage report:', len(report['configured_feeds']), 'configured,',
          len(queue), 'priority candidates. Output:', DATA / 'toronto_department_coverage.html')


if __name__ == '__main__':
    run()
