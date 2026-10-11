"""Evidence-led cross-source matching; exact address is a candidate, not verified identity."""
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
from intelligence_dashboard import connection,rows,safe_url
ROOT=Path(__file__).resolve().parent
def normalize_address(s):
 s=re.sub(r'[^a-z0-9]+',' ',str(s or '').lower()).strip()
 return re.sub(r'\s+',' ',s)
def candidate_key(*items):return hashlib.sha256('|'.join(map(str,items)).encode()).hexdigest()[:24]
def extract(data,max_records=25000,max_results=250):
 b=connection(data/'brampton_sources.sqlite')
 d=connection(data/'business_discovery.sqlite')
 if not b or not d:
  if b:b.close()
  if d:d.close()
  return []
 try:
  business=rows(d,'SELECT source_id,source_key,company_name,address,city FROM observations WHERE address IS NOT NULL AND TRIM(address)<>\'\' LIMIT ?', (max_records,))
  licences=rows(b,"SELECT source_id,record_id,json FROM records WHERE source_id LIKE 'brampton_lic_%' OR source_id='brampton_food_licences_structured' LIMIT ?",(max_records,))
  index={}
  for row in business:
   address=normalize_address(row['address'])
   if len(address)<12:continue
   index.setdefault(address,[]).append(row)
  result=[]
  for r in licences:
   try:obj=json.loads(r['json'] or '{}')
   except (ValueError,TypeError):continue
   if not isinstance(obj,dict):continue
   fields=obj.get('fields') or {}
   if not isinstance(fields,dict):continue
   address=normalize_address(fields.get('business_address'))
   if address not in index:continue
   for other in index[address][:5]:
    evidence_url=safe_url(obj.get('source_url'))
    result.append({'candidate_id':candidate_key(r['source_id'],r['record_id'],other['source_id'],other['source_key']),
     'name_a':str(fields.get('organization_name') or fields.get('operating_name') or ''),'name_b':other['company_name'],
     'shared_address':fields.get('business_address',''),'source_a':r['source_id'],'key_a':r['record_id'],
     'source_b':other['source_id'],'key_b':other['source_key'],
     'evidence_url':evidence_url,'classification':'UNVERIFIED_ADDRESS_MATCH',
     'reason':'Same normalized street address; tenants, subsidiaries or unrelated occupants may share an address',
     'verified_identity':'NO','publication_date_confirmed':'NO'})
    if len(result)>=max_results:return result
  return result
 finally:b.close();d.close()
def run(data):
 matches=extract(data)
 output=data/'relationship_candidates_REVIEW_ONLY.csv'
 output.parent.mkdir(parents=True,exist_ok=True)
 fields=['candidate_id','name_a','name_b','shared_address','source_a','key_a','source_b','key_b','evidence_url','classification','reason','verified_identity','publication_date_confirmed']
 with output.open('w',encoding='utf-8-sig',newline='') as handle:
  writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(matches)
 return {'candidate_count':len(matches),'output':str(output),'verified_links':0}
def main():
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data')
 a=p.parse_args();print(json.dumps(run(a.data_dir),indent=2))
if __name__=='__main__':main()
