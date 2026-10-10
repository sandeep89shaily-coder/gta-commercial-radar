"""Autonomous, budgeted, evidence-first lead research using Brave Search API.

Search key: BRAVE_SEARCH_API_KEY. AI key optional: OPENAI_API_KEY.
No search-engine HTML scraping, no Ontario registry automation.
Output always REVIEW_ONLY. Separate research cache; never change source radar.sqlite.
"""
import argparse,csv,hashlib,html,json,os,re,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlparse,quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from lead_research import read_csv,write_csv,candidate_id,clean_url,collect_public_page
from ai_investigator import responses_api,extract_response,validate_answer,compact_evidence,SCHEMA,INSTRUCTIONS

ROOT=Path(__file__).resolve().parent
SEARCH_ENDPOINT='https://api.search.brave.com/res/v1/web/search'
COLUMNS=['candidate_id','candidate_company','candidate_address','status','operating_company','legal_company','franchisee','decision_maker','decision_maker_role','business_email','business_phone','evidence_urls','evidence_count','searches_used','pages_checked','service_fit','caveats','review_required','researched_at']
EVIDENCE=['candidate_id','url','source_type','operating_name','legal_name','franchise_brand','franchisee_name','decision_maker','decision_maker_role','contact_email','contact_phone','notes']
EMAIL=re.compile(r'(?<![\w.])([\w.+-]+@[\w-]+(?:\.[\w-]+)+)',re.I)
PHONE=re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]?([2-9]\d{2})[\s.\-]?(\d{4})(?!\d)')
SKIP_DOMAINS=('facebook.com','linkedin.com','instagram.com','x.com','twitter.com','tiktok.com','pinterest.com','yelp.com','yellowpages.ca','reddit.com','google.com','bing.com','canada.ca')

def search_brave(query,key,timeout=20):
    url=SEARCH_ENDPOINT+'?'+urlencode({'q':query[:350],'count':8,'country':'CA','search_lang':'en'})
    req=Request(url,headers={'Accept':'application/json','X-Subscription-Token':key,'User-Agent':'GTACommercialRadar/0.12'})
    with urlopen(req,timeout=timeout) as res:data=json.load(res)
    result=[]
    for x in data.get('web',{}).get('results',[]):
        url=clean_url(x.get('url',''))
        if url:result.append({'url':url,'title':x.get('title','')[:250],'description':x.get('description','')[:600]})
    return result

def is_company_site(url):
    host=(urlparse(url).hostname or '').lower()
    return bool(host) and not any(host==d or host.endswith('.'+d) for d in SKIP_DOMAINS) and not host.endswith(('.gov.on.ca','.gc.ca'))

def candidate_queries(name,address):
    p=' '.join((address or '').split())[:110]
    name=' '.join((name or '').split())[:100]
    if not name:return []
    return [f'"{name}" "{p}" business operator contact' if p else f'"{name}" business operator contact',
            f'"{name}" "{p}" franchisee owner company' if p else f'"{name}" franchisee owner company',
            f'"{name}" "{p}" email telephone' if p else f'"{name}" email telephone',
            f'"{name}" "{p}" opening manager director' if p else f'"{name}" opening manager director']

def extract_site_contact(url, page):
    return {'url':url,'source_type':'observed_public_webpage','operating_name':'','legal_name':'','franchise_brand':'','franchisee_name':'','decision_maker':'','decision_maker_role':'','contact_email':'','contact_phone':'','notes':f"Page title: {page.get('title','')[:130]}; public emails: {', '.join(page.get('emails',[])[:5])}; public phones: {', '.join(page.get('phones',[])[:5])}"}

def official_match(name,address,title):
    words=[w for w in re.findall(r'[a-z0-9]+',name.lower()) if len(w)>3 and w not in ('incorporated','limited','company','restaurant','corporation')]
    if not words:return False
    title=title.lower()
    return any(w in title for w in words[:4])

