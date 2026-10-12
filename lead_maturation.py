"""Local, evidence-preserving business lead maturation.

Does not contact external services or modify collection databases. Builds a
ranked research queue by grouping recent observations at a location and
cross-referencing the locally collected business directory. A shared address
is never treated as proof of a franchisee, operator or corporate relationship.
"""
import csv, hashlib, html, re, sqlite3
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT_FIELDS=['investigation_id','opportunity_id','source_id','source_key','company_name','entity_name','address','city','event_date','event_type','description','commercial_priority','source_group','maturity','review_status','buyer_categories','evidence_url','possible_operator','identity_confidence','missing_information','research_priority','research_reason','linked_events','linked_sources','operator_candidates','identity_evidence','contact_status','service_opportunities','event_class','event_confidence','identity_status','contact_evidence','source_evidence_urls','qualification_note']

def clean(v):
    return re.sub(r'[^a-z0-9]+',' ',str(v or '').lower()).strip()

def address_key(v):
    s=' '+clean(v)+' '
    for a,b in [(' street ',' st '),(' road ',' rd '),(' avenue ',' ave '),(' boulevard ',' blvd '),(' drive ',' dr '),(' crescent ',' cres '),(' highway ',' hwy '),(' court ',' ct '),(' parkway ',' pkwy ')]:s=s.replace(a,b)
    return s.strip()

def read_csv(p):
    if not p.is_file():return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write_csv(p,fields,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def identity_index(data):
    """Address-only hints: never proof of legal operator; do not load whole DB in RAM."""
    db=data/'business_discovery.sqlite'; index=defaultdict(set)
    if not db.is_file():return index
    with sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True) as c:
        try:
            for name,addr,city,source in c.execute('SELECT company_name,address,city,source_id FROM observations'):
                k=address_key(addr)
                if len(k)<8 or not clean(name):continue
                index[(k,clean(city))].add((str(name).strip(),str(source or '')))
        except sqlite3.DatabaseError:pass
    return index

def event_class(r):
    """Classify what was observed, never infer an opening from an inspection."""
    source=clean(r.get('source_id'))
    desc=clean(' '.join(str(r.get(k) or '') for k in ('event_type','description','industry')))
    if 'peel health' in source or 'dinesafe' in source:
        return 'INSPECTION_OR_ESTABLISHMENT_RECORD'
    if 'environmental' in source or source.startswith('ero '):
        return 'REGULATORY_ACTIVITY'
    if 'development' in source or 'rezoning' in source or 'site plan' in source or 'planit' in source:
        return 'DEVELOPMENT_APPLICATION'
    if 'permit' in source:
        return 'BUILDING_PERMIT'
    if 'licence' in source or 'license' in source:
        return 'BUSINESS_LICENSING'
    if 'corporation' in source or 'incorporat' in desc:
        return 'CORPORATE_EVENT'
    return 'OTHER_ACTIVITY'

def project_marker(r):
    """Use a strong project identifier when supplied; otherwise conservatively avoid merging conflicting named enterprises."""
    for k in ('project_id','application_number','permit_number','file_number'):
        v=clean(r.get(k))
        if v:return 'project:'+clean(r.get('source_id'))+':'+v
    # The opportunity export may not retain a project ID. Preserve separate distinct
    # operators/tenants even at one address, and separate different event families.
    name=clean(r.get('company_name'))
    kind=event_class(r)
    if kind=='INSPECTION_OR_ESTABLISHMENT_RECORD':
        return 'establishment:'+name if name else 'record:'+clean(r.get('source_key'))
    return 'kind:'+kind

def group_recent(rows):
    """Group same-place compatible observations, not every tenant at a civic address."""
    groups=defaultdict(list)
    for r in rows:
        location=address_key(r.get('address'))
        city=clean(r.get('city'))
        if location and len(location)>=8:
            key='location:'+location+'|'+city+'|'+project_marker(r)
        else:
            key='record:'+str(r.get('opportunity_id') or r.get('source_id','')+'|'+r.get('source_key',''))
        groups[key].append(r)
    return groups

