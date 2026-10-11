import unittest
from unittest.mock import patch
import brampton_network as b
class Response:
 def __init__(self,text):self.text=text;self.url=b.LICENSING_INDEX
class LicensingDiscoveryTests(unittest.TestCase):
 def test_follows_official_index_and_ignores_external_links(self):
  markup='''<html><a href="/EN/Business/Licensing/Pages/Licensed-Animal-Kennels-Doggie-Daycare.aspx">Licensed Animal Kennels or Doggie Daycare</a><a href="https://evil.example/EN/Business/Licensing/Pages/fake.aspx">Licensed Fake</a></html>'''
  with patch.object(b,'get',return_value=Response(markup)):
   links=b.resolve_licence_urls(None)
  self.assertTrue(any(v.endswith('Licensed-Animal-Kennels-Doggie-Daycare.aspx') for v in links.values()))
  self.assertFalse(any('evil.example' in v for v in links.values()))
 def test_stable_kennel_source_identifier(self):
  entries=[x for x in b.SOURCES if 'kennels' in x[0]]
  self.assertEqual(len(entries),1)
  self.assertEqual(entries[0][0],'brampton_lic_licensed_animal_kennels_or_doggie_daycare')
  self.assertTrue(entries[0][3].endswith('Licensed-Animal-Kennels-Doggie-Daycare.aspx'))
if __name__=='__main__':unittest.main()
