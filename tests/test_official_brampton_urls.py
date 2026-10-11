import unittest
import brampton_network as b
class OfficialSourceUrlTests(unittest.TestCase):
 def test_known_official_sources(self):
  sources={row[0]:row for row in b.SOURCES}
  self.assertEqual(sources['brampton_lic_licensed_plumbing_contractors'][3],
   'https://www.brampton.ca/EN/Business/Licensing/Pages/Licensed-Contractors-Plumbing.aspx')
  self.assertEqual(sources['brampton_procurement_content'][3],
   'https://www.brampton.ca/EN/Business/Doing-Business-with-the-City/Pages/Understanding-Procurement.aspx')
if __name__=='__main__':unittest.main()
