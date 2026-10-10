"""DeepSeek-only evidence review with conservative daily reserved budget.
No autonomous paid web search and no invented contacts.
"""
import csv, datetime, json, os, sqlite3, subprocess, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
BUDGET=0.50
MAX_LEADS=50
# Deliberately conservative upper-bound rates for this single supported model.
# Before any provider price change, owner must validate these bounds remain safe.
MODEL='deepseek-flash'
INPUT_RATE_USD_M=1.00
OUTPUT_RATE_USD_M=4.00
MAX_OUTPUT_TOKENS=850
MAX_INPUT_TOKENS=3600
RESERVE_USD=round((MAX_INPUT_TOKENS*INPUT_RATE_USD_M+MAX_OUTPUT_TOKENS*OUTPUT_RATE_USD_M)/1_000_000,6)
API='https://api.deepseek.com/chat/completions'

def key_from_windows():
    k=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if k:return k
    path=ROOT/'settings'/'deepseek_key.dpapi'
    if os.name!='nt' or not path.is_file():return ''
    script=("$ErrorActionPreference='Stop';$s=Get-Content -Raw -LiteralPath '"+str(path).replace("'","''")+"' | ConvertTo-SecureString;"
            "$p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}")
    r=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=20)
    return r.stdout.strip() if r.returncode==0 else ''

