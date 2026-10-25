"""Strict post-baseline early signals -> DeepSeek research *candidates*.

A candidate is not a confirmed procurement opportunity. Deterministic,
free gate runs before any paid request; only new/changed source records enter.
"""
from __future__ import annotations
import csv
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

GATES=(
    'EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv',
    'EARLY_CUES_CHANGES_REVIEW_ONLY.csv',
    'EARLY_DISCOVERY_CHANGES_REVIEW_ONLY.csv',
    'EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv',
    'EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv',
    'EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv',
    'EARLY_AJAX_CHANGES_REVIEW_ONLY.csv',
    'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv',
)
GTA=re.compile(r'\b(?:Brampton|Mississauga|Toronto|Vaughan|Markham|Richmond Hill|'
               r'Burlington|Oakville|Milton|Ajax|Pickering|Whitby|Oshawa|Hamilton|'
               r'Kitchener|Waterloo|Cambridge|Guelph|Niagara|York Region|Peel|Durham|'
               r'Halton|Scarborough|Etobicoke|Brantford|Newmarket|Concord|Woodbridge)\b',re.I)
WORK=re.compile(r'\b(?:expan\w*|investment|investing|manufactur\w*|production line|'
    r'new (?:facility|plant|factory|warehouse|distribution|building)|moderniz\w*|'
    r'install\w*|equipment|automation|facility upgrade|industrial|warehouse|'
    r'fit[ -]?out|rezoning|site plan|preconsultation|propos\w*|construction|'
    r'large load|power connection|capacity increase)\b',re.I)
RESIDENTIAL=re.compile(r'\b(?:townhouses?|apartments?|condominiums?|single.family|residential only)\b',re.I)
COLUMNS=('project_id','source_id','source_keys','description','company_name','address','city',
         'lane','review_priority','current_source_status','event_date','source_record_date',
         'record_source_url','record_source_url_basis','early_signal_stage',
         'early_signal_type','procurement_status','date_basis','purchase_status')
GAPS=('source_id','record_id','title','company','site','source_url','reason')


def read_csv(path):
    if not Path(path).is_file():return []
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def _url(x):
    try:
        p=urlparse(x)
        return p.scheme=='https' and p.hostname and p.hostname!='localhost' and not p.username
    except ValueError:return False


def qualify(record):
    """Fail closed on residential, undated/non-change documents and weak claims."""
    kind=(record.get('change_type') or '').upper()
    if kind not in ('NEW','UPDATED'):return 'NOT_NEW_OR_CHANGED'
    sid=record.get('source_id') or ''
    if sid in ('industrial_property_watch','corporate_capex_watch'):
        # Generic market or earnings context should not consume DeepSeek.
        return 'CONTEXT_ONLY_REVIEW'
    title=record.get('title') or record.get('description') or ''
    desc=record.get('description') or title
    fit=(record.get('commercial_fit') or record.get('commercial_signal') or '').upper()
    if fit in ('LOW','RESIDENTIAL_LIKELY','UNKNOWN','USE_UNKNOWN'):
        return 'COMMERCIAL_FIT_NOT_ESTABLISHED'
    if RESIDENTIAL.search(desc) and not re.search(r'\b(?:industrial|commercial|warehouse|manufactur)\b',desc,re.I):
        return 'RESIDENTIAL_ONLY'
    if not WORK.search(desc+' '+title):return 'NO_PURCHASING_RELATED_PROJECT_SCOPE'
    url=record.get('source_url') or record.get('exact_source_record_url') or ''
    if not _url(url):return 'MISSING_RECORD_URL'
    recid=record.get('record_id') or record.get('record_key') or record.get('feature_id') or ''
    if not recid:return 'MISSING_PROJECT_IDENTITY'
    location=record.get('site') or record.get('location') or ''
    city=record.get('city') or ''
    company=record.get('company') or record.get('published_company_unverified_role') or ''
    # Investment-funded record with explicit company, or planning with site.
    if sid.startswith(('feddev_','investontario_')):
        if not company:return 'COMPANY_NOT_IDENTIFIED_IN_INDEX'
        if not GTA.search(desc+' '+title+' '+location+' '+city):
            return 'GTA_SITE_NOT_ESTABLISHED'
    elif not location and not company:
        return 'BUYER_AND_SITE_BOTH_UNKNOWN'
    if 'CALENDAR_ONLY' in recid:return 'CALENDAR_NOT_PROJECT'
    return ''


