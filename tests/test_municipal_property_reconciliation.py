import unittest
from municipal_property_reconciliation import reconcile
class ReconciliationTest(unittest.TestCase):
 def test_two_properties_one_report_stay_separate(self):
  base={"section":1,"event_type":"tax_exemption","organization":"Toronto Community Housing Corporation","organization_role":"owner","stage":"agreement","source_url":"https://www.toronto.ca/report.pdf"}
  rows=[dict(base,address="175 Oak Street",grounded=True,evidence_page=2,evidence_excerpt="175 Oak Street"),
        dict(base,address="130 Augusta Avenue",grounded=True,evidence_page=3,evidence_excerpt="130 Augusta Avenue"),
        dict(base,address="Invented Place",grounded=False,evidence_page=3,evidence_excerpt="fake")]
  r=reconcile(rows)
  self.assertEqual(len(r["properties"]),2)
  self.assertEqual(len(r["unresolved_mentions"]),1)
  self.assertEqual(r["sale_ready"],0)
  self.assertTrue(all(p["supplier_selection"]=="UNKNOWN" for p in r["properties"]))
if __name__=="__main__":unittest.main()
