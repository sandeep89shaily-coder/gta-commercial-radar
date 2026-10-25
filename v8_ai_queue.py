"""Persistent GTA Radar AI backlog.

All non-excluded V4 candidate projects remain in this queue across 48-hour
source refreshes until substantive DeepSeek analysis finishes. Source-only
analyses are scheduled for later evidence rechecks, not treated as verified.
No independent spending policy: v8_deepseek_native owns the $1 daily ledger.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from commercial_research_policy import research_route, canonical_lane
from official_record_verifier import BY_ID
from opportunity_lifecycle import classify_status

META = ('_queued_on', '_fingerprint')
FINISHED = {'AI_EVIDENCE_REVIEW', 'AI_SOURCE_RECORD_REVIEW'}
CLOSED = re.compile(r'\b(closed|refused|withdrawn|cancelled|canceled|rejected|denied|inactive)\b', re.I)
# Genuine newly observed pre-permit cues precede late permit records.
# This is investigation order, not proof the procurement window is still open.
LANES = {'EARLY_SIGNAL_WATCH':0, 'PLANNING_WATCH':1,
         'BUSINESS_REVIEW':2, 'PERMIT_REVIEW':3, 'ENVIRONMENT_WATCH':4,
         'OTHER_WATCH':5, 'SOURCE_UPDATE_WATCH':6}
SIGNATURE_FIELDS = ('project_id', 'source_id', 'source_keys', 'address',
                    'company_name', 'description', 'current_source_status',
                    'record_source_url', 'permit_types', 'early_signal_stage',
                    'early_signal_type', 'procurement_status')


def fingerprint(row):
    important = {k: str(row.get(k) or '').strip() for k in SIGNATURE_FIELDS}
    return hashlib.sha256(json.dumps(important, sort_keys=True).encode('utf-8')).hexdigest()


def load(path):
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def save(path, rows):
    """Atomic queue checkpoint: never erase old work during daily refresh."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(
        [k for row in rows for k in row] + list(META)))
    if not fields:
        fields = ['project_id', *META]
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def local_attempt_date(old, timezone=None):
    """Interpret old UTC researched_at in LOCAL time, avoiding midnight drift."""
    literal = str(old.get('investigated_local_date') or '')
    if literal:
        try:
            return dt.date.fromisoformat(literal[:10])
        except ValueError:
            pass
    stamp = str(old.get('researched_at') or '').strip()
    if not stamp:
        return None
    try:
        moment = dt.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if moment.tzinfo is not None:
            moment = moment.astimezone(timezone)
        return moment.date()
    except ValueError:
        return None


def days_since(date, now):
    return (now - date).days if date else 100000


def build(current_rows, queued_rows, history, today):
    """Join fresh candidates to retained backlog; never lose aged-out records."""
    combined = {r['project_id']: dict(r) for r in queued_rows
                if r.get('project_id') and research_route(r)!='ENRICHMENT_ONLY'}
    for r in current_rows:
        ident = r.get('project_id')
        if (not ident or research_route(r)=='ENRICHMENT_ONLY'
                or CLOSED.search(str(r.get('current_source_status') or ''))):
            continue
        old = combined.get(ident, {})
        added = dict(old)
        added.update(r)
        added['_queued_on'] = old.get('_queued_on') or today.isoformat()
        added['lane'] = canonical_lane(added)
        added['_fingerprint'] = fingerprint(added)
        combined[ident] = added

    pending = []
    for ident, row in combined.items():
        if (research_route(row)=='ENRICHMENT_ONLY'
                or CLOSED.search(str(row.get('current_source_status') or ''))):
            continue
        row['lane']=canonical_lane(row)
        old = history.get(ident, {})
        same_source = not old.get('input_fingerprint') or old.get('input_fingerprint') == fingerprint(row)
        if (old.get('status') == 'AI_EVIDENCE_REVIEW' and same_source
                and old.get('project_evidence_verified') == 'YES'
                and old.get('project_identity_confidence') in
                    ('EXACT_LIVE_OFFICIAL','EXACT_LOCAL_COLLECTOR','EXACT_ID_ON_PUBLIC_PAGE')):
            continue  # Only project-specific evidence passed under the new rule.
        # Legacy AI_EVIDENCE_REVIEW rows have no strict evidence field; retain
        # and automatically retry them rather than grandfathering directories.
        pending.append(row)
    return pending


