import unittest,tempfile,csv,hashlib
from pathlib import Path
from unittest.mock import patch
from toronto_ai_same_day_recovery import recover
class RecoveryTest(unittest.TestCase):
 def test_one_recovery_with_prior_unknown_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/"saved.pdf";p.write_bytes(b"fixture")
   audit=root/"VERIFIED_REPORT_FETCH_AUDIT.csv"
   url="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf"
   sha=hashlib.sha256(p.read_bytes()).hexdigest()
   with audit.open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["attachment_url","status","saved_path","sha256"]);w.writeheader()
    w.writerow(dict(attachment_url=url,status="CAPTURED",saved_path=str(p),sha256=sha))
   ledger={"status":"READ_ONLY_DIAGNOSTIC","budget_allows_new_request":True,
           "municipal_attempts":[{"id":"municipal_report_compact_v2_"+hashlib.sha256((sha+url).encode()).hexdigest()[:24],"status":"UNKNOWN"}]}
   with patch("toronto_ai_same_day_recovery.diagnose",return_value=ledger),patch("toronto_ai_same_day_recovery.analyze") as ai:
    no=recover(root,root,audit=audit)
    self.assertEqual(no["status"],"READY_FOR_ONE_RECOVERY")
    ai.return_value={"status":"AI_REVIEW_ONLY_NOT_SALE_READY","paid_ai_calls":1,"supported_claims":1}
    yes=recover(root,root,audit=audit,paid=True)
    self.assertEqual(yes["status"],"AI_REVIEW_ONLY_NOT_SALE_READY")
    self.assertEqual(ai.call_args.kwargs["retry_version"],"one_approved_nonthinking_v4")
 def test_v4_already_attempted_blocks_without_call(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/"saved.pdf";p.write_bytes(b"fixture")
   audit=root/"VERIFIED_REPORT_FETCH_AUDIT.csv"
   url="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf"
   sha=hashlib.sha256(p.read_bytes()).hexdigest()
   with audit.open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["attachment_url","status","saved_path","sha256"]);w.writeheader()
    w.writerow(dict(attachment_url=url,status="CAPTURED",saved_path=str(p),sha256=sha))
   ledger={"status":"READ_ONLY_DIAGNOSTIC","budget_allows_new_request":True,
      "municipal_attempts":[{"id":"municipal_report_nonthinking_v4_"+hashlib.sha256((sha+url).encode()).hexdigest()[:24],"status":"UNKNOWN"}]}
   with patch("toronto_ai_same_day_recovery.diagnose",return_value=ledger),patch("toronto_ai_same_day_recovery.analyze") as ai:
    self.assertEqual(recover(root,root,audit=audit,paid=True)["status"],"SAME_DAY_RECOVERY_ALREADY_ATTEMPTED")
    ai.assert_not_called()
if __name__=="__main__":unittest.main()
