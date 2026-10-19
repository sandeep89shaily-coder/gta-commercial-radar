import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from lead_qualification import grade, source_tier, official
import v8_deepseek_native as v8
import v6_daily_pipeline as v6

ROW={'project_id':'test-project','address':'1430 Birchmount Road, Toronto, ON',
     'source_id':'toronto_active_building_permits','source_keys':'24 101010',
     'company_name':'', 'description':'Commercial fit-out under review',
     'city':'Toronto','lane':'PERMIT_REVIEW','review_priority':'70',
     'current_source_status':'Under review'}

class EvidenceQualificationTests(unittest.TestCase):
    def test_no_proof_not_sale_ready(self):
        result=grade(ROW,{'buyer_fit':'HVAC'},[])
        self.assertEqual(result['lead_maturity'],'SOURCE_RECORD_OBSERVED')
        self.assertEqual(result['sale_ready'],'NO')
    def test_official_page_supports_project(self):
        pages=[{'url':'https://www.toronto.ca/city-government/planning-development/','text':'1430 Birchmount Road permit'}]
        self.assertEqual(source_tier(pages)[0],'OFFICIAL_PAGE_MATCHED')
        self.assertEqual(grade(ROW,{},pages)['lead_maturity'],'PROJECT_EVIDENCE_FOUND')
    def test_contact_requires_company_and_contact_on_public_page(self):
        pages=[{'url':'https://developer.example/projects','text':'Primepoint Developments contact 416-555-1234'}]
        answer={'operator':'Primepoint Developments','contact':'416-555-1234',
                'buyer_fit':'Security access installation'}
        self.assertEqual(grade(ROW,answer,pages)['lead_maturity'],'PUBLIC_OPERATOR_CONTACT_IDENTIFIED')
        self.assertEqual(grade(ROW,{**answer,'contact':'not@listed.com'},pages)['lead_maturity'],
                         'PROJECT_AND_OPERATOR_IDENTIFIED')
        self.assertFalse(official('https://not-toronto.ca'))
    def test_native_search_uses_relevance_before_fetching(self):
        with tempfile.TemporaryDirectory() as folder:
            db=v8.v5._ledger(Path(folder)/'budget.sqlite')
            fetched=[]
            def fake(path,payload):
                if path.endswith('search'):
                    return {'results':[
                        {'url':'https://irrelevant.example/a','title':'Holiday sale','snippet':'vacation',
                         'summary':'Cheap holidays','content':'','rerank_score':3},
                        {'url':'https://developer.example/project','title':'1430 Birchmount Road Toronto','snippet':'Industrial property development',
                         'summary':'Commercial project at 1430 Birchmount Road','content':'','rerank_score':1},
                    ]}
                if path.endswith('fetch'):
                    fetched.append(payload['url'])
                    return {'title':'Building project','content':'1430 Birchmount Road Toronto development'}
                self.fail('No model request expected')
            evidence, counts=v8.fetch_native(ROW,'test',db,'2026-10-19',0,fake)
            db.close()
            self.assertEqual(fetched,['https://developer.example/project'])
            self.assertEqual(counts['fetch'],1)
            self.assertEqual(len(evidence),1)
    def test_preserve_evidence_when_deepseek_omits_url(self):
        evidence=[{'url':'https://developer.example/project',
                   'text':'1430 Birchmount Road Toronto - Primepoint Ltd contractor 416-555-1234'}]
        def fake(path,payload):
            self.assertEqual(path,'/chat/completions')
            return {'choices':[{'finish_reason':'stop','message':{'content':
                     '{"operator":"Primepoint Ltd","developer":"", "contact":"416-555-1234",'
                     '"project_stage":"Under review","buyer_fit":"Fit-out potential",'
                     '"source_urls":[],"next_verification":"Check contractor schedule"}'}}],
                    'usage':{'prompt_tokens':150,'completion_tokens':80}}
        result,actual=v8.analyze(ROW,evidence,'key',fake)
        self.assertEqual(result['source_urls'],'https://developer.example/project')
        self.assertEqual(result['evidence_level'],'FETCHED_PAGE_MATCHED')
        self.assertEqual(result['operator'],'Primepoint Ltd')
    def test_deferred_projects_are_not_shown_as_actionable(self):
        with tempfile.TemporaryDirectory() as f:
            out=Path(f);state={'status':'SUCCESS','investigation_date':'2026-10-19','steps':[]}
            cols=['project_id','address','status','lead_maturity','caveats','source_urls']
            with (out/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv').open('w',newline='') as fp:
                w=csv.DictWriter(fp,fieldnames=cols);w.writeheader()
                w.writerow(dict(project_id='wait',address='Unverified street',status='AI_BUDGET_DEFERRED',
                                lead_maturity='SOURCE_RECORD_OBSERVED',caveats='None',source_urls=''))
            page=v6.render_dashboard(out,state).read_text()
            self.assertIn('automatic',page)
            self.assertNotIn('Manual verification needed',page)
            self.assertNotIn('<h3>Unverified street</h3>',page)

if __name__=='__main__':unittest.main()
