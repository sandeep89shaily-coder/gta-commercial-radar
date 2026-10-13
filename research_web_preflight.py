"""Free relevance-aware public-web check. Never calls DeepSeek or accesses API keys."""
import re
from urllib.parse import urlparse
from deepseek_research_agent import search_public,read_public_page

ADDRESS='37 Shorncliffe Road'
QUERY='"37 Shorncliffe Road" Toronto development'
ADDRESS_RE=re.compile(r'\b37\s+Shorncliffe\s+(?:Road|Rd\.?|St\.?)\b',re.I)

def main():
 print('GTA COMMERCIAL RADAR - FREE PROJECT RESEARCH VALIDATION',flush=True)
 print('No AI usage; no DeepSeek cost; no ledger changes.',flush=True)
 print('Looking for evidence ABOUT 37 Shorncliffe Road, not just a reachable webpage.',flush=True)
 outcome=search_public(QUERY)
 hits=outcome.get('results',[]) if isinstance(outcome,dict) else outcome
 error=outcome.get('error','') if isinstance(outcome,dict) else ''
 print('Search result count:',len(hits),'provider error:',error or 'none',flush=True)
 if not hits:
  print('FAIL: Search returned no project evidence. Do not run paid AI.',flush=True)
  return 1
 eligible=[]
 for hit in hits:
  title=(hit.get('title') or '')
  snippet=(hit.get('snippet') or '')
  url=hit.get('url') or ''
  relevant=bool(ADDRESS_RE.search(title+' '+snippet+' '+url.replace('-',' ')))
  print('Search hit:',title[:100],'relevant:',relevant,flush=True)
  if relevant and urlparse(url).scheme=='https':
   eligible.append(url)
 if not eligible:
  print('FAIL: No search hit identifies the exact project address. Unrelated web pages are NOT a pass.',flush=True)
  return 1
 for url in eligible[:5]:
  print('Reading candidate:',url[:160],flush=True)
  page=read_public_page(url)
  if not page.get('url'):
   print('Page not usable:',page.get('error','unknown'),flush=True)
   continue
  content=page.get('text','')
  if ADDRESS_RE.search(content):
   print('PASS: Public page actually mentions 37 Shorncliffe Road; ',len(content),'characters retrieved.',flush=True)
   print('Public discovery and relevance verified. This does NOT verify a developer, contact or sale-ready lead.',flush=True)
   return 0
  print('REJECTED: Page does not mention the exact project address.',flush=True)
 print('FAIL: No retrieved page verifies the exact project address. No AI spending recommended.',flush=True)
 return 1

if __name__=='__main__':
 raise SystemExit(main())
