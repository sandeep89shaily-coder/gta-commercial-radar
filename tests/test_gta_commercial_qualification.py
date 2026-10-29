import datetime as dt,json,tempfile,unittest
from pathlib import Path
from gta_commercial_qualification import classify,rank,create,qualify_private
class QualificationTests(unittest.TestCase):
 def test_old_open_not_actionable(self):
  r={"document_number":"1234567890","title":"HVAC work","temporal_review":"PAST_CLOSING_DATE_STALE_OPEN_STATUS","closing_date":"2010-11-24"}
  self.assertIsNone(rank(r,as_of=dt.date(2026,10,29)))
 def test_source_candidate_not_private_verified(self):
  r={"document_number":"1234567890","title":"Fire alarm upgrades",
   "closing_date":"2026-11-20","temporal_review":"FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION",
   "buyer_email_official_publication":"procurement@toronto.ca"}
  result=rank(r,as_of=dt.date(2026,10,29))
  self.assertIn("Security / fire protection",result["service_categories"])
  self.assertFalse(result["sale_ready"])
  self.assertFalse(result["private_project_opportunity"])
 def test_insufficient_dossier_never_promotes(self):
  candidate={"verified":{x:True for x in (
   "project_source","project_identity","scope_evidence","buyer_org_evidence",
   "buying_authority_evidence","contact_route_evidence","procurement_evidence",
   "source_first_publication","radar_first_observed")},
   "supplier_status":"UNKNOWN"}
  self.assertFalse(qualify_private(candidate)["sale_ready"])
 def test_board_writes_json_and_csv(self):
  with tempfile.TemporaryDirectory() as t:
   inp=Path(t)/"in.json";inp.write_text(json.dumps({"status":"FETCHED","complete":True,
    "records":[{"document_number":"1234567890","title":"Industrial refrigeration",
    "closing_date":"2026-12-01","temporal_review":"FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION"}]}))
   result=create(inp,Path(t)/"board.json",as_of=dt.date(2026,10,29))
   self.assertEqual(result["relevant_trade_candidates"],1)
   self.assertTrue((Path(t)/"board.csv").exists())
if __name__=="__main__":unittest.main()