def compile_sources(folder,successful_runners,run_started):
    """Require actual current-run status and observed_at >= run start."""
    folder=Path(folder)
    target=[];gaps=[];seen=set()
    from datetime import datetime,timezone
    def moment(s):
        try:
            d=datetime.fromisoformat((s or '').replace('Z','+00:00'))
            return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:return None
    start=moment(run_started)
    file_to_runner={
        'EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv':'early_planning_pilot',
        'EARLY_CUES_CHANGES_REVIEW_ONLY.csv':'early_industrial_cues',
        'EARLY_DISCOVERY_CHANGES_REVIEW_ONLY.csv':'early_agendas',
        'EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv':'early_hamilton',
        'EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv':'early_notices',
        'EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv':'early_oakville',
        'EARLY_AJAX_CHANGES_REVIEW_ONLY.csv':'early_ajax',
        'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv':'investment_cues',
    }
    for file in GATES:
        if file_to_runner[file] not in successful_runners and file!='EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv':continue
        live_sources=None
        if file=='EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv':
            live_sources={r.get('source_id') for r in read_csv(folder/'EARLY_INVESTMENT_SOURCE_STATUS.csv')
                          if r.get('status')=='SUCCESS'}
        for row in read_csv(folder/file):
            if live_sources is not None and row.get('source_id') not in live_sources:continue
            stamp=moment(row.get('observed_at'))
            if not stamp or not start or stamp<start:continue
            sid=row.get('source_id') or ''
            rid=row.get('record_id') or row.get('record_key') or row.get('feature_id') or ''
            key=sid+'|'+rid
            if not sid or not rid or key in seen:continue
            seen.add(key)
            reason=qualify(row)
            if reason:
                gaps.append(dict(source_id=sid,record_id=rid,title=row.get('title',''),
                    company=row.get('company',''),site=row.get('site',''),
                    source_url=row.get('source_url',''),reason=reason))
                continue
            desc=(row.get('description') or row.get('title') or '')[:1100]
            addr=row.get('site') or row.get('location') or ''
            city=row.get('city') or ''
            # Do not invent a project street address from the source company.
            company=row.get('company') or row.get('published_company_unverified_role') or ''
            target.append(dict(
                project_id='EARLY-'+hashlib.sha256(key.encode()).hexdigest()[:18],
                source_id=sid,source_keys=rid,description=desc,company_name=company,
                address=addr,city=city,lane='EARLY_SIGNAL_WATCH',review_priority=75,
                current_source_status=row.get('stage') or row.get('status') or 'PUBLIC_CUE',
                event_date=(row.get('observed_at') or '')[:10],
                source_record_date=row.get('source_date') or row.get('source_application_date') or '',
                record_source_url=row.get('source_url') or row.get('exact_source_record_url'),
                record_source_url_basis='DIRECT_PUBLISHED_SOURCE_OR_INDEX_LINK',
                early_signal_stage=row.get('stage') or 'PUBLIC_INVESTMENT_OR_PLANNING_CUE',
                early_signal_type=row.get('signal_type') or 'EARLY_PUBLIC_OBSERVATION',
                procurement_status='UNKNOWN',date_basis='FIRST_OBSERVED_NOT_PROOF_OF_PUBLICATION',
                purchase_status='POSSIBLE_SPEND_NEEDS_SUPPLIER_STATUS_VERIFICATION'))
    return target,gaps


def export(folder,accepted,gaps):
    folder=Path(folder)
    for fname,cols,records in (
        ('GTA_RADAR_EARLY_PURCHASE_CANDIDATES.csv',COLUMNS,accepted),
        ('GTA_RADAR_EARLY_PURCHASE_RESEARCH_GAPS.csv',GAPS,gaps)):
        path=folder/fname
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
            writer.writeheader();writer.writerows(records)
    return folder/'GTA_RADAR_EARLY_PURCHASE_CANDIDATES.csv'