def rank(r,linked,operator_names):
    """Ranking guides research spend; it does not decide which observations are stored."""
    kind=event_class(r)
    base={'DEVELOPMENT_APPLICATION':32,'BUILDING_PERMIT':39,'BUSINESS_LICENSING':45,
          'CORPORATE_EVENT':35,'REGULATORY_ACTIVITY':32,
          'INSPECTION_OR_ESTABLISHMENT_RECORD':12,'OTHER_ACTIVITY':15}[kind]
    src=clean(r.get('source_id'))
    desc=clean(r.get('description'))
    score=base
    if r.get('source_group') in ('MUNICIPAL','PEEL_PROJECT'): score+=12
    if r.get('source_group')=='MUNICIPAL_CHANGE':score-=18
    if r.get('commercial_priority')=='LOW':score-=28
    if any(x in desc for x in ('commercial','industrial','retail','restaurant','warehouse','office','factory','new construction','new building','fit out','tenant')):score+=18
    if any(x in desc for x in ('single family','residential','basement','detached dwelling','semi detached','interior alteration dwelling')):score-=27
    if r.get('commercial_priority')=='HIGH':score+=8
    if r.get('address'):score+=5
    if r.get('company_name') and clean(r['company_name']) not in ('company unknown','unknown'):score+=6
    if len(linked)>1:score+=min(12,4*(len(linked)-1))
    if operator_names:score+=5
    if r.get('evidence_url') or r.get('source_evidence_urls'):score+=7
    if not r.get('address') and not r.get('company_name'):score-=12
    return max(0,min(score,100))

