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

META = ('_queued_on', '_fingerprint')
FINISHED = {'AI_EVIDENCE_REVIEW', 'AI_SOURCE_RECORD_REVIEW'}
CLOSED = re.compile(r'\b(closed|refused|withdrawn|cancelled|canceled|rejected|denied|inactive)\b', re.I)
LANES = {'PERMIT_REVIEW':0, 'BUSINESS_REVIEW':1, 'PLANNING_WATCH':2,
         'OTHER_WATCH':3, 'SOURCE_UPDATE_WATCH':4}
SIGNATURE_FIELDS = ('project_id', 'source_id', 'source_keys', 'address',
                    'company_name', 'description', 'current_source_status',
                    'record_source_url', 'permit_types')


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
    combined = {r['project_id']: dict(r) for r in queued_rows if r.get('project_id')}
    for r in current_rows:
        ident = r.get('project_id')
        if not ident or CLOSED.search(str(r.get('current_source_status') or '')):
            continue
        old = combined.get(ident, {})
        added = dict(old)
        added.update(r)
        added['_queued_on'] = old.get('_queued_on') or today.isoformat()
        added['_fingerprint'] = fingerprint(added)
        combined[ident] = added

    pending = []
    for ident, row in combined.items():
        if CLOSED.search(str(row.get('current_source_status') or '')):
            continue
        old = history.get(ident, {})
        same_source = not old.get('input_fingerprint') or old.get('input_fingerprint') == fingerprint(row)
        if old.get('status') == 'AI_EVIDENCE_REVIEW' and same_source:
            continue
        pending.append(row)
    return pending


def due(pending, history, today):
    ready = []
    for row in pending:
        old = history.get(row['project_id'], {})
        same_source = not old.get('input_fingerprint') or old.get('input_fingerprint') == fingerprint(row)
        age = days_since(local_attempt_date(old), today)
        if same_source:
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
        base = LANES.get(row.get('lane'), 5) * 7
        # Old backlog gains priority, so ongoing new permits cannot starve it.
        effective = max(0, base - min(35, age // 2))
        prior = history.get(row.get('project_id'), {})
        followup = prior.get('status') == 'AI_SOURCE_RECORD_REVIEW'
        try:
            score = int(row.get('review_priority') or 0)
        except ValueError:
            score = 0
        return (followup, effective, -score, queued, row.get('project_id', ''))
    return sorted(ready, key=rank)
