"""Offline-only tests: the Google pilot never contacts Google during CI."""
import csv,datetime as dt,json,sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
import gta_google_grounding_pilot as pilot

def write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)

class GoogleGroundingPilotTests(unittest.TestCase):
    def seed(self,root,n=12):
        rows=[dict(project_id="municipal:"+str(i),address=str(i)+" Main St",
                   city="Brampton",description="New industrial workshop "+str(i),
                   source_record_date="2026-10-30",record_source_url="https://www.brampton.ca/",
                   observation="FIRST_OBSERVED" if i<9 else "RECORD_CHANGED",
                   review_priority=str(80-i)) for i in range(n)]
        write(root/pilot.SOURCE,rows)
        write(root/pilot.AI_SOURCE,[dict(project_id="municipal:0",
            status="AI_EVIDENCE_REVIEW",investigated_local_date="2026-11-01")])
        return rows
    def response(self,query="industrial project"):
        return {"status":"completed","steps":[
            {"type":"google_search_call","arguments":{"queries":[query]}},
            {"type":"model_output","content":[{"type":"text",
                "text":"Warehouse expansion, stage unverified; see cited page.",
                "annotations":[{"type":"url_citation","url":"https://www.brampton.ca/project"}]}]}],
            "usage":{"total_input_tokens":1200,"total_output_tokens":360,"total_thought_tokens":10}}
    def test_dry_run_does_not_create_ledger_or_make_api_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root)
            called=[]
            report=pilot.run(root,transport=lambda p:called.append(p),today=dt.date(2026,11,1))
            self.assertEqual(report["status"],"PREVIEW_ONLY_NO_PAID_CALLS")
            self.assertEqual(report["projects_selected"],10)
            self.assertFalse(called)
            self.assertFalse((root/pilot.LEDGER).exists())
    def test_paid_is_explicit_keeps_annotations_and_compares_deepseek(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,2)
            sent=[]
            result=pilot.run(root,paid=True,key="fake-test",limit=2,
                             today=dt.date(2026,11,1),
                             transport=lambda p:(sent.append(p) or self.response()))
            self.assertEqual(result["projects_queried"],2)
            self.assertEqual(len(sent),2)
            self.assertEqual(sent[0]["tools"],[{"type":"google_search"}])
            self.assertIn("construction",sent[0]["input"].lower())
            with Path(result["csv"]).open(encoding="utf-8-sig",newline="") as f:
                records=list(csv.DictReader(f))
            self.assertEqual(records[0]["google_source_urls"],"https://www.brampton.ca/project")
            self.assertEqual(records[0]["deepseek_research_status"],"AI_EVIDENCE_REVIEW")
            self.assertEqual(records[0]["google_search_queries"],"industrial project")
            self.assertTrue((root/pilot.LEDGER).exists())
            self.assertLessEqual(result["monthly_estimated_or_reserved_usd"],5.0)
            again=pilot.run(root,paid=True,key="fake-test",limit=2,
                            today=dt.date(2026,11,1),
                            transport=lambda _:self.fail("Duplicate Google request"))
            self.assertEqual(again["projects_queried"],0)
    def test_failure_keeps_unknown_cost_reservation_and_prevents_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,1)
            fail=pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                transport=lambda _:(_ for _ in ()).throw(TimeoutError("unknown charge")))
            self.assertEqual(fail["projects_queried"],0)
            self.assertEqual(fail["monthly_estimated_or_reserved_usd"],0.5)
            with closing(sqlite3.connect(root/pilot.LEDGER)) as db:
                self.assertEqual(db.execute("SELECT status FROM google_pilot").fetchone()[0],
                                 "UNKNOWN_PROVIDER_CHARGE")
            safe=pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                 transport=lambda _:self.fail("No retried charge"))
            self.assertEqual(safe["projects_queried"],0)
    def test_cap_is_ten_projects_even_if_cost_below_five(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,12)
            calls=[]
            pilot.run(root,paid=True,key="test",today=dt.date(2026,11,1),
                      transport=lambda payload:(calls.append(payload) or self.response()))
            self.assertEqual(len(calls),10)
            self.assertEqual(len(pilot.candidates(root/pilot.SOURCE)),10)
    def test_interactions_api_single_query_and_provider_grounding_count(self):
        response={"status":"completed","steps":[
            {"type":"google_search_call","arguments":{"query":"warehouse Toronto"}},
            {"type":"model_output","content":[{"type":"text","text":"New warehouse",
                "annotations":[{"type":"url_citation","url":"https://www.toronto.ca/project"}]}]}],
            "usage":{"total_input_tokens":1000,"total_output_tokens":250,
                     "grounding_tool_count":[{"type":"google_search","count":3}]}}
        data=pilot.extract(response)
        self.assertEqual(data["queries"],["warehouse Toronto"])
        self.assertEqual(data["sources"],["https://www.toronto.ca/project"])
        self.assertGreaterEqual(data["estimated_usd"],3*pilot.GROUNDING_PER_QUERY_USD)
    def test_diagnostic_is_read_only_and_does_not_generate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            called=[]
            result=pilot.diagnose_key("test-only",transport=lambda url,key:
                (called.append((url,key)) or {"name":"models/gemini-3.1-flash-lite"}))
            self.assertEqual(result["status"],"MODEL_LOOKUP_OK")
            self.assertTrue(result["no_paid_calls"])
            self.assertEqual(len(called),1)
            self.assertIn("/models/gemini-3.1-flash-lite",called[0][0])
            self.assertFalse((root/pilot.LEDGER).exists())
    def test_ten_project_paid_batch_stops_after_one_failed_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,10)
            attempted=[]
            def fail(_payload):
                attempted.append(True)
                raise TimeoutError("Unknown charge; stop further requests")
            result=pilot.run(root,paid=True,key="test-only",limit=10,
                today=dt.date(2026,11,1),transport=fail)
            self.assertEqual(len(attempted),1)
            self.assertEqual(result["status"],"GOOGLE_FAILED_STOPPED_SAFELY")
            self.assertEqual(result["failed_requests"],1)
            self.assertEqual(result["skipped_after_failure"],9)
            self.assertEqual(result["monthly_estimated_or_reserved_usd"],0.50)
    def test_http_error_details_hide_key(self):
        from io import BytesIO
        from urllib.error import HTTPError
        raw=b'{"error":{"status":"PERMISSION_DENIED","message":"Bad key PRIVATEKEY: check billing"}}'
        error=HTTPError("https://example.com",403,"Forbidden",None,BytesIO(raw))
        details=pilot.google_error_details(error,"PRIVATEKEY")
        self.assertEqual(details["http_status"],403)
        self.assertEqual(details["google_error_status"],"PERMISSION_DENIED")
        self.assertNotIn("PRIVATEKEY",details["google_message"])
        self.assertIn("[REDACTED]",details["google_message"])
        self.assertNotIn("network_error",details)

    def test_invalid_api_key_401_is_not_misreported_as_network_error(self):
        from io import BytesIO
        from urllib.error import HTTPError,URLError
        invalid=b'{"error":{"code":401,"status":"UNAUTHENTICATED","message":"API key not valid"}}'
        response=HTTPError("https://example.com",401,"Unauthorized",None,BytesIO(invalid))
        details=pilot.google_error_details(response,"PRIVATEKEY")
        self.assertEqual(details["http_status"],401)
        self.assertEqual(details["google_error_status"],"UNAUTHENTICATED")
        self.assertNotIn("network_error",details)
        real_network=pilot.google_error_details(URLError("DNS failure"))
        self.assertEqual(real_network["network_error"],"Network, proxy, or DNS failure")
    def test_diagnostic_cli_does_not_need_desktop_workspace(self):
        """GET-only check should run even when no Desktop/new data folder exists."""
        import io,sys
        from unittest.mock import patch
        from contextlib import redirect_stdout
        fake={"status":"MODEL_LOOKUP_OK","model":pilot.MODEL,"no_paid_calls":True}
        with patch.object(sys,"argv",["gta_google_grounding_pilot.py","--diagnose-key"]), \
             patch.object(pilot,"find_workspace",side_effect=AssertionError("workspace must not be used")), \
             patch.object(pilot,"diagnose_key",return_value=fake) as diag, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(pilot.main(),0)
        self.assertTrue(diag.called)
        self.assertIn("MODEL_LOOKUP_OK",output.getvalue())

    def test_diagnostic_prompt_keeps_key_out_of_output(self):
        """A hidden private prompt is used only when GEMINI_API_KEY is unset."""
        import io,os,sys
        from unittest.mock import patch
        from contextlib import redirect_stdout
        fake={"status":"MODEL_LOOKUP_OK","model":pilot.MODEL,"no_paid_calls":True}
        with patch.dict(os.environ,{"GEMINI_API_KEY":""}), \
             patch.object(sys,"argv",["gta_google_grounding_pilot.py","--diagnose-key","--prompt-key"]), \
             patch("getpass.getpass",return_value="PRIVATE_PROMPT_KEY") as private_prompt, \
             patch.object(pilot,"diagnose_key",return_value=fake) as diag, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(pilot.main(),0)
        private_prompt.assert_called_once()
        diag.assert_called_once_with("PRIVATE_PROMPT_KEY")
        self.assertNotIn("PRIVATE_PROMPT_KEY",output.getvalue())

    def test_missing_key_does_not_touch_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.seed(root,1)
            result=pilot.run(root,paid=True,key="",today=dt.date(2026,11,1))
            self.assertEqual(result["status"],"GOOGLE_KEY_MISSING")
            self.assertFalse((root/pilot.LEDGER).exists())

if __name__=="__main__":
    unittest.main()
