import csv
import json
import tempfile
import unittest
from pathlib import Path
from early_purchase_queue import compile_sources,qualify,export
import early_investment_radar as radar

class EarlyPurchaseTests(unittest.TestCase):
    def test_require_postbaseline_and_company_for_funded_investment(self):
        sample=dict(source_id='feddev_investment',record_id='official#company',change_type='NEW',
            description='Brampton factory manufacturing expansion through new CNC equipment',
            company='Example Manufacturing',source_url='https://www.canada.ca/approved',commercial_fit='REVIEW')
        self.assertEqual(qualify(sample),'')
        self.assertEqual(qualify(dict(sample,company='')),'COMPANY_NOT_IDENTIFIED_IN_INDEX')
        self.assertEqual(qualify(dict(sample,commercial_fit='LOW')),'COMMERCIAL_FIT_NOT_ESTABLISHED')
        self.assertEqual(qualify(dict(sample,change_type='BASELINE')),'NOT_NEW_OR_CHANGED')
        self.assertEqual(qualify(dict(sample,source_id='industrial_property_watch')),'CONTEXT_ONLY_REVIEW')
    def test_live_observation_only_and_separate_review_queue(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'EARLY_INVESTMENT_SOURCE_STATUS.csv').write_text(
                'source_id,status\nfeddev_investment,SUCCESS\n',encoding='utf-8')
            (root/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').write_text(
                'source_id,record_id,change_type,observed_at,company,description,source_url,commercial_fit\n'
                'feddev_investment,a,NEW,2026-10-25T11:01:00Z,Demo Factory,Brampton factory new CNC equipment,https://www.canada.ca/a,REVIEW\n'
                'feddev_investment,b,NEW,2026-10-24T11:01:00Z,Old Factory,Brampton new plant,https://www.canada.ca/b,REVIEW\n',encoding='utf-8')
            accepted,gaps=compile_sources(root,set(),'2026-10-25T11:00:00Z')
            self.assertEqual(len(accepted),1)
            self.assertEqual(accepted[0]['procurement_status'],'UNKNOWN')
            self.assertEqual(accepted[0]['company_name'],'Demo Factory')
            self.assertEqual(len(gaps),0)
            path=export(root,accepted,gaps)
            self.assertTrue(path.exists())
    def test_no_core_collection_and_paid_research_only_with_explicit_option(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);data=root/'data';out=root/'out'
            seen=[];paid=[]
            def collect(name,command):
                seen.append(name)
                if name=='investment_cues':
                    out.mkdir(parents=True,exist_ok=True)
                    (out/'EARLY_INVESTMENT_SOURCE_STATUS.csv').write_text(
                        'source_id,status,fetched,new,updated\nfeddev_investment,SUCCESS,1,1,0\n'
                        'investontario_investment,SUCCESS,0,0,0\n'
                        'corporate_capex_watch,SUCCESS,0,0,0\n'
                        'industrial_property_watch,SUCCESS,0,0,0\n',encoding='utf-8')
                    (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').write_text(
                        'source_id,record_id,change_type,observed_at,company,description,source_url,commercial_fit\n'
                        'feddev_investment,id,NEW,2099-10-25T13:00:00Z,Acme,Brampton factory equipment expansion,https://www.canada.ca/id,REVIEW\n',encoding='utf-8')
                return {'step':name,'status':'SUCCESS','exit_code':0}
            a=radar.run(data,out,collector=collect,paid=False)
            self.assertEqual(len(seen),10)
            self.assertNotIn('municipal_collector',seen)
            self.assertNotIn('business_collector',seen)
            self.assertEqual(a['ai_status'],'DISABLED_FREE_RUN')
            self.assertTrue((out/radar.REPORT).is_file())
            self.assertTrue((out/'GTA_RADAR_EARLY_SOURCES.csv').is_file())
            self.assertEqual(len(paid),0)
if __name__=='__main__':unittest.main()

class EarlyInvestmentEvidenceTests(unittest.TestCase):
    def test_direct_official_article_with_named_company_is_source_evidence(self):
        import v8_deepseek_native as v8
        row={'source_id':'feddev_investment','company_name':'Example Factory',
             'record_source_url':'https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/example.html'}
        self.assertTrue(v8.matches(row,'Example Factory will invest in manufacturing equipment',
                                   row['record_source_url']))
        self.assertFalse(v8.matches(row,'Example Factory is a supplier of bolts',row['record_source_url']))
        self.assertFalse(v8.matches(row,'Example Factory will invest in production equipment','https://example.com/a'))
    def test_investment_research_queries_use_company_not_backgrounder_url(self):
        import v8_deepseek_native as v8
        row={'source_id':'feddev_investment','company_name':'Example Manufacturing',
             'source_keys':'https://www.canada.ca/some/backgrounder#recipient-example'}
        q=v8.queries(row)
        self.assertTrue(q)
        self.assertTrue(all('Example Manufacturing' in x and 'https' not in x for x in q))
