import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import brampton_network as b
from bs4 import BeautifulSoup
class BramptonExpansionTests(unittest.TestCase):
 def test_source_ids_unique(self):
  ids=[x[0] for x in b.SOURCES]
  self.assertEqual(len(ids),len(set(ids)))
 def test_official_road_host(self):
  self.assertEqual(len([x for x in b.SOURCES if x[0].startswith('brampton_roadworks_')]),5)
  self.assertTrue(all('maps1.brampton.ca' in x[3] for x in b.SOURCES if x[0].startswith('brampton_roadworks_')))
 def test_license_column_order(self):
  h='''<table><tr><th>Classification</th><th>Business Address</th><th>Organization Name</th><th>Contractor Operating Name</th><th>Expiry Date</th><th>File Number</th></tr><tr><td>Food</td><td>123 Main St</td><td>123 Ontario Inc</td><td>Sample Cafe</td><td>2027-01-01</td><td>ABC 123</td></tr></table>'''
  got=b.parse_extended_table(BeautifulSoup(h,'html.parser').table)
  self.assertEqual(got[0]['business_address'],'123 Main St')
  self.assertEqual(got[0]['file_number'],'ABC 123')
 def test_no_bad_license(self):
  self.assertEqual(b.parse_extended_table(BeautifulSoup('<table><tr><td>Unknown</td></tr></table>','html.parser').table),[])
if __name__=='__main__':unittest.main()