def run(data_dir,limit=10,max_searches=30,max_pages=20,ai=False,dry_run=False,refresh=False):
    data_dir=Path(data_dir);data_dir.mkdir(parents=True,exist_ok=True)
    candidates=read_csv(data_dir/'lead_research_REVIEW_ONLY.csv')
    if not candidates:
        raw=read_csv(data_dir/'business_leads_REVIEW_ONLY.csv') or read_csv(data_dir/'lead_candidates.csv')
        candidates=[{'candidate_id':candidate_id(x),'candidate_company':x.get('company_name',x.get('entity_name','')),'candidate_address':x.get('address',''),'service_categories':x.get('buyer_categories','')} for x in raw]
    key=os.environ.get('BRAVE_SEARCH_API_KEY','').strip()
    if not key and not dry_run:
        print('BRAVE_SEARCH_API_KEY is required for autonomous discovery. No search request made.');return 2
    if ai and not os.environ.get('OPENAI_API_KEY','').strip() and not dry_run:
        print('OPENAI_API_KEY missing; --ai requires a key.');return 2
    cache_file=data_dir/'autonomous_research_cache.json'
    try: cache=json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
    except (ValueError,OSError):cache={}
    known=read_csv(data_dir/'research_sources.csv')
    byid={}
    for e in known:byid.setdefault(e.get('candidate_id',''),[]).append(e)
    results=[]; evidence_rows=[]; audits=[]; total_searches=0;total_pages=0
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    import requests
    session=requests.Session();session.headers['User-Agent']='GTACommercialRadarResearch/0.1 (public business contact research)'
    for c in candidates[:max(0,limit)]:
        cid=c.get('candidate_id','');name=c.get('candidate_company','');address=c.get('candidate_address','')
        row={k:'' for k in COLUMNS};row.update(candidate_id=cid,candidate_company=name,candidate_address=address,review_required='YES',researched_at=now)
        if not name:
            row['status']='MISSING_COMPANY_NAME';results.append(row);continue
        cached=cache.get(cid)
        if cached and not refresh and cached.get('name')==name and cached.get('address')==address:
            matches=cached.get('matches',[])
            row['status']='CACHED_EVIDENCE_REVIEW_REQUIRED'
        else:
            matches=[];seen=set()
            for q in candidate_queries(name,address):
                if total_searches>=max_searches:break
                if dry_run:
                    audits.append({'candidate_id':cid,'kind':'SEARCH_PREVIEW','url':'','detail':q});continue
                total_searches+=1
                try:
                    hits=search_brave(q,key)
                    audits.append({'candidate_id':cid,'kind':'SEARCH_OK','url':'','detail':q+' | results='+str(len(hits))})
                except Exception as exc:
                    audits.append({'candidate_id':cid,'kind':'SEARCH_ERROR','url':'','detail':type(exc).__name__+' '+str(exc)[:150]});continue
                for hit in hits:
                    if hit['url'] not in seen:
                        seen.add(hit['url']);matches.append(hit)
                if len(matches)>=10:break
            if not dry_run:cache[cid]={'name':name,'address':address,'matches':matches,'timestamp':now}
        row['searches_used']=len([a for a in audits if a['candidate_id']==cid and a['kind']=='SEARCH_OK'])
        evidence=list(byid.get(cid,[]))
        seen_e={e.get('url') for e in evidence}
        for hit in matches:
            url=hit['url']
            if url in seen_e:continue
            seen_e.add(url)
            evidence.append({'candidate_id':cid,'url':url,'source_type':'search_result_unverified','notes':f"Search result: {hit['title']} — {hit['description']}"})
        # Discover public sites through API first; visit only a small number of candidate-matched websites.
        for hit in matches:
            if dry_run or total_pages>=max_pages:break
            if not is_company_site(hit['url']) or not official_match(name,address,hit['title']):continue
            total_pages+=1
            page,error=collect_public_page(hit['url'],session)
            audits.append({'candidate_id':cid,'kind':'PAGE_OK' if not error else 'PAGE_SKIPPED','url':hit['url'],'detail':error or json.dumps(page)[:350]})
            if page:
                item=extract_site_contact(hit['url'],page);item['candidate_id']=cid
                evidence.append(item)
        for e in evidence:
            # Preserve manually supplied contacts and page observations, but never promote a search snippet to verified contact.
            evidence_rows.append({k:e.get(k,'') for k in EVIDENCE})
        row['pages_checked']=len([a for a in audits if a['candidate_id']==cid and a['kind'] in ('PAGE_OK','PAGE_SKIPPED')])
        row['evidence_count']=len(evidence)
        row['evidence_urls']=' | '.join(dict.fromkeys(e.get('url','') for e in evidence if clean_url(e.get('url',''))))[:6000]
        row['status']='SEARCH_EVIDENCE_REVIEW_REQUIRED' if matches else ('DRY_RUN' if dry_run else 'NO_RESULTS')
        if ai and evidence and not dry_run:
            try:
                comp=compact_evidence([e for e in evidence if e.get('source_type')!='search_result_unverified'],limit=12)
                if not comp:
                    row['status']='SEARCH_ONLY_UNCORROBORATED';results.append(row);continue
                payload={'model':os.environ.get('RADAR_AI_MODEL','gpt-4.1-mini'),'store':False,'instructions':INSTRUCTIONS,
                         'input':json.dumps({'candidate':{'name':name,'address':address,'service_categories':c.get('service_categories','')},'evidence':comp}),
                         'text':{'format':{'type':'json_schema','name':'lead_identity','strict':True,'schema':SCHEMA}},'max_output_tokens':1100}
                answer=extract_response(responses_api(payload,os.environ['OPENAI_API_KEY']))
                row.update(validate_answer(answer,comp));row['status']='AI_EVIDENCE_REVIEW_REQUIRED'
            except Exception as exc:
                row['status']='AI_ERROR_REVIEW';row['caveats']=type(exc).__name__+': '+str(exc)[:200]
        results.append(row)
    write_csv(data_dir/'autonomous_investigations_REVIEW_ONLY.csv',COLUMNS,results)
    write_csv(data_dir/'autonomous_evidence_REVIEW_ONLY.csv',EVIDENCE,evidence_rows)
    write_csv(data_dir/'autonomous_fetch_audit.csv',['candidate_id','kind','url','detail'],audits)
    if not dry_run:cache_file.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Candidates: {len(results)}; search API calls: {total_searches}; public page checks: {total_pages}; evidence entries: {len(evidence_rows)}')
    print('Review output:',data_dir/'autonomous_investigations_REVIEW_ONLY.csv')
    return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default=str(ROOT/'data'));p.add_argument('--limit',type=int,default=10);p.add_argument('--max-searches',type=int,default=30);p.add_argument('--max-pages',type=int,default=20);p.add_argument('--ai',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--refresh',action='store_true')
    a=p.parse_args();sys.exit(run(a.data_dir,a.limit,a.max_searches,a.max_pages,a.ai,a.dry_run,a.refresh))
if __name__=='__main__':main()
