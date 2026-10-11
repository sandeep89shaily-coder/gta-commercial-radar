import sqlite3
import unittest
from unittest.mock import Mock
from mississauga_procurement import (parse_legacy,monitor_page,collect,setup_monitors,
                                     SOURCES,valid)

HTML='''<html><table>
<tr><td>PRC005419 - Cooling loop chemical services</td>
<td>Open</td><td>Oct 27, 2026</td>
<td><a href="/Module/Tenders/en/Tender/Detail/348438bb-1617-4f51-83e8-fbc472953470">Bid Details - PRC005419 - Cooling loop chemical services</a></td></tr>
<tr><td>PRC005569 - Utility Locate Services</td><td>Closed</td>
<td><a href="/Module/Tenders/en/Tender/Detail/5eeda84f-1fff-488c-8d19-07d251f799c3">Bid Details - PRC005569 - Utility Locate Services</a></td></tr>
</table></html>'''
class MississaugaProcurementTests(unittest.TestCase):
 def test_parse_official_public_bid_links(self):
  portal=SOURCES[0]
  rows=parse_legacy(HTML,portal['url'])
  self.assertEqual([r['BID_NUMBER'] for r in rows],['PRC005419','PRC005569'])
  self.assertEqual(rows[0]['STATUS'],'OPEN')
  self.assertEqual(rows[1]['STATUS'],'CLOSED')
  self.assertTrue(all('mississauga.bidsandtenders.ca' in r['DETAIL_URL'] for r in rows))
 def test_host_restriction_and_unlisted_notice(self):
  self.assertFalse(valid('https://mississauga.bidsandtenders.ca.evil.test/Module/Tenders/Detail/0',
                         'mississauga.bidsandtenders.ca'))
  bad='''<a href="https://other.example/Module/Tenders/en/Tender/Detail/danger">Bid Details - PRC00001</a>'''
  self.assertEqual(parse_legacy(bad,SOURCES[0]['url']),[])
 def test_page_monitor_is_baseline_then_change(self):
  db=sqlite3.connect(':memory:')
  setup_monitors(db)
  source=SOURCES[1]
  status,changed=monitor_page(db,source,'<html>Current Bonfire portal</html>','day1',0)
  self.assertEqual(status,'PUBLIC_PAGE_ONLY')
  self.assertTrue(changed)
  _,changed=monitor_page(db,source,'<html>Current Bonfire portal</html>','day2',0)
  self.assertFalse(changed)
  _,changed=monitor_page(db,source,'<html>New public message</html>','day3',0)
  self.assertTrue(changed)
  self.assertEqual(db.execute('SELECT COUNT(*) FROM public_page_versions').fetchone()[0],2)
  self.assertEqual(db.execute('SELECT COUNT(*) FROM changes').fetchone()[0],0)
  db.close()
 def test_refuse_unexpected_document_type(self):
  class Http:
   def get(self,url,**kwargs):
    return Mock(content=b'%PDF-1.7',text='PDF',headers={'Content-Type':'application/pdf'})
  with self.assertRaisesRegex(ValueError,'Expected public HTML'):
   collect(Http(),SOURCES[0])
 def test_migration_keeps_both_portals(self):
  self.assertEqual({r['id'] for r in SOURCES},
   {'mississauga_bidsandtenders_legacy','mississauga_bonfire_public'})
if __name__=='__main__':unittest.main()
