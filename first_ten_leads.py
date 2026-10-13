"""Build an honest, buyer-oriented first-10 commercial lead review pack.

Local/offline only. Does not verify contacts, claim leads are sale-ready,
change source databases, or initiate paid AI requests.
"""
import argparse
import csv
import html
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
FIELDS=['investigation_id','business','address','city','commercial_signal','event_date','date_basis',
        'source_id','buyer_categories','source_evidence','operator_status','contact_status',
        'missing_to_qualify','readiness','review_priority','source_description']

def valid_url(value):
    url=str(value or '').strip()
    p=urlparse(url)
    return url if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''

def buyer_fit(row):
    """Suggestions describe possible buyer needs, never an actual purchase intent."""
    text=' '.join(str(row.get(k) or '') for k in ('description','event_class','event_type')).lower()
    result=[]
    if any(s in text for s in ('construction','development','building','site plan','tenant','retail','restaurant','office','warehouse','industrial','commercial')):
        result+=['Commercial HVAC','Security/access systems','Commercial insurance']
    if any(s in text for s in ('restaurant','food','kitchen','cafe')):
        result.append('Restaurant/equipment suppliers')
    if any(s in text for s in ('warehouse','industrial','factory','manufactur')):
        result.append('Industrial equipment suppliers')
    if not result:result=['Commercial insurance — fit to verify']
    return '; '.join(dict.fromkeys(result))

def build(data,maximum=10):
    data=Path(data)
    data.mkdir(parents=True,exist_ok=True)
    source=data/'research_priority_queue.csv'
    with source.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    profiles=[]
    for row in rows[:max(0,maximum)]:
        name=(row.get('company_name') or '').strip()
        operator='NAMED_UNVERIFIED' if name else ('POSSIBLE_ADDRESS_MATCH_UNVERIFIED' if row.get('operator_candidates') else 'UNKNOWN')
        urls=[valid_url(u) for u in (row.get('source_evidence_urls') or row.get('evidence_url') or '').split(' | ')]
        urls=list(dict.fromkeys(u for u in urls if u))
        missing=[]
        if not name:missing.append('Identify business/operator')
        if not urls:missing.append('Attach official record URL')
        if not row.get('address'):missing.append('Confirm location')
        missing.extend(['Verify operating entity','Verify decision-maker','Verify business contact','Human commercial relevance review'])
        item=dict(investigation_id=row.get('investigation_id',''),business=name or 'OPERATOR UNKNOWN',
                  address=row.get('address',''),city=row.get('city',''),
                  commercial_signal=row.get('event_class') or row.get('event_type',''),
                  event_date=row.get('event_date',''),
                  date_basis=('CHANGE_DETECTED_NOT_NEW_ISSUANCE' if row.get('source_group')=='MUNICIPAL_CHANGE'
                              else row.get('event_confidence') or 'SOURCE_DATE_UNVERIFIED'),
                  source_id=row.get('source_id',''),buyer_categories=buyer_fit(row),
                  source_evidence=' | '.join(urls),operator_status=operator,
                  contact_status='NOT_VERIFIED',missing_to_qualify='; '.join(missing),
                  readiness='RESEARCH_ONLY_NOT_FOR_SALE',review_priority=row.get('research_priority',''),
                  source_description=row.get('description',''))
        profiles.append(item)
    with (data/'FIRST_10_LEAD_PROFILES_REVIEW_ONLY.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(profiles)
    page=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>GTA Radar — First 10 Lead Profiles</title>',
          '<style>body{font:15px Segoe UI,Arial;max-width:1200px;margin:30px auto;padding:0 15px;color:#243246;background:#fafafa}article{background:white;border:1px solid #ddd;border-radius:10px;padding:18px;margin:16px 0}small{color:#555}h1{margin-bottom:4px}dt{font-weight:bold;margin-top:8px}dd{margin-left:0;overflow-wrap:anywhere}a{color:#195b93}</style></head><body>',
          '<h1>GTA Commercial Radar — First 10 Lead Profiles</h1>',
          '<p><strong>Research only — not verified, not ready for sale.</strong> Buyer categories are potential service fits, not contacted buyers. No AI spending.</p>',
          '<p>'+str(len(profiles))+' investigation profiles prepared. Source records remain unchanged.</p>']
    for row in profiles:
        esc=lambda v:html.escape(str(v or ''),quote=True)
        page.append('<article><h2>'+esc(row['business'])+'</h2>')
        for title,key in [('Commercial event','commercial_signal'),('Location','address'),('City','city'),
                          ('Detected/source date','event_date'),('Date basis','date_basis'),('Municipal source','source_id'),
                          ('Potential buyers','buyer_categories'),('Research priority','review_priority'),
                          ('Operator status','operator_status'),('Contact status','contact_status'),
                          ('Work required','missing_to_qualify'),('Source description','source_description')]:
            page.append('<dt>'+esc(title)+'</dt><dd>'+esc(row[key])+'</dd>')
        page.append('<dt>Evidence</dt><dd>')
        for url in row['source_evidence'].split(' | '):
            if url:page.append('<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">'+esc(url)+'</a> ')
        if not row['source_evidence']:page.append('Missing official record link')
        page.append('</dd><small>RESEARCH ONLY — NOT FOR SALE</small></article>')
    page.append('</body></html>')
    (data/'first_10_leads_dashboard.html').write_text(''.join(page),encoding='utf-8')
    print('First lead profiles:',len(profiles),'research-only; verified-for-sale=0')
    print('Open:',data/'first_10_leads_dashboard.html')
    return profiles

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',type=Path,default=ROOT/'data')
    p.add_argument('--max',type=int,default=10)
    a=p.parse_args()
    build(a.data_dir,a.max)