def ledger(db):
    db.execute('PRAGMA busy_timeout=30000')
    db.execute('CREATE TABLE IF NOT EXISTS spends (id INTEGER PRIMARY KEY, date TEXT NOT NULL, candidate TEXT NOT NULL, reserved REAL NOT NULL, actual REAL, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    db.commit()

def claim(db,candidate,day):
    db.execute('BEGIN IMMEDIATE')
    spent=db.execute('SELECT COALESCE(SUM(reserved),0),COUNT(*) FROM spends WHERE date=?',(day,)).fetchone()
    previous=db.execute("SELECT COUNT(*) FROM spends WHERE date=? AND candidate=?",(day,candidate)).fetchone()[0]
    if previous or spent[1]>=MAX_LEADS or spent[0]+RESERVE_USD>BUDGET+1e-10:
        db.rollback();return None
    cur=db.execute('INSERT INTO spends(date,candidate,reserved,status) VALUES(?,?,?,?)',(day,candidate,RESERVE_USD,'RESERVED'))
    db.commit();return cur.lastrowid

def complete(db,id,status,actual=None):
    db.execute('UPDATE spends SET status=?,actual=? WHERE id=?',(status,actual,id));db.commit()

def request_ai(key,candidate,evidence):
    system='Return JSON ONLY with keys operating_company,legal_company,franchisee,decision_maker,decision_maker_role,business_email,business_phone,evidence_urls,caveats. Use ONLY provided evidence; unknown as empty strings; never guess any email, telephone, person, franchisee or company. All output requires human review.'
    msg=json.dumps({'candidate':candidate,'evidence':evidence},ensure_ascii=False)
    # Hard preflight based on UTF-8 bytes: >=4 bytes/token is NOT a guaranteed upper bound;
    # using character count as 1 token/character is conservative for typical English but
    # unusual Unicode can exceed; reject non-ASCII before dispatch to enforce more safety.
    msg=msg.encode('ascii','backslashreplace').decode('ascii')
    if len(system)+len(msg)>MAX_INPUT_TOKENS:msg=msg[:MAX_INPUT_TOKENS-len(system)-80]
    payload={'model':MODEL,'messages':[{'role':'system','content':system},{'role':'user','content':msg}],
             'response_format':{'type':'json_object'},'max_tokens':MAX_OUTPUT_TOKENS,'stream':False}
    body=json.dumps(payload).encode('utf-8')
    req=Request(API,data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=75) as res: result=json.load(res)
    ch=result['choices'][0];usage=result.get('usage',{})
    if ch.get('finish_reason')=='length':raise ValueError('Truncated response; cannot use')
    obj=json.loads(ch['message']['content']);return obj,usage

def main():
    DATA.mkdir(exist_ok=True)
    key=key_from_windows()
    if not key:
        print('DeepSeek key not configured. AI skipped. Collection remains available.');return 0
    # Only use evidence already collected by permitted sources. No Brave or OpenAI calls.
    infile=DATA/'autonomous_evidence_REVIEW_ONLY.csv'
    candidates_file=DATA/'lead_research_REVIEW_ONLY.csv'
    if not infile.exists() or not candidates_file.exists():
        print('No candidate evidence yet. AI skipped without cost.');return 0
    with infile.open(encoding='utf-8-sig',newline='') as f:ev=list(csv.DictReader(f))
    with candidates_file.open(encoding='utf-8-sig',newline='') as f:cs=list(csv.DictReader(f))
    byid={}
    for e in ev:
        if e.get('source_type')=='search_result_unverified':continue
        if not e.get('url'):continue
        byid.setdefault(e.get('candidate_id',''),[]).append(e)
    db=sqlite3.connect(DATA/'deepseek_budget.sqlite',timeout=30)
    try:
        ledger(db);day=datetime.datetime.now().astimezone().date().isoformat()
        out=DATA/'deepseek_results_REVIEW_ONLY.csv'
        columns=['candidate_id','company','status','operating_company','legal_company','franchisee','decision_maker','decision_maker_role','business_email','business_phone','evidence_urls','caveats','researched_at']
        finished=0
        with out.open('a',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=columns)
            if f.tell()==0:w.writeheader()
            for c in cs:
                if finished>=MAX_LEADS:break
                cid=c.get('candidate_id','');evidence=byid.get(cid,[])[:8]
                if not cid or not evidence:continue
                ident=claim(db,cid,day)
                if ident is None:
                    budget_count=db.execute('SELECT COALESCE(SUM(reserved),0),COUNT(*) FROM spends WHERE date=?',(day,)).fetchone()
                    if budget_count[0]+RESERVE_USD>BUDGET or budget_count[1]>=MAX_LEADS:
                        print('Daily budget or 50-lead cap reached. Stopping safely.');break
                    continue
                status='ERROR';obj={};actual=None
                try:
                    obj,usage=request_ai(key,c,evidence)
                    # Never accept contacts not explicitly present in observed evidence fields.
                    sources=' '.join((v.get('contact_email','')+' '+v.get('contact_phone','')+' '+v.get('notes','')) for v in evidence).lower()
                    for field in ('business_email','business_phone'):
                        if obj.get(field) and str(obj[field]).lower() not in sources:obj[field]=''
                    evidence_urls={v.get('url','') for v in evidence}
                    claimed=obj.get('evidence_urls',[])
                    if isinstance(claimed,str):claimed=[x.strip() for x in claimed.split('|')]
                    obj['evidence_urls']=' | '.join(x for x in claimed if x in evidence_urls)
                    # Preserve reservation, even when actual charge is smaller, as safety buffer.
                    actual=(int(usage.get('prompt_tokens',0))*INPUT_RATE_USD_M+int(usage.get('completion_tokens',0))*OUTPUT_RATE_USD_M)/1e6
                    status='REVIEW_REQUIRED'
                except Exception as ex:
                    obj={'caveats':type(ex).__name__+': '+str(ex)[:120]}
                finally:
                    complete(db,ident,status,actual)
                row={k:'' for k in columns};row.update({k:obj.get(k,'') for k in columns if k in obj})
                row.update(candidate_id=cid,company=c.get('candidate_company',''),status=status,researched_at=datetime.datetime.now().isoformat())
                w.writerow(row);f.flush();finished+=1
        used=db.execute('SELECT COALESCE(SUM(reserved),0) FROM spends WHERE date=?',(day,)).fetchone()[0]
        print(f'DeepSeek: {finished} investigations attempted today in this run. USD ${used:.4f}/${BUDGET:.2f} reserved for today.')
        print('Results:',out)
    finally:db.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
