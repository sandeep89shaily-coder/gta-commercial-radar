"""Free public-web reachability check for the research agent. No AI or API key access."""
import sys
from deepseek_research_agent import search_public,read_public_page

def main():
 print('GTA COMMERCIAL RADAR - FREE RESEARCH WEB CHECK',flush=True)
 print('No DeepSeek requests. No AI cost. No research budget ledger changes.',flush=True)
 queries=['37 Shorncliffe Road Toronto industrial self-storage development',
          'City of Toronto development applications']
 checked=0
 for query in queries:
  print('\nSEARCH:',query,flush=True)
  outcome=search_public(query)
  if isinstance(outcome,list):
   outcome={'results':outcome,'error':'Legacy search result format'}
  hits=outcome.get('results') or []
  print('Search results:',len(hits),'error:',outcome.get('error') or 'none',flush=True)
  for hit in hits[:2]:
   url=hit.get('url','')
   if not url:continue
   print('Trying page:',url[:160],flush=True)
   page=read_public_page(url)
   checked+=1
   if page.get('url') and len(page.get('text',''))>=100:
    print('PASS: Retrieved',len(page['text']),'characters from public page.',flush=True)
    print('Diagnosis: Search and page reading are available for this source.',flush=True)
    return 0
   print('Page unavailable:',page.get('error','Insufficient readable page text'),flush=True)
 if checked==0:
  print('FAIL: No searchable HTTPS page URLs were returned.',flush=True)
 else:
  print('FAIL: Search yielded links, but none of the sampled pages were readable.',flush=True)
 print('No AI investigation was attempted or paid for.',flush=True)
 return 1

if __name__=='__main__':
 raise SystemExit(main())
