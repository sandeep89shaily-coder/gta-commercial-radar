"""Evidence-first commercial lead review. Read-only on existing Radar databases.

A source observation or municipal UPDATED event is not a newly issued permit.
Nothing output by this module is certified as a sale-ready lead.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from commercial_research_policy import INSPECTION, PERMIT, research_route, lead_sector
from official_record_verifier import BY_ID, exact_id, published_query

ROOT = Path(__file__).resolve().parent
OUTPUT_FIELDS = [
    'lane', 'review_priority', 'project_id', 'address', 'city', 'company_name',
    'description', 'source_id', 'source_keys', 'permit_count', 'permit_types',
    'event_date', 'date_basis', 'source_record_date', 'source_record_date_basis',
    'current_source_status', 'source_group', 'record_source_url', 'record_source_url_basis',
    'service_hypotheses', 'review_reason', 'review_status', 'manual_research_url',
    'research_route', 'lead_sector', 'early_signal_stage', 'early_signal_type',
    'first_observed_at', 'pre_permit_verification', 'procurement_status',
]
EXCLUDED_FIELDS = ['source_id', 'source_key', 'address', 'description', 'reason']

COMMERCIAL = re.compile(r'\b(industrial|warehouse|factory|manufactur\w*|distribution (?:centre|center|facility)|logistics|commercial|retail|office|restaurant|food processing|clinic|medical|pharmacy|hotel|hospitality|storefront|shop|shopping|tenant fit[ -]?out|data cent(?:re|er)|business licen[cs]e|automotive|dealership|self[ -]storage|school|daycare)\b', re.I)
SMALL_RESIDENTIAL = re.compile(r'\b(sfd|single[ -]family|single[ -]detached|semi[ -]detached|detached dwelling|two[ -]unit dwelling|secondary (?:suite|unit|apartment)|second (?:suite|unit)|basement (?:apartment|suite)|garden suite|laneway (?:suite|house)|rear yard suite|duplex|triplex|fourplex|houseplex|townhouse unit|private (?:residence|garage)|(?:2|two)[ -]storey detached dwelling)\b', re.I)
RESIDENTIAL_LED = re.compile(r'\b(residential (?:building|tower|development|infill|high[ -]rise|apartment)|rental apartment|apartment (?:building|tower)|condominium (?:building|tower)|condo(?:minium)? tower|dwelling units|affordable housing units|purpose[ -]built rental|residential units|residential buildings|multi[ -]?residential|\d+[- ]storey (?:infill )?(?:rental |residential |condominium )?(?:apartment|residential|rental)|mixed[ -]use residential|residential\/commercial)\b', re.I)
INDEPENDENT_COMMERCIAL = re.compile(r'\b((?:restaurant|clinic|retail|office|warehouse|industrial|pharmacy|shop|food processing) (?:tenant )?fit[ -]?out|tenant fit[ -]?out (?:for |of )?(?:restaurant|office|shop|retail|clinic)|interior alterations? (?:for|of|to) (?:a |an |the )?(?:restaurant|retail|office|clinic|pharmacy|industrial)|new (?:restaurant|shop|office|warehouse|factory))\b', re.I)
NO_WORK = re.compile(r'\b(as[ -]built documentation|no (?:new )?(?:construction|alteration|repair|work|renovation|addition|demolition|change of use) (?:is )?(?:proposed|planned)|documentation only|administrative correction only)\b', re.I)
ACTION = re.compile(r'\b(construction|construct\w*|renovat\w*|alterat\w*|installation|retrofit|expansion|fit[ -]?out|new building|addition|new business|new restaurant|change of use|occupancy|replacement)\b', re.I)
TORONTO_PERMIT = re.compile(r'^\s*(\d{2})\s+(\d{5,8})\s+([A-Z]{2,4})\s*\|\s*\d+\s*$', re.I)
PLANNING = re.compile(r'development_application|planning_application|site_plan', re.I)
SERVICES = [
    ('Commercial HVAC', re.compile(r'\b(hvac|heating|ventilation|air conditioning|chiller|boiler|mechanical)\b', re.I)),
    ('Plumbing services', re.compile(r'\b(plumbing|washroom|drainage|water supply|sewer)\b', re.I)),
    ('Fire protection', re.compile(r'\b(sprinkler|fire alarm|fire protection|suppression)\b', re.I)),
    ('Electrical services', re.compile(r'\b(electrical|wiring|power distribution|lighting)\b', re.I)),
    ('Security/access control', re.compile(r'\b(security|access control|surveillance|alarm system)\b', re.I)),
]
LANE_ORDER = {'EARLY_SIGNAL_WATCH': 0, 'PERMIT_REVIEW': 1,
              'BUSINESS_REVIEW': 2, 'PLANNING_WATCH': 3,
              'ENVIRONMENT_WATCH': 4, 'SOURCE_UPDATE_WATCH': 5,
              'OTHER_WATCH': 6, 'ENRICHMENT_ONLY': 7}


def safe_url(value):
    try:
        value = str(value or '').strip()
        p = urlparse(value)
        return value if p.scheme in ('https', 'http') and p.hostname and not p.username and not p.password else ''
    except ValueError:
        return ''


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def classify(row):
    d = str(row.get('description') or '')
    sid = str(row.get('source_id') or '')
    group = str(row.get('source_group') or '')
    if NO_WORK.search(d):
        return 'EXCLUDE_NO_WORK', 'Documentation or explicit statement that no new work is proposed'
    if SMALL_RESIDENTIAL.search(d) and not INDEPENDENT_COMMERCIAL.search(d):
        return 'EXCLUDE_SMALL_RESIDENTIAL', 'Standalone small-dwelling or garden-suite work'
    if RESIDENTIAL_LED.search(d) and not INDEPENDENT_COMMERCIAL.search(d):
        return 'EXCLUDE_RESIDENTIAL_LED', 'Residential-led construction is outside commercial-only lead scope'
    if not COMMERCIAL.search(d) and not ('licen' in sid.lower() and row.get('company_name')):
        return 'EXCLUDE_NO_COMMERCIAL', 'No specific commercial activity established'
    if group == 'EARLY_PILOT_OBSERVED_CHANGE':
        return 'EARLY_SIGNAL_WATCH', ('Upstream commercial signal for pre-permit investigation; '
                                      'permit issuance, public posting date and purchasing stage unverified')
    if INSPECTION.search(sid):
        return 'ENRICHMENT_ONLY', 'Routine health inspection is company context, not a new commercial purchasing trigger'
    if PLANNING.search(sid):
        return 'PLANNING_WATCH', 'Planning-stage activity; no issued permit or purchasing event confirmed'
    if PERMIT.search(sid) or 'building_permit' in sid:
        return 'PERMIT_REVIEW', 'Commercial permit work, not proof of permit issuance or purchasing intent'
    if 'environmental_instrument' in sid:
        return 'ENVIRONMENT_WATCH', 'Environmental regulatory proposal; supplier demand not established'
    if 'licen' in sid.lower() or group == 'BUSINESS_DISCOVERY':
        kind=research_route({'source_id':sid,'description':d,'lane':'BUSINESS_REVIEW'})
        if kind=='ENRICHMENT_ONLY':
            return 'ENRICHMENT_ONLY', 'Existing business record with no evidenced opening or expansion'
        return 'BUSINESS_REVIEW', 'Commercial business-opening or expansion record; independently verify timing'
    if group in ('MUNICIPAL_CHANGE', 'PEEL_PROJECT') or 'CHANGE_DETECTED' in str(row.get('event_date_basis') or ''):
        return 'SOURCE_UPDATE_WATCH', 'A detected record update is not a new permit or opening'
    return 'OTHER_WATCH', 'Commercial reference with insufficient evidence of actionable activity'


def group_key(r):
    sid = str(r.get('source_id') or '')
    key = str(r.get('source_key') or r.get('candidate_id') or r.get('opportunity_id') or '')
    match = TORONTO_PERMIT.fullmatch(key) if sid == 'toronto_active_building_permits' else None
    if match:
        return sid + ':' + match.group(1) + ' ' + match.group(2)
    # Never merge unrelated companies merely because they share a street address.
    return sid + ':' + key


def permit_type(r):
    m = TORONTO_PERMIT.fullmatch(str(r.get('source_key') or ''))
    return m.group(3).upper() if m else ''


def load_metadata(db_path, rows):
    """Read only records already in SQLite; missing DB is supported for previews."""
    p = Path(db_path)
    if not p.is_file():
        return {}
    result = {}
    try:
        with closing(sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            for sid, key in {(str(r.get('source_id') or ''), str(r.get('source_key') or '')) for r in rows}:
                found = db.execute('SELECT source_date,normalized_json FROM records_current WHERE source_id=? AND record_key=? AND active=1', (sid, key)).fetchone()
                if not found:
                    continue
                try:
                    info = json.loads(found[1] or '{}')
                except (TypeError, ValueError):
                    info = {}
                result[(sid, key)] = {'source_date': found[0] or '', 'status': info.get('status') or '', 'evidence_url': info.get('evidence_url') or ''}
    except sqlite3.Error:
        return {}  # Existing collector/DB data must never be altered by selection.
    return result


def service_hypotheses(desc, kinds):
    found = [name for name, pattern in SERVICES if pattern.search(desc)]
    if 'HVA' in kinds and 'Commercial HVAC' not in found:
        found.append('Commercial HVAC')
    if 'PLB' in kinds and 'Plumbing services' not in found:
        found.append('Plumbing services')
    if 'FSU' in kinds and 'Fire protection' not in found:
        found.append('Fire protection')
    return '; '.join(found) or 'Needs industry-specific research'


def summarize(members, metadata):
    # Prefer the building permit's full description to mechanical trade fragments.
    chosen = sorted(members, key=lambda r: (permit_type(r) == 'BLD', len(r.get('description') or '')), reverse=True)[0]
    sid = str(chosen.get('source_id') or '')
    key = str(chosen.get('source_key') or '')
    lane, reason = classify(chosen)
    group = str(chosen.get('source_group') or '')
    kinds = sorted({permit_type(x) for x in members if permit_type(x)})
    fulltext = ' '.join(dict.fromkeys((x.get('description') or '') for x in members))
    # A related trade permit cannot rescue an excluded residential/no-work project.
    for x in members:
        candidate_lane, why = classify(x)
        if candidate_lane.startswith('EXCLUDE') and (candidate_lane in ('EXCLUDE_NO_WORK', 'EXCLUDE_RESIDENTIAL_LED', 'EXCLUDE_SMALL_RESIDENTIAL')):
            lane, reason = candidate_lane, why
            break
    meta = next((metadata.get((str(x.get('source_id') or ''), str(x.get('source_key') or ''))) for x in members if metadata.get((str(x.get('source_id') or ''), str(x.get('source_key') or '')))), {})
    direct_urls = [safe_url(x.get('evidence_url') or x.get('source_url')) for x in members]
    direct = next((x for x in direct_urls if x), '') or safe_url(meta.get('evidence_url'))
    direct_basis='PUBLISHED_SOURCE_EVIDENCE_FIELD' if direct else ''
    if not direct and meta:
        # Construct an EXACT official lookup, never a generic address-search
        # page. The clickable lookup is NOT proof the current record remains
        # live until verified separately against the government endpoint.
        single=next((x for x in members if metadata.get((
                    str(x.get('source_id') or ''),str(x.get('source_key') or '')))),None)
        if single:
            official_source=BY_ID.get(sid,{})
            match=exact_id({'source_keys':single.get('source_key','')},official_source)
            direct=published_query(official_source,match) if match else ''
            if direct:direct_basis='EXACT_ID_OFFICIAL_LOOKUP_UNCHECKED'
    company = next((str(x.get('company_name') or '').strip() for x in members if str(x.get('company_name') or '').strip().upper() not in ('', 'UNKNOWN', 'NONE')), 'UNKNOWN')
    score = {'EARLY_SIGNAL_WATCH': 38, 'PERMIT_REVIEW': 70, 'BUSINESS_REVIEW': 55, 'PLANNING_WATCH': 35, 'ENVIRONMENT_WATCH':25,'SOURCE_UPDATE_WATCH': 12, 'OTHER_WATCH': 8}.get(lane, 0)
    if ACTION.search(fulltext) and lane in ('PERMIT_REVIEW', 'BUSINESS_REVIEW'):
        score += 10
    if company != 'UNKNOWN':
        score += 5
    if direct:
        score += 7
    if kinds and len(kinds) > 1:
        score += 3
    # Change timestamps are never actionable event dates; cap review priority.
    if lane == 'SOURCE_UPDATE_WATCH':
        score = min(score, 20)
    address = chosen.get('address') or ''
    city = chosen.get('city') or ''
    search = ' '.join(x for x in (f'"{address}"' if address else '', city, company if company != 'UNKNOWN' else '', key) if x)
    raw_basis = str(chosen.get('event_date_basis') or chosen.get('date_basis') or '')
    date_basis = ('RADAR FIRST OBSERVATION — NOT ORIGINAL POSTING DATE OR PERMIT ISSUANCE'
                  if lane == 'EARLY_SIGNAL_WATCH' else
                  'SOURCE RECORD UPDATE OBSERVED — NOT ISSUANCE/OPENING'
                  if group == 'MUNICIPAL_CHANGE' or lane == 'SOURCE_UPDATE_WATCH'
                  else ('PLANNING APPLICATION DATE — VERIFY' if lane == 'PLANNING_WATCH'
                        else ('SOURCE EVENT DATE — NOT VERIFIED ISSUANCE/OPENING' if group == 'MUNICIPAL'
                              else 'REPORTED SOURCE/OBSERVATION DATE — VERIFY')))
    record_date = meta.get('source_date') or chosen.get('source_record_date') or ''
    return {
        'lane': lane, 'review_priority': score, 'project_id': group_key(chosen),
        'address': address, 'city': city, 'company_name': company, 'description': chosen.get('description') or '',
        'source_id': sid, 'source_keys': ' | '.join(dict.fromkeys(str(x.get('source_key') or '') for x in members)),
        'permit_count': 0 if lane == 'EARLY_SIGNAL_WATCH' else len(members), 'permit_types': ', '.join(kinds),
        'event_date': chosen.get('event_date') or '', 'date_basis': date_basis,
        'source_record_date': record_date,
        'source_record_date_basis': ('PILOT REPORTED PLANNING/ACTIVITY DATE — NOT PROVEN PUBLIC POST DATE'
                                     if record_date and lane == 'EARLY_SIGNAL_WATCH' else
                                     'COLLECTOR-PREFERRED DATE FIELD, MAY BE STATUS DATE; NOT CONFIRMED ISSUED DATE'
                                     if record_date else 'NOT AVAILABLE'),
        'current_source_status': meta.get('status') or chosen.get('current_source_status') or '', 'source_group': group,
        'record_source_url': direct, 'record_source_url_basis':direct_basis,
        'service_hypotheses': service_hypotheses(fulltext, kinds),
        'review_reason': reason, 'review_status': 'RESEARCH ONLY — OPERATOR, DATE AND DEMAND UNVERIFIED',
        'manual_research_url': 'https://www.google.com/search?q=' + quote_plus(search[:240]),
        'research_route':research_route({'source_id':sid,'lane':lane,'description':fulltext}),
        'lead_sector':lead_sector({'source_id':sid,'description':fulltext}),
        'early_signal_stage': chosen.get('early_signal_stage') or '',
        'early_signal_type': chosen.get('early_signal_type') or '',
        'first_observed_at': chosen.get('first_observed_at') or '',
        'pre_permit_verification': chosen.get('pre_permit_verification') or
            ('NOT_VERIFIED' if lane == 'EARLY_SIGNAL_WATCH' else ''),
        'procurement_status': chosen.get('procurement_status') or
            ('UNKNOWN' if lane == 'EARLY_SIGNAL_WATCH' else ''),
    }


def write_csv(path, fields, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def render_html(rows, counts):
    e = lambda x: html.escape(str(x or ''), quote=True)
    out = ['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar — V4 Review</title>',
           '<style>body{max-width:1100px;margin:30px auto;font:15px Segoe UI,Arial;background:#f5f6fa;color:#263244;padding:0 14px}',
           'article{background:white;padding:15px;margin:12px 0;border-radius:9px}small{color:#555}a{color:#145da2}</style></head><body>',
           '<h1>GTA Commercial Radar — evidence-first V4 review</h1>',
           '<p><b>These are not verified or sale-ready leads.</b> Municipal record changes are NOT new permits. Missing original source evidence must be researched.</p>',
           '<p>Unique projects retained: ' + str(len(rows)) + ' | Removed records: ' + str(sum(v for k, v in counts.items() if k.startswith('EXCLUDE'))) + '</p>']
    for lane in LANE_ORDER:
        group = [r for r in rows if r['lane'] == lane]
        out.append('<h2>' + e(lane.replace('_', ' ').title()) + ' (' + str(len(group)) + ')</h2>')
        for r in group:
            out.append('<article><b>' + e(r['address'] or r['project_id']) + '</b> — ' + e(r['review_priority']) + '/100'
                       + '<p>' + e(r['description']) + '</p><small>' + e(r['review_reason']) + ' | '
                       + e(r['date_basis']) + ' | Related permits: ' + e(r['permit_count']) + '</small>'
                       + '<p>Possible services to research: ' + e(r['service_hypotheses']) + '</p>')
            if r['record_source_url']:
                out.append('<a href="' + e(r['record_source_url']) + '">Source record link</a> · ')
            out.append('<a href="' + e(r['manual_research_url']) + '">Research project</a></article>')
    out.append('</body></html>')
    return ''.join(out)


def run(input_csv, output_dir, db_path=None):
    source = read_csv(input_csv)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata(db_path or output / 'radar.sqlite', source)
    groups = {}
    seen = set()
    for r in source:
        ident = (r.get('source_id'), r.get('source_key') or r.get('candidate_id') or r.get('opportunity_id'))
        if ident in seen:
            continue
        seen.add(ident)
        groups.setdefault(group_key(r), []).append(r)
    counts = Counter()
    selected, excluded, enriched = [], [], []
    for group in groups.values():
        item = summarize(group, metadata)
        counts[item['lane']] += 1
        if item['lane']=='ENRICHMENT_ONLY' or item['research_route']=='ENRICHMENT_ONLY':
            enriched.append(item)
        elif item['lane'].startswith('EXCLUDE'):
            for record in group:
                excluded.append({'source_id': record.get('source_id'), 'source_key': record.get('source_key'),
                                 'address': record.get('address'), 'description': record.get('description'),
                                 'reason': item['review_reason']})
        else:
            selected.append(item)
    selected.sort(key=lambda r: (LANE_ORDER[r['lane']], -r['review_priority'], r['project_id']))
    write_csv(output / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv', OUTPUT_FIELDS, selected)
    write_csv(output / 'CANDIDATES_V4_ENRICHMENT_ONLY.csv', OUTPUT_FIELDS, enriched)
    write_csv(output / 'CANDIDATES_V4_EXCLUDED_AUDIT.csv', EXCLUDED_FIELDS, excluded)
    write_csv(output / 'CANDIDATES_V4_COUNTS.csv', ['category', 'count'],
              [{'category': k, 'count': v} for k, v in sorted(counts.items())])
    (output / 'commercial_candidates_v4.html').write_text(render_html(selected, counts), encoding='utf-8')
    print('V4:', len(source), 'input records;', len(selected), 'actionable projects for AI;', len(enriched), 'company-enrichment records;', len(excluded), 'records excluded')
    print('By lane:', dict(counts))
    return selected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--db', type=Path)
    args = parser.parse_args()
    run(args.input or args.data_dir / 'opportunities_ALL_REVIEW_ONLY.csv', args.data_dir, args.db)
