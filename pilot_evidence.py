"""Bounded free official-source discovery for the DeepSeek investigation pilot.

Only follows source links already in the local opportunity queue. This is NOT a
general search engine; unknown URLs are never invented. Does not call AI.
"""
import argparse,csv,datetime,html,ipaddress,json,re,socket
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from lead_research import candidate_id,read_csv,UA

ROOT=Path(__file__).resolve().parent
FIELDS=['candidate_id','url','source_type','operating_name','legal_name','franchise_brand',
        'franchisee_name','decision_maker','decision_maker_role','contact_email',
        'contact_phone','notes']
AUDIT=['candidate_id','url','status','detail']
# City/region original sources only. Never auto-fetch arbitrary model-supplied URLs.
OFFICIAL_SUFFIXES=('toronto.ca','brampton.ca','mississauga.ca','peelregion.ca',
                   'halton.ca','york.ca','durham.ca','hamilton.ca','niagararegion.ca',
                   'waterloo.ca','ontario.ca','arcgis.com','arcgisonline.com')
def public_official_url(url):
    p=urlparse(str(url or '').strip())
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        return ''
    host=p.hostname.lower().rstrip('.')
    if not any(host==domain or host.endswith('.'+domain) for domain in OFFICIAL_SUFFIXES):
        return ''
    return p.geturl()

def public_dns(host):
    try:
        ips={v[4][0] for v in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)}
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (OSError,ValueError):return False

def fetch_official_page(url,session):
    """Robots fail-closed; fixed host, no redirect, strict byte/content limit."""
    url=public_official_url(url)
    if not url:return '', 'not approved official HTTPS link'
    p=urlparse(url)
    if not public_dns(p.hostname):return '', 'host is not publicly resolvable'
    robots=p.scheme+'://'+p.netloc+'/robots.txt'
    try:
        rr=session.get(robots,timeout=10,allow_redirects=False)
        if rr.status_code!=200:return '', 'robots policy unavailable'
        rp=RobotFileParser();rp.parse(rr.text[:200000].splitlines())
        if not rp.can_fetch(UA,url):return '', 'robots disallows page'
        with session.get(url,timeout=15,allow_redirects=False,stream=True,
                         headers={'Accept':'text/html'}) as r:
            if r.status_code!=200:return '', 'HTTP '+str(r.status_code)
            if 'text/html' not in r.headers.get('content-type','').lower():return '', 'not an HTML document'
            chunks=[];count=0
            for part in r.iter_content(chunk_size=16384):
                count+=len(part)
                if count>350000:return '', 'document too large'
                chunks.append(part)
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(b''.join(chunks).decode(r.encoding or 'utf-8',errors='replace'),'html.parser')
            for tag in soup(['script','style','noscript','nav','footer']):tag.decompose()
            return re.sub(r'\\s+',' ',soup.get_text(' ',strip=True))[:6000], ''
    except Exception as exc:return '',type(exc).__name__+': '+str(exc)[:100]

def url_list(row):
    result=[]
    for field in ('source_evidence_urls','evidence_url'):
        for s in re.split(r'\\s*\\|\\s*',row.get(field,'') or ''):
            u=public_official_url(s.strip())
            if u and u not in result:result.append(u)
    return result

def collect(data,max_leads=3,max_pages=6,fetch=False):
    """Dry run defaults to no network requests, no paid calls."""
    data=Path(data);data.mkdir(parents=True,exist_ok=True)
    candidates=read_csv(data/'research_priority_queue.csv')
    evidence=[];audit=[];seen=set();pages=0
    import requests
    session=requests.Session();session.trust_env=False;session.headers['User-Agent']=UA
    for row in candidates[:max(0,max_leads)]:
        cid=candidate_id(row)
        for url in url_list(row):
            if (cid,url) in seen:continue
            seen.add((cid,url))
            if not fetch:
                audit.append(dict(candidate_id=cid,url=url,status='DRY_RUN',detail='Would check official source URL'))
                continue
            if pages>=max_pages:
                audit.append(dict(candidate_id=cid,url=url,status='SKIPPED',detail='Page limit reached'))
                continue
            pages+=1
            text,error=fetch_official_page(url,session)
            audit.append(dict(candidate_id=cid,url=url,status='FETCHED' if text else 'SKIPPED',detail=error or 'Official page text collected for review'))
            if text:
                evidence.append(dict(candidate_id=cid,url=url,source_type='official_municipal_page',
                                     notes=text[:5500]))
    def save(path,cols,rows):
        with (data/path).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
    save('pilot_official_evidence_REVIEW_ONLY.csv',FIELDS,evidence)
    save('pilot_evidence_audit.csv',AUDIT,audit)
    print('Evidence pilot:',len(candidates[:max(0,max_leads)]),'candidates;',len(audit),'official URLs;',len(evidence),'pages retrieved; paid AI calls=0')
    if not audit:print('No direct official record URLs in this queue; requires source-specific official lookup integration.')
    return evidence,audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',type=Path,default=ROOT/'data')
    p.add_argument('--max-leads',type=int,default=3)
    p.add_argument('--max-pages',type=int,default=6)
    p.add_argument('--fetch',action='store_true',help='Retrieve publicly accessible linked official HTML (no AI charges)')
    a=p.parse_args();collect(a.data_dir,a.max_leads,a.max_pages,a.fetch)
if __name__=='__main__':main()
