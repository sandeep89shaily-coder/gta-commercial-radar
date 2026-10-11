import json
import tempfile
import unittest
from pathlib import Path
from toronto_catalog_audit import catalog_changes, store_history

class TorontoCatalogHistoryTests(unittest.TestCase):
 def test_baseline_creates_no_new_business_events(self):
  current=[{'package_id':'1','title':'New data','url':'https://open.toronto.ca/a'}]
  self.assertEqual(catalog_changes(None,current,'now'),[])
 def test_detects_new_changed_and_missing_only_as_publication_metadata(self):
  old=[{'package_id':'x','title':'Old','resource_ids':'a','modified':'1'},
       {'package_id':'z','title':'Unlisted','resource_ids':'b','modified':'1'}]
  new=[{'package_id':'x','title':'Old','resource_ids':'a,c','modified':'2'},
       {'package_id':'y','title':'Published','resource_ids':'new','modified':'2'}]
  events=catalog_changes(old,new,'today')
  statuses={e['package_id']:e['event_type'] for e in events}
  self.assertEqual(statuses,{'x':'CATALOGUE_METADATA_CHANGED','y':'NEW_CATALOGUE_ENTRY',
                             'z':'NOT_LISTED_IN_CURRENT_CATALOGUE'})
  self.assertNotIn('DELETED',statuses['z'])
  self.assertIn('resource_ids',next(e['details'] for e in events if e['package_id']=='x'))
 def test_journal_retry_deduplicated_but_reversion_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/'history.jsonl'
   event={'package_id':'x','title':'X','event_type':'CATALOGUE_METADATA_CHANGED',
          'details':{'modified':{'before':'a','after':'b'}},'observed_at':'time1'}
   self.assertEqual(store_history(target,[event]),1)
   self.assertEqual(store_history(target,[{**event,'observed_at':'time2'}]),0)
   inverse={**event,'details':{'modified':{'before':'b','after':'a'}},'observed_at':'time3'}
   self.assertEqual(store_history(target,[inverse]),1)
   self.assertEqual(store_history(target,[{**event,'observed_at':'time4'}]),1)
   lines=[json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
   self.assertEqual(len(lines),3)
if __name__=='__main__':unittest.main()
