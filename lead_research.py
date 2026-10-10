"""Evidence-led business contact research. No search-engine/registry scraping.

Inputs: data/business_leads_REVIEW_ONLY.csv plus optional data/research_sources.csv.
Optional URLs are visited only from expressly supplied public company-domain URLs,
with robots.txt respected; existing files and radar databases are never modified.
"""
import argparse,csv,hashlib,html,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,quote_plus,urljoin
from urllib.robotparser import RobotFileParser

ROOT=Path(__file__).resolve().parent
UA='GTACommercialRadarResearch/0.1 (public business contact research)'
FIELDS=['candidate_id','candidate_company','candidate_address','source_id','source_key','service_categories','operating_name','legal_name','franchise_brand','franchisee_name','decision_maker','decision_maker_role','contact_email','contact_phone','official_website','research_status','confidence','evidence_urls','evidence_notes','google_search','bing_search','ontario_registry_status','last_researched']
EVIDENCE=['candidate_id','url','source_type','operating_name','legal_name','franchise_brand','franchisee_name','decision_maker','decision_maker_role','contact_email','contact_phone','notes']
EMAIL=re.compile(r'(?<![\w.])([\w.+-]+@[\w-]+(?:\.[\w-]+)+)',re.I)
PHONE=re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4})(?!\d)')

def read_csv(p):
    if not p.exists():return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write_csv(p,cols,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)

def candidate_id(row):
    if row.get('opportunity_id'):return str(row['opportunity_id'])[:24]
    s='|'.join(str(row.get(k,'') or '').strip().lower() for k in ('source_id','source_key','company_name','entity_name','address'))
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def clean_url(v):
    v=(v or '').strip()
    if not v:return ''
    p=urlparse(v)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:return ''
    host=p.hostname.lower()
    if host in ('localhost',) or host.endswith(('.local','.internal','.onion')):return ''
    return v

def collect_public_page(url,session):
    """Fetch a limited, robots-permitted official site page, never arbitrary search results."""
    from bs4 import BeautifulSoup
    from ipaddress import ip_address
    from socket import getaddrinfo
    u=clean_url(url)
    if not u:return {},'invalid URL'
    p=urlparse(u)
    try:
        for ai in getaddrinfo(p.hostname,443 if p.scheme=='https' else 80):
            if not ip_address(ai[4][0]).is_global:return {},'non-public network address'
        robots=f'{p.scheme}://{p.netloc}/robots.txt'
        rp=RobotFileParser()
        rr=session.get(robots,timeout=10,allow_redirects=False)
        if rr.status_code!=200:return {},'robots policy unavailable (fail closed)'
        rp.parse(rr.text.splitlines())
        if not rp.can_fetch(UA,u):return {},'blocked by robots.txt'
        r=session.get(u,timeout=15,allow_redirects=False,headers={'Accept':'text/html'})
        if r.status_code!=200:return {},f'HTTP {r.status_code}'
        if not 'html' in r.headers.get('content-type','').lower():return {},'not HTML'
        if len(r.content)>2_000_000:return {},'page too large'
        soup=BeautifulSoup(r.text,'html.parser')
        for item in soup(['script','style','noscript']):item.decompose()
        text=soup.get_text(' ',strip=True)[:160000]
        links=[]
        for a in soup.select('a[href^="mailto:"],a[href^="tel:"]'):
            links.append(a['href'])
        emails=sorted(set(x.lower() for x in EMAIL.findall(text+' '+' '.join(links)) if not x.endswith(('.png','.jpg','.jpeg'))))[:20]
        phones=sorted(set(f'{a}-{b}-{c}' for a,b,c in PHONE.findall(text+' '+' '.join(links))))[:20]
        return {'emails':emails,'phones':phones,'title':(soup.title.get_text(' ',strip=True)[:120] if soup.title else '')},''
    except Exception as e:return {},type(e).__name__+': '+str(e)[:160]

