import json,tempfile,unittest
from pathlib import Path
from municipal_evidence_graph import graph
class ProcurementGraphTest(unittest.TestCase):
 def test_official_tender_address_link_stays_unverified(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/"tenders.json"
   f.write_text(json.dumps({"records":[{"document_number":"1234567890",
    "status":"OPEN","buyer_name_official_publication":"City Buyer",
    "buyer_email_official_publication":"buyer@toronto.ca",
    "title":"175 Oak Street chilled water plant upgrades",
    "description":"Facilities refurbishment","source_url":"https://secure.toronto.ca/odata"}]}))
   data=graph(project_address="175 Oak Street",procurement=f)
   self.assertEqual(len(data["edges"]),1)
   self.assertFalse(data["edges"][0]["verified"])
   self.assertEqual(data["sale_ready_opportunities"],0)
   entry=next(x for x in data["nodes"] if x["id"].startswith("tender_"))
   self.assertFalse(entry["current_status_rechecked"])
 def test_prevent_substring_wrong_street_number(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/"tenders.json"
   f.write_text(json.dumps({"records":[{"document_number":"1234567890",
    "title":"1175 Oak Street facilities","source_url":"https://secure.toronto.ca/odata"}]}))
   data=graph(project_address="175 Oak Street",procurement=f)
   self.assertEqual(data["edges"],[])
if __name__=="__main__":unittest.main()
