import csv,tempfile,unittest
from pathlib import Path
from lead_research import research,candidate_id,clean_url
class LeadResearchTests(unittest.TestCase):
 def test_id_deterministic(self):
  r={'source_id':'a','source_key':'b','company_name':'ABC'}
  self.assertEqual(candidate_id(r),candidate_id(r))
 def test_non_http(self):
  self.assertEqual(clean_url('file:///etc/passwd'),'')
 def test_empty(self):
  with tempfile.TemporaryDirectory() as p:
   self.assertEqual(research(Path(p))[0],0)
   self.assertTrue((Path(p)/'lead_research_REVIEW_ONLY.csv').exists())
 def test_explicitly_empty_priority_queue_never_falls_back_to_historical_leads(self):
  with tempfile.TemporaryDirectory() as p:
   d=Path(p)
   with (d/'research_priority_queue.csv').open('w',newline='') as f:
    csv.writer(f).writerow(['opportunity_id','company_name'])
   with (d/'business_leads_REVIEW_ONLY.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['source_id','source_key','company_name'])
    w.writeheader()
    w.writerow({'source_id':'old','source_key':'1','company_name':'Historical'})
   self.assertEqual(research(d)[0],0)
   with (d/'lead_research_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
    self.assertEqual(list(csv.DictReader(f)),[])
 def test_evidence(self):
  with tempfile.TemporaryDirectory() as p:
   p=Path(p);row={'source_id':'s','source_key':'9','company_name':'Example','address':'Toronto'};cid=candidate_id(row)
   with (p/'business_leads_REVIEW_ONLY.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
   evidence={'candidate_id':cid,'url':'https://example.org/contact','source_type':'official_company_contact','contact_email':'info@example.org','contact_phone':'416-555-0100'}
   with (p/'research_sources.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=evidence);w.writeheader();w.writerow(evidence)
   self.assertEqual(research(p)[0],1)
   with (p/'lead_research_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:r=list(csv.DictReader(f))[0]
   self.assertEqual(r['contact_email'],'info@example.org');self.assertEqual(r['confidence'],'SOURCE_ATTACHED_UNVERIFIED')
if __name__=='__main__':unittest.main()