def research(data,fetch=False,max_pages=20):
    candidates=read_csv(data/'research_priority_queue.csv')
    if not candidates:candidates=read_csv(data/'recent_queue_pending.csv')
    if not candidates:
        candidates=read_csv(data/'business_leads_REVIEW_ONLY.csv')
    if not candidates:
        candidates=read_csv(data/'lead_candidates.csv')
    evidence=read_csv(data/'research_sources.csv')
    byid={}
    for row in evidence:
        byid.setdefault(row.get('candidate_id',''),[]).append(row)
    lookup={}
    for row in candidates:
        cid=candidate_id(row)
        lookup[cid]=row
    data.mkdir(parents=True,exist_ok=True)
    write_csv(data/'research_sources_TEMPLATE.csv',EVIDENCE,[])
    audits=[];out=[];session=None;budget=max_pages
    if fetch:
        import requests
        session=requests.Session();session.headers['User-Agent']=UA
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    for cid,c in lookup.items():
        name=(c.get('company_name') or c.get('entity_name') or c.get('possible_operator') or '').strip()
        addr=(c.get('address') or '').strip()
        entry={'candidate_id':cid,'candidate_company':name,'candidate_address':addr,'source_id':c.get('source_id',''),'source_key':c.get('source_key',''),'service_categories':c.get('buyer_categories',c.get('service_category','')),'research_status':'RESEARCH_REQUIRED','confidence':'NONE','ontario_registry_status':'MANUAL_VERIFICATION_REQUIRED','last_researched':now}
        evidence_records=[]
        for e in byid.get(cid,[]):
            url=clean_url(e.get('url',''))
            if not url:continue
            record={**e,'url':url};evidence_records.append(record)
            if fetch and budget>0 and e.get('source_type','').lower() in ('official_company_website','official_company_contact'):
                budget-=1
                extracted,error=collect_public_page(url,session)
                audits.append({'candidate_id':cid,'url':url,'result':'OK' if not error else 'SKIPPED','detail':error or json.dumps(extracted,ensure_ascii=False)})
                if extracted:
                    if extracted['emails'] and not record.get('contact_email'):record['contact_email']=extracted['emails'][0]
                    if extracted['phones'] and not record.get('contact_phone'):record['contact_phone']=extracted['phones'][0]
        # Avoid silently merging contradictory names/contacts: flag for review.
        for field in ('operating_name','legal_name','franchise_brand','franchisee_name','decision_maker','decision_maker_role','contact_email','contact_phone'):
            vals=list(dict.fromkeys((e.get(field,'') or '').strip() for e in evidence_records if (e.get(field,'') or '').strip()))
            if len(vals)==1:entry[field]=vals[0]
            elif len(vals)>1:entry[field]='';entry['research_status']='CONFLICT_REVIEW'
        urls=list(dict.fromkeys(e['url'] for e in evidence_records))
        entry['evidence_urls']=' | '.join(urls)
        entry['evidence_notes']=' | '.join((e.get('notes','') or '') for e in evidence_records if e.get('notes'))[:800]
        entry['official_website']=next((e['url'] for e in evidence_records if e.get('source_type','').lower().startswith('official_company')), '')
        if evidence_records and entry['research_status']!='CONFLICT_REVIEW':
            entry['research_status']='EVIDENCE_REVIEW_REQUIRED'
            entry['confidence']='SOURCE_ATTACHED_UNVERIFIED'
        # Explicitly zero contact fields when sources are absent.
        q=quote_plus(' '.join([name,addr,'franchise owner contact']).strip())
        entry['google_search']='https://www.google.com/search?q='+q
        entry['bing_search']='https://www.bing.com/search?q='+q
        out.append(entry)
    write_csv(data/'lead_research_REVIEW_ONLY.csv',FIELDS,out)
    write_csv(data/'lead_research_fetch_audit.csv',['candidate_id','url','result','detail'],audits)
    page=['<!DOCTYPE html><html><head><meta charset="utf-8"><title>Lead Research Queue</title><style>body{font:15px Segoe UI,Arial;max-width:1200px;margin:30px auto;padding:0 15px;color:#243042}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}a{color:#135b92}small{color:#555}</style></head><body><h1>Business Identity Research Queue</h1><p>Review only. Contacts and executives are not verified automatically. Evidence-backed research; no automated registry or search-engine scraping.</p><table><tr><th>Candidate</th><th>Address</th><th>Decision-maker</th><th>Business email</th><th>Phone</th><th>Status</th><th>Research</th></tr>']
    for e in out:
        esc=lambda x:html.escape(str(x or ''))
        page.append('<tr><td>'+esc(e['candidate_company'])+'</td><td>'+esc(e['candidate_address'])+'</td><td>'+esc(e.get('decision_maker'))+'</td><td>'+esc(e.get('contact_email'))+'</td><td>'+esc(e.get('contact_phone'))+'</td><td>'+esc(e['research_status'])+'</td><td><a href="'+esc(e['google_search'])+'">Search</a></td></tr>')
    page.append('</table><p><small>To attach evidence, enter candidate_id and official URLs in data/research_sources.csv using the supplied template. Re-run the research script.</small></p></body></html>')
    (data/'lead_research_dashboard.html').write_text(''.join(page),encoding='utf-8')
    return len(out),len(evidence),len(audits)

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default=str(ROOT/'data'));p.add_argument('--fetch-official-pages',action='store_true');p.add_argument('--max-pages',type=int,default=20)
    a=p.parse_args();data=Path(a.data_dir)
    n,e,pages=research(data,a.fetch_official_pages,a.max_pages)
    print(f'Lead candidates queued: {n}; attached evidence rows: {e}; website checks: {pages}')
    print('Outputs:',data/'lead_research_REVIEW_ONLY.csv',data/'lead_research_dashboard.html')
    print('To attach evidence: fill research_sources.csv from research_sources_TEMPLATE.csv; no registry scraping or guessed contacts.')
if __name__=='__main__':main()