REGION_PRIORITY=('Peel','York','Halton','Durham','Hamilton','Waterloo','Niagara','Toronto','Other')

def source_region(row):
    """Only authoritative feed metadata decides region; never scrape it from web."""
    source=BY_ID.get(str(row.get('source_id') or ''),{})
    return str(source.get('region') or 'Other')

def fair_regional_order(ready):
    """Interleave qualified projects by official region; never drop or reprice one.

    Within each region the original research-priority and age ordering remains.
    One per region per round prevents a large Toronto backlog monopolizing the
    shared $1/day AI budget. It does NOT enforce fixed quotas or suppress Toronto.
    """
    if not ready:return []
    bins={}
    for r in ready:
        bins.setdefault(source_region(r),[]).append(r)
    if len(bins)<=1:return ready
    regions=[r for r in REGION_PRIORITY if r in bins]
    regions += sorted(r for r in bins if r not in regions)
    from collections import deque
    queues={name:deque(bins[name]) for name in regions}
    ordered=[]
    while any(queues.values()):
        for name in regions:
            if queues[name]:
                ordered.append(queues[name].popleft())
    return ordered


def due(pending, history, today):
    ready = []
    for row in pending:
        if research_route(row)=='ENRICHMENT_ONLY':
            continue
        old = history.get(row['project_id'], {})
        same_source = not old.get('input_fingerprint') or old.get('input_fingerprint') == fingerprint(row)
        age = days_since(local_attempt_date(old), today)
        if same_source:
            if (old.get('status')=='AI_EVIDENCE_REVIEW'
                    and old.get('project_identity_confidence') not in
                        ('EXACT_LIVE_OFFICIAL','EXACT_LOCAL_COLLECTOR','EXACT_ID_ON_PUBLIC_PAGE')
                    and 0 <= age < 7):
                continue  # Retain address-only history, retry at most weekly
            if old.get('status') == 'AI_SOURCE_RECORD_REVIEW' and 0 <= age < 14:
                continue  # AI analyzed; schedule later independent-evidence recheck
            if old.get('status') in ('AI_ERROR_REVIEW', 'INSUFFICIENT_SOURCE_RECORD') and age == 0:
                continue  # do not retry a broken API or empty record repeatedly today
        ready.append(row)

    def rank(row):
        queued = row.get('_queued_on') or today.isoformat()
        try:
            age = max(0, (today - dt.date.fromisoformat(queued[:10])).days)
        except ValueError:
            age = 0
        # Lane is the primary key: credible early cues first, mature permits
        # later. Old inspection and generic updates never jump lanes by age.
        base = LANES.get(canonical_lane(row), 6)
        effective = base
        prior = history.get(row.get('project_id'), {})
        followup = prior.get('status') == 'AI_SOURCE_RECORD_REVIEW'
        try:
            score = int(row.get('review_priority') or 0)
        except ValueError:
            score = 0
        status_order={'PRE_APPROVAL':0,'PRE_ISSUANCE':1,'APPROVED_NOT_ISSUED':2,
                      'PERMIT_ISSUED':3,'UNKNOWN':4,'INSPECTION_STAGE':5,
                      'COMPLETED':8,'BLOCKED_OR_INACTIVE':9}
        # These are rankings from the local record, NOT a claim of live stage.
        status_rank=status_order.get(classify_status(row.get('current_source_status')),4)
        return (effective,status_rank,followup,-min(365,age),-score,
                queued,row.get('project_id',''))
    return fair_regional_order(sorted(ready, key=rank))