def balanced_focus(opportunities,maximum):
    """Cap change-only investigations and per-source concentration.

    Preserve the complete sorted archive; quota applies solely to today's
    review/research shortlist, never to collection or commercial eligibility.
    """
    maximum=max(0,maximum)
    change_cap=max(1,maximum//3) if maximum else 0
    source_cap=max(1,maximum//3) if maximum else 0
    selected=[];seen=set();source_counts=Counter();changes=0
    for r in opportunities:
        if len(selected)>=maximum:break
        sid=str(r.get('source_id') or '')
        change=r.get('source_group')=='MUNICIPAL_CHANGE'
        if change and changes>=change_cap:continue
        if source_counts[sid]>=source_cap:continue
        key=r.get('investigation_id')
        if key in seen:continue
        selected.append(r);seen.add(key)
        source_counts[sid]+=1
        if change:changes+=1
    # Avoid leaving research slots unused when sources are genuinely scarce,
    # while continuing to respect the change quota.
    for r in opportunities:
        if len(selected)>=maximum:break
        if r.get('investigation_id') in seen:continue
        if r.get('source_group')=='MUNICIPAL_CHANGE' and changes>=change_cap:continue
        selected.append(r);seen.add(r.get('investigation_id'))
        if r.get('source_group')=='MUNICIPAL_CHANGE':changes+=1
    return selected

def mature(data,maximum=50):
    data=Path(data)
    current=read_csv(data/'opportunities_ALL_REVIEW_ONLY.csv')
    if not current:
        # A no-event run must invalidate yesterday's visible and research
        # outputs; otherwise the dashboard can display stale candidates.
        write_csv(data/'matured_opportunities_REVIEW_ONLY.csv',OUT_FIELDS,[])
        write_csv(data/'research_priority_queue.csv',OUT_FIELDS,[])
        (data/'investigation_dashboard.html').write_text(
            '<!doctype html><html><meta charset="utf-8"><title>GTA Radar Intelligence</title>'
            '<h1>GTA Radar — Prioritized Investigation</h1>'
            '<p>No qualifying recent events in the current selection window.</p>'
            '<p>Historical records remain archived; zero sale-ready leads are claimed.</p></html>',
            encoding='utf-8')
        return dict(observations=0,groups=0,prioritized=0,with_operator_hints=0)
    ix=identity_index(data)
    grouped=group_recent(current)
    opportunities=[]
    for groupkey,members in grouped.items():
        # Choose a primary municipal observation if present, then commercial relevance.
        members=sorted(members,key=lambda x:(x.get('source_group') in ('MUNICIPAL','PEEL_PROJECT'),x.get('commercial_priority')=='HIGH',x.get('event_date','')),reverse=True)
        r=dict(members[0]);addr=address_key(r.get('address'))
        city=clean(r.get('city'))
        possible=sorted(set(ix.get((addr,city),())) | set(ix.get((addr,''),()))) if addr else []
        names=sorted(set(n for n,s in possible))[:12]
        iid=hashlib.sha256(groupkey.encode('utf-8')).hexdigest()[:24]
        score=rank(r,members,names)
        r.update(event_class=event_class(r),event_confidence='SOURCE_EVENT_NOT_OPENING_VERIFIED',identity_status='UNVERIFIED' if names else 'UNKNOWN',contact_evidence='',source_evidence_urls=' | '.join(sorted(set(m.get('evidence_url','') for m in members if m.get('evidence_url')))),qualification_note='Research candidate only; event and operator require corroboration',investigation_id=iid,linked_events=str(len(members)),linked_sources=';'.join(sorted(set(m.get('source_id','') for m in members))),operator_candidates=' | '.join(names),identity_evidence='ADDRESS_ONLY_UNVERIFIED' if names else 'NO_IDENTITY_MATCH',contact_status='NOT_VERIFIED',research_priority=str(score),research_reason=('MULTI_RECORD_LOCATION' if len(members)>1 else 'SINGLE_SOURCE_EVENT'),service_opportunities=r.get('buyer_categories',''),review_status='UNVERIFIED_NOT_FOR_SALE')
        # Never assign a possible operator as confirmed legal identity.
        if names and not r.get('possible_operator'):r['possible_operator']=' | '.join(names[:5])
        opportunities.append(r)
    opportunities.sort(key=lambda r:(int(r['research_priority']),r.get('event_date',''),r.get('investigation_id','')),reverse=True)
    write_csv(data/'matured_opportunities_REVIEW_ONLY.csv',OUT_FIELDS,opportunities)
    # Restrict research budget/workload; all potential opportunities remain in full export.
    focus=balanced_focus(opportunities,maximum)
    write_csv(data/'research_priority_queue.csv',OUT_FIELDS,focus)
    page=['<!doctype html><html><meta charset="utf-8"><title>GTA Radar Intelligence</title><style>body{font:15px Segoe UI,Arial;max-width:1250px;margin:35px auto;color:#223349}table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}small{color:#555}</style><h1>GTA Radar — Prioritized Investigation</h1>']
    page.append(f'<p><b>{len(current):,}</b> recent source events grouped into <b>{len(opportunities):,}</b> location/event investigations. <b>{len(focus):,}</b> queued for research. No operating identities or contacts are automatically verified.</p>')
    page.append('<p>Change-only detections are capped at one third of the review shortlist. Source concentration is limited when alternatives exist. These are NOT verified leads.</p>')
    page.append('<p>Missing information remains a research task. All source observations are preserved separately. Shared addresses are possible matches, not proof of ownership, tenancy or franchise operation.</p>')
    page.append('<table><tr><th>Priority</th><th>Event type</th><th>Source</th><th>Business</th><th>Address</th><th>Events</th><th>Possible operator (unverified)</th><th>Evidence</th></tr>')
    for r in focus:
        vals=(r['research_priority'],r['event_class'],r['linked_sources'],r.get('company_name') or 'UNKNOWN',r.get('address') or 'UNKNOWN',r['linked_events'],r['operator_candidates'] or 'Not identified',r['source_evidence_urls'] or 'Not supplied')
        page.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in vals)+'</tr>')
    page.append('</table></html>')
    (data/'investigation_dashboard.html').write_text(''.join(page),encoding='utf-8')
    return dict(observations=len(current),groups=len(opportunities),prioritized=len(focus),with_operator_hints=sum(bool(r['operator_candidates']) for r in opportunities))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default=str(ROOT/'data'));p.add_argument('--max',type=int,default=50);a=p.parse_args()
    print('Investigation preparation:',mature(Path(a.data_dir),a.max))
