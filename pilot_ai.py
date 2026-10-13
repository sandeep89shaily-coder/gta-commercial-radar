"""Explicit, budgeted DeepSeek pilot using fetched official evidence.

Run separately after: python pilot_evidence.py --fetch
NEVER invoked by START_RADAR.bat; requires --confirm-paid.
"""
import argparse,csv,datetime,json,sqlite3
from pathlib import Path
from deepseek_daily import key_from_windows,ledger,claim,complete,request_ai
from lead_research import candidate_id,read_csv

ROOT=Path(__file__).resolve().parent
COLUMNS=['candidate_id','address','status','operating_company','legal_company','franchisee',
         'decision_maker','decision_maker_role','business_email','business_phone',
         'evidence_urls','caveats','researched_at']

def investigate(data,max_leads=3,confirm_paid=False):
    data=Path(data)
    ev=read_csv(data/'pilot_official_evidence_REVIEW_ONLY.csv')
    rows=read_csv(data/'research_priority_queue.csv')[:max(0,min(max_leads,3))]
    byid={}
    for r in ev:
        if r.get('source_type')!='official_municipal_page' or not r.get('notes') or not r.get('url'):continue
        byid.setdefault(r['candidate_id'],[]).append(r)
    available=[r for r in rows if byid.get(candidate_id(r))]
    if not confirm_paid:
        print('DeepSeek pilot DRY RUN: eligible=',len(available),'; paid calls=0. Explicit --confirm-paid required.')
        return 0
    if not available:
        print('No fetched official evidence attached to the first 3. DeepSeek skipped; no charge.')
        return 0
    key=key_from_windows()
    if not key:
        print('DeepSeek API key not installed. No paid calls made.')
        return 0
    db=sqlite3.connect(data/'deepseek_budget.sqlite',timeout=30)
    db.execute('PRAGMA busy_timeout=30000')
    ledger(db)
    date=datetime.datetime.now().astimezone().date().isoformat()
    output=data/'deepseek_pilot_REVIEW_ONLY.csv'
    try:
        with output.open('a',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=COLUMNS)
            if f.tell()==0:writer.writeheader()
            for row in available:
                cid=candidate_id(row)
                reservation=claim(db,cid,date)
                if reservation is None:
                    print('Already investigated today or daily spending cap reached:',cid);continue
                evidence=byid[cid][:2]
                # No AI-generated contact fields accepted unless directly in official
                # retrieved text, and no AI-generated evidence URL accepted.
                status='ERROR';actual=None;obj={}
                try:
                    obj,usage=request_ai(key,row,evidence)
                    source_text=' '.join(e.get('notes','') for e in evidence).lower()
                    for fld in ('business_email','business_phone','decision_maker',
                                'operating_company','legal_company','franchisee'):
                        value=str(obj.get(fld,'') or '').strip()
                        if value and value.lower() not in source_text:obj[fld]=''
                    allowed={e['url'] for e in evidence}
                    claimed=obj.get('evidence_urls',[])
                    if isinstance(claimed,str):claimed=claimed.split(' | ')
                    obj['evidence_urls']=' | '.join(u for u in claimed if u in allowed)
                    from deepseek_daily import INPUT_RATE_USD_M,OUTPUT_RATE_USD_M
                    actual=(int(usage.get('prompt_tokens',0))*INPUT_RATE_USD_M+int(usage.get('completion_tokens',0))*OUTPUT_RATE_USD_M)/1000000
                    status='REVIEW_REQUIRED_NOT_FOR_SALE'
                except Exception as err:
                    obj={'caveats':type(err).__name__+': '+str(err)[:100]}
                finally:complete(db,reservation,status,actual)
                item={k:obj.get(k,'') for k in COLUMNS}
                item.update(candidate_id=cid,address=row.get('address',''),
                            status=status,researched_at=datetime.datetime.now().isoformat())
                writer.writerow(item);f.flush()
        print('AI pilot finished. All outputs require human validation:',output)
    finally:db.close()
    return 0

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',type=Path,default=ROOT/'data')
    p.add_argument('--max-leads',type=int,default=3)
    p.add_argument('--confirm-paid',action='store_true')
    a=p.parse_args();return investigate(a.data_dir,a.max_leads,a.confirm_paid)
if __name__=='__main__':raise SystemExit(main())
