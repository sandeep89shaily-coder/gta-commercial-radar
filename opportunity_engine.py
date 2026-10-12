"""Municipal-led event intelligence. Preservation and qualification are separate.
No paid network calls. Read-only against existing collector stores.
"""
import argparse,csv,hashlib,html,json,re,sqlite3
from contextlib import closing
from collections import Counter,defaultdict
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from recent_opportunities import parse_date
ROOT=Path(__file__).resolve().parent
COLS=['opportunity_id','source_id','source_key','company_name','entity_name','address','city','industry','event_date','event_type','observed_at','buyer_categories','evidence_url','description','review_status','selection_reason','maturity','identity_confidence','contact_quality','commercial_priority','source_group','missing_information','related_record_count','is_primary_municipal']
def norm(v):return re.sub(r'[^a-z0-9]+',' ',str(v or '').lower()).strip()
def valid(v):return bool(norm(v) and norm(v) not in {'unknown','none','n a','not available','anonymous','unidentified'})
def digest(*parts):return hashlib.sha256('|'.join(map(str,parts)).encode('utf-8')).hexdigest()[:24]
def iter_municipal(data):
    p=data/'radar.sqlite'
    if not p.is_file():return
    with closing(sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        try:
            for raw in db.execute('SELECT source_id,record_key,source_date,normalized_json FROM records_current WHERE active=1'):
                try:normalized=json.loads(raw['normalized_json'] or '{}')
                except (ValueError,TypeError):normalized={}
                if not isinstance(normalized,dict):normalized={}
                name=str(normalized.get('entity_name') or normalized.get('business_name') or normalized.get('applicant') or normalized.get('owner_name') or '')
                addr=str(normalized.get('address') or normalized.get('site_address') or '')
                description=str(normalized.get('description') or normalized.get('work_description') or '')
                yield dict(source_id=raw['source_id'],source_key=raw['record_key'],company_name=name,entity_name=name,address=addr,city=normalized.get('region',''),industry=normalized.get('industry',''),event_date=raw['source_date'] or normalized.get('event_date',''),event_type=normalized.get('event_type',''),observed_at='',buyer_categories='commercial_insurance;commercial_hvac;security_access',evidence_url=normalized.get('evidence_url',''),description=description,commercial_relevance=normalized.get('commercial_relevance',''),source_group='MUNICIPAL',is_primary_municipal='YES')
        except sqlite3.DatabaseError as e: print('Municipal database unreadable:',str(e)[:120])
def iter_municipal_updates(data):
    """Post-baseline material updates are detection events, NOT newly issued permits.

    A dated UPDATED entry only exists after comparison against an existing stored
    record. Its observed timestamp denotes when Radar detected the change.
    Historical first-seen NEW records are deliberately excluded.
    """
    p=data/'radar.sqlite'
    if not p.is_file():return
    with closing(sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        try:
            for raw in db.execute("""SELECT source_id,record_key,observed_at,normalized_json
                    FROM changes WHERE change_type='UPDATED'"""):
                try: info=json.loads(raw['normalized_json'] or '{}')
                except (ValueError,TypeError):continue
                if not isinstance(info,dict):continue
                name=str(info.get('entity_name') or '')
                address=str(info.get('address') or '')
                yield dict(source_id=raw['source_id'],source_key=raw['record_key'],
                    company_name=name,entity_name=name,address=address,
                    city=info.get('region',''),industry='',
                    event_date=raw['observed_at'],event_type='SOURCE_RECORD_UPDATED',
                    observed_at=raw['observed_at'],
                    buyer_categories='commercial_insurance;commercial_hvac;security_access',
                    evidence_url=info.get('evidence_url',''),
                    description=info.get('description',''),
                    commercial_relevance=info.get('commercial_relevance',''),
                    source_group='MUNICIPAL_CHANGE',is_primary_municipal='YES',
                    event_date_basis='CHANGE_DETECTED_NOT_PERMIT_ISSUED',
                    opportunity_type=info.get('event_type',''),
                    selection_reason='MATERIAL_SOURCE_RECORD_UPDATED')
        except sqlite3.DatabaseError as e:
            print('Municipal change history unreadable:',str(e)[:120])

def iter_peel_project_changes(data):
    """Only genuine post-baseline changes qualify for consideration.

    Pilot source pages lack dependable event dates, so observed_at is labelled
    as a detection date, never misrepresented as a permit/project issue date.
    The pilot baseline remains available as research evidence, not fresh leads.
    """
    p=data/'peel_pilot.sqlite'
    if not p.is_file():return
    with closing(sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        try:
            for raw in db.execute("""SELECT e.source_id,e.record_key,e.change_type,e.observed_at,
                  e.title,e.source_url FROM events e
                  WHERE e.change_type IN ('NEWLY_OBSERVED','UPDATED')"""):
                r=dict(raw)
                group='PRIVATE_DEVELOPMENT' if r['source_id']=='caledon_development_register' else 'PUBLIC_INFRASTRUCTURE'
                yield dict(source_id=r['source_id'],source_key=r['record_key'],company_name='',entity_name='',
                    address='',city='Caledon' if group=='PRIVATE_DEVELOPMENT' else 'Peel Region',
                    industry='',event_date=r['observed_at'],event_type=r['change_type'],
                    observed_at=r['observed_at'],buyer_categories=('commercial_construction;engineering;insurance' if group=='PRIVATE_DEVELOPMENT' else 'municipal_procurement;civil_construction;water_infrastructure'),
                    evidence_url=r['source_url'],description=r['title'],commercial_relevance='UNASSESSED',
                    source_group='PEEL_PROJECT',is_primary_municipal='YES',
                    event_date_basis='FIRST_SEEN_AFTER_BASELINE_OR_CHANGED_NOT_ISSUE_DATE',opportunity_type=group)
        except sqlite3.DatabaseError as e:print('Peel pilot event database unreadable:',str(e)[:120])

def iter_business(data):
    p=data/'business_discovery.sqlite'
    if not p.is_file():return
    with closing(sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        try:
            for raw in db.execute('SELECT source_id,source_key,company_name,address,city,industry,event_date,event_type,observed_at FROM observations WHERE event_date IS NOT NULL AND TRIM(event_date) != \'\''):
                r=dict(raw);r.update(entity_name=r.get('company_name') or '',buyer_categories='commercial_insurance;accounting_payroll;it_telecom',evidence_url='',description=r.get('industry') or '',source_group='BUSINESS_DISCOVERY',is_primary_municipal='NO')
                yield r
        except sqlite3.DatabaseError as e:print('Business database unreadable:',str(e)[:120])
def score(r):
    description=norm(' '.join(str(r.get(x) or '') for x in ('event_type','description','industry')))
    high=any(k in description for k in ('new construction','new building','new business','new licence','restaurant','commercial','industrial','warehouse','site plan','tenant','expansion','retail','occupancy'))
    low=norm(r.get('commercial_relevance'))=='low' or any(k in description for k in ('single family dwelling','residential only'))
    return 'LOW' if low else ('HIGH' if high else 'UNASSESSED')
def eligible_business_event(r):
    """A historical directory observation is identity evidence, not a new event.

    Only records whose type establishes a formation or licence action can seed
    a standalone lead. Observation/download date never establishes activity.
    """
    kind=norm(r.get('event_type')).upper().replace(' ','_')
    if kind == 'FEDERAL_INCORPORATION_RECORD':
        return True
    if kind == 'BUSINESS_LICENCE_OBSERVATION':
        return True  # source date still must be within recent activity window
    return False

def collect(data,days=2,today=None,limit=100000,lookback_days=90):
    today=today or datetime.now().astimezone().date()
    cutoff=today-timedelta(days=days)
    rows=[];stats=Counter();sources=Counter()
    for group,iterator in [('MUNICIPAL',iter_municipal(data)),('MUNICIPAL_CHANGE',iter_municipal_updates(data)),('PEEL_PROJECT',iter_peel_project_changes(data)),('BUSINESS_DISCOVERY',iter_business(data))]:
        for r in iterator:
            source=str(r.get('source_id') or '')
            sources[(group,source)]+=1
            if group=='BUSINESS_DISCOVERY' and not eligible_business_event(r):
                stats[(group,'enrichment_only')]+=1
                continue
            # Download/observed_at is NEVER an event date; for both source families
            # only an explicitly provided source event date can create a lead.
            d=parse_date(r.get('event_date'))
            if d is None:
                stats[(group,source,'missing_or_invalid_date')]+=1
                stats[(group,'unknown_event_date')]+=1
                continue
            if not cutoff<=d<=today:
                stats[(group,source,'future_date' if d>today else 'older_than_window')]+=1
                stats[(group,'outside_window')]+=1
                continue
            name=r.get('company_name') or ''
            addr=r.get('address') or ''
            missing=[]
            if not valid(name):missing.append('COMPANY_UNKNOWN')
            if not valid(addr):missing.append('LOCATION_UNRESOLVED')
            missing+=['CONTACT_UNVERIFIED','DECISION_MAKER_UNKNOWN']
            key=str(r.get('source_key') or digest(group,source,name,addr,d))
            r.update(source_key=key,opportunity_id=digest(group,source,key),review_status='UNVERIFIED_NOT_FOR_SALE',selection_reason=(r.get('selection_reason') or ('MUNICIPAL_SOURCE_EVENT_DATE' if group=='MUNICIPAL' else ('PEEL_POST_BASELINE_CHANGE_OBSERVED_DATE_NOT_ISSUE_DATE' if group=='PEEL_PROJECT' else 'EXPLICIT_FORMATION_OR_LICENCE_DATE'))),maturity='DETECTED',identity_confidence='UNVERIFIED' if not valid(name) else 'NAMED_UNCONFIRMED',contact_quality='MISSING',commercial_priority=score(r),missing_information=';'.join(missing),related_record_count=1)
            rows.append(r);stats[(group,'selected')]+=1
            stats[(group,source,'selected')]+=1
    # Keep one detection per source record within a run window; do not count
    # several revisions as separate sales opportunities.
    dedup={r['opportunity_id']:r for r in rows}
    priority={'HIGH':2,'UNASSESSED':1,'LOW':0}
    ordered=sorted(dedup.values(),key=lambda r:(r['source_group'] in ('MUNICIPAL','MUNICIPAL_CHANGE','PEEL_PROJECT'),priority.get(r['commercial_priority'],0),str(r.get('event_date') or ''),r['opportunity_id']),reverse=True)
    return ordered,stats,sources

def enrich(rows,data):
    """Attach high-certainty exact-address business hints; preserve uncertainty, never assert a franchisee."""
    index=defaultdict(list)
    p=data/'business_discovery.sqlite'
    if p.is_file():
        with closing(sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)) as db:
            try:
                for name,addr,city,source in db.execute('SELECT company_name,address,city,source_id FROM observations'):
                    if valid(name) and len(norm(addr))>=9:index[(norm(addr),norm(city))].append((name,source))
            except sqlite3.DatabaseError:pass
    for r in rows:
        candidates=index.get((norm(r.get('address')),norm(r.get('city'))),[])
        unique=list(dict.fromkeys(c[0] for c in candidates if valid(c[0])))
        r['related_record_count']=1+len(candidates)
        # Same address may contain different units/businesses. Never auto-confirm legal identity.
        if len(unique)==1 and not valid(r.get('company_name')):
            r['possible_operator']=unique[0];r['maturity']='ENRICHED';r['identity_confidence']='ADDRESS_ONLY_POSSIBLE_MATCH';r['missing_information']+=';VERIFY_SAME_UNIT_AND_OPERATOR'
        elif unique:
            r['possible_operator']=' | '.join(unique[:5]);r['maturity']='ENRICHED';r['missing_information']+=';VERIFY_BUSINESS_ASSOCIATION'
    return rows

def export(data,days=2,today=None,limit=500):
    data.mkdir(parents=True,exist_ok=True)
    rows,stats,sources=collect(data,days,today,limit)
    enrich(rows,data)
    fields=COLS+['possible_operator','event_date_basis','opportunity_type']
    with (data/'opportunities_ALL_REVIEW_ONLY.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    # Stable queue across overlapping daily runs. Never replace existing investigations.
    queue=data/'recent_queue_pending.csv'
    previous=[]
    if queue.is_file():
        with queue.open(encoding='utf-8-sig',newline='') as f:previous=list(csv.DictReader(f))
    backlog={r.get('opportunity_id') or digest(r.get('source_group'),r.get('source_id'),r.get('source_key')):r for r in previous}
    before=len(backlog)
    # Full selected list remains in opportunities_ALL_REVIEW_ONLY.csv.
    # Queue only the highest-priority capped cohort; municipal events rank first.
    for r in rows[:limit]:backlog[r['opportunity_id']]=r
    with queue.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(backlog.values())
    counts=Counter((r['source_group'],r['source_id']) for r in rows)
    # Include zero-event Peel sources; their baseline inventory is not a lead queue.
    pp=data/'peel_pilot.sqlite'
    if pp.is_file():
        with closing(sqlite3.connect(f'file:{pp.as_posix()}?mode=ro',uri=True)) as db:
            try:
                for source_id,n in db.execute('SELECT source_id,COUNT(*) FROM observations GROUP BY source_id'):
                    sources[('PEEL_PROJECT',source_id)]=n
            except sqlite3.DatabaseError:pass

    with (data/'collector_opportunity_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['source_group','source_id','records_available','recent_events_selected','not_selected_in_window'])
        for (group,source),all_count in sorted(sources.items()):
            selected=counts.get((group,source),0);w.writerow([group,source,all_count,selected,all_count-selected])
    # Exact reason breakdown for a zero-selection source. These categories are
    # diagnostic only: an old or missing date is not a new commercial event.
    with (data/'source_date_quality_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['source_group','source_id','records_available','selected_recent','missing_or_invalid_date','older_than_window','future_date','enrichment_only','unclassified'])
        for (group,source),total in sorted(sources.items()):
            selected=counts.get((group,source),0)
            missing=stats[(group,source,'missing_or_invalid_date')]
            older=stats[(group,source,'older_than_window')]
            future=stats[(group,source,'future_date')]
            enrichment=stats[(group,source,'enrichment_only')]
            # Some legacy source families are excluded before date inspection.
            if group=='BUSINESS_DISCOVERY':
                enrichment=max(0,total-selected-missing-older-future)
            w.writerow([group,source,total,selected,missing,older,future,enrichment,
                        max(0,total-selected-missing-older-future-enrichment)])
    dashboard=['<!doctype html><html><meta charset="utf-8"><title>Radar opportunities</title><style>body{font:15px Segoe UI,Arial;max-width:1300px;margin:35px auto;color:#243246}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #ddd;padding:9px;text-align:left}small{color:#555}</style><h1>GTA Radar — Municipal-led Opportunities</h1>']
    municipal=sum(r['source_group']=='MUNICIPAL' for r in rows)
    changes=sum(r['source_group']=='MUNICIPAL_CHANGE' for r in rows)
    peel=sum(r['source_group']=='PEEL_PROJECT' for r in rows)
    business=len(rows)-municipal-changes-peel
    dashboard.append(f'<p><b>{len(rows):,}</b> dated events in recent window: <b>{municipal:,}</b> dated municipal records, <b>{changes:,}</b> post-baseline municipal updates (change-detection dates, not new issuances), <b>{peel:,}</b> Peel project changes, and <b>{business:,}</b> explicit business events. Directory observations remain enrichment-only. No source records were deleted. Leads are not yet verified for sale.</p>')
    dashboard.append('<h2>Collection coverage</h2><table><tr><th>Group</th><th>Source</th><th>Available records</th><th>Recent candidates</th></tr>')
    for (group,source),n in sorted(sources.items()):dashboard.append(f'<tr><td>{html.escape(group)}</td><td>{html.escape(source)}</td><td>{n:,}</td><td>{counts.get((group,source),0):,}</td></tr>')
    dashboard.append('</table><h2>Recent opportunities</h2><table><tr><th>Source</th><th>Business / unresolved</th><th>Address</th><th>Event date</th><th>Stage</th><th>Priority</th></tr>')
    for r in rows[:1000]:
        esc=lambda v:html.escape(str(v or ''))
        dashboard.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (r['source_id'],r.get('company_name') or 'COMPANY UNKNOWN',r.get('address') or 'LOCATION UNRESOLVED',r.get('event_date'),r.get('maturity'),r.get('commercial_priority')) )+'</tr>')
    dashboard.append('</table><p><small>Peel baseline projects stay as evidence and are NOT fresh leads. Peel post-baseline changes use an observed change date, NOT an official issue date. Other records use source event dates. An address match is only a possible identity, never verified ownership.</small></p></html>')
    (data/'opportunity_dashboard.html').write_text(''.join(dashboard),encoding='utf-8')
    print(f'Municipal-led opportunity scan: {len(rows)} dated events; municipal dated={municipal}; municipal updates={changes}; peel post-baseline changes={peel}; explicit business events={business}; pending={len(backlog)}; newly queued={len(backlog)-before}; enrichment-only directory records={stats.get(("BUSINESS_DISCOVERY","enrichment_only"),0)}')
    print('Per-source audit:',data/'collector_opportunity_audit.csv')
    print('Why sources have zero recent leads:',data/'source_date_quality_audit.csv')
    return len(rows),len(backlog)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=2);p.add_argument('--data-dir',default=str(ROOT/'data'));args=p.parse_args()
    if not 1<=args.days<=90:raise SystemExit('days must be 1..90')
    export(Path(args.data_dir),args.days)
