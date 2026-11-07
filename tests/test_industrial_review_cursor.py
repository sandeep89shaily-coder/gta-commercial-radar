import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import gta_industrial_review_cursor as cursor
import gta_industrial_equipment_pilot as pilot

def sample_cards():
    return {
        "026-1152":{"ero_number":"026-1152",
                    "official_notice_url":"https://ero.ontario.ca/notice/026-1152",
                    "notice_stage":"Proposal","last_updated":"2026-11-06"},
        "026-1155":{"ero_number":"026-1155",
                    "official_notice_url":"https://ero.ontario.ca/notice/026-1155",
                    "notice_stage":"Proposal","last_updated":"2026-11-06"},
        "026-1148":{"ero_number":"026-1148",
                    "official_notice_url":"https://ero.ontario.ca/notice/026-1148",
                    "notice_stage":"Proposal","last_updated":"2026-11-05"},
        "026-1140":{"ero_number":"026-1140",
                    "official_notice_url":"https://ero.ontario.ca/notice/026-1140",
                    "notice_stage":"Decision","last_updated":"2026-11-05"},
    }

class IndustrialReviewCursorTests(unittest.TestCase):
    def test_migrate_successful_prior_zip_without_repeating_first_five(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            prior={"official_fetch_audit":[
                {"ero_number":"026-1155","status":"DETAIL_RETRIEVED"},
                {"ero_number":"026-1152","status":"DETAIL_RETRIEVED"},
                {"ero_number":"026-1148","status":"DETAIL_REJECTED"},
            ]}
            (out/cursor.PREVIOUS_STATUS).write_text(json.dumps(prior))
            cards=sample_cards()
            state=cursor.load(out,cards)
            chosen=cursor.select(cards,state,2)
            self.assertEqual(list(chosen),["026-1140","026-1148"])
            self.assertEqual(cursor.reviewed_count(state),2)

    def test_new_notices_before_retries_and_unchanged_completions(self):
        cards=sample_cards()
        state={"version":1,"notices":{
            "026-1155":{"status":"DETAIL_RETRIEVED",
                        "card_fingerprint":cursor.fingerprint(cards["026-1155"])},
            "026-1148":{"status":"DETAIL_REJECTED","card_fingerprint":cursor.fingerprint(cards["026-1148"])}
        }}
        selected=cursor.select(cards,state,2)
        self.assertEqual(list(selected),["026-1152","026-1140"])
        # Stage/status change on prior reviewed notice has priority
        cards["026-1155"]["notice_stage"]="Decision"
        selected=cursor.select(cards,state,1)
        self.assertEqual(list(selected),["026-1155"])

    def test_save_does_not_mutate_source_card_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            cards=sample_cards()
            state={"version":1,"notices":{}}
            cursor.update(state, cards,[{"ero_number":"026-1152","status":"DETAIL_RETRIEVED"}])
            cursor.save(td,state)
            result=cursor.load(td,cards)
            self.assertEqual(cursor.reviewed_count(result),1)
            self.assertEqual(result["notices"]["026-1152"]["card_fingerprint"],
                             cursor.fingerprint(cards["026-1152"]))

    def test_existing_two_real_evidence_rows_carried_forward_with_site_history(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            old_rows=[{
                "signal_id":"pintys-physical-replace",
                "ero_number":"026-1152",
                "official_notice_url":"https://ero.ontario.ca/notice/026-1152",
                "site_address":"2714 Bristol Circle","city":"Oakville",
                "equipment":"Dust collection","action":"REPLACEMENT",
                "replacement_equipment":"Scrubber",
                "procurement_status":"UNKNOWN",
            }, {
                "signal_id":"burlington-install",
                "ero_number":"026-1155",
                "official_notice_url":"https://ero.ontario.ca/notice/026-1155",
                "site_address":"890 Harrington Court","city":"Burlington",
                "equipment":"Cremation equipment","action":"INSTALLATION",
                "procurement_status":"UNKNOWN",
            }]
            with (out/pilot.OUTPUT).open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(old_rows[0].keys()))
                w.writeheader()
                for row in old_rows: w.writerow(row)
            status={"official_fetch_audit":[
                {"ero_number":"026-1152","status":"DETAIL_RETRIEVED"},
                {"ero_number":"026-1155","status":"DETAIL_RETRIEVED"},
            ]}
            (out/cursor.PREVIOUS_STATUS).write_text(json.dumps(status))
            results=out/"GTA_RADAR_RESULTS"
            results.mkdir()
            with (results/"GTA_RADAR_COLLECTION_MASTER.csv").open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=[
                    "canonical_id","city","record_kind","description","evidence_urls","address"])
                w.writeheader()
                w.writerow({"canonical_id":"OAKVILLE:FILE:140307101","city":"Oakville",
                            "record_kind":"APPLICATION_ID","address":"",
                            "description":"Pinty's Delicious Foods Inc. - 2714 Bristol Circle - 1403.071/01",
                            "evidence_urls":"https://www.oakville.ca/planning/"})
            cards=sample_cards()
            fake_called=[]
            def fake_fetch(selected, max_notices):
                fake_called.extend(selected)
                return [],[{"ero_number":x,"status":"DETAIL_REJECTED",
                           "reason":"FIXTURE_UNAVAILABLE"} for x in selected]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                summary=pilot.run(out,db=out/"unused.sqlite",results=results,
                                  fetch_official=True,fetch_limit=1,
                                  official_fetcher=fake_fetch)
            self.assertEqual(fake_called,["026-1148"])
            rows=pilot._read_csv(out/pilot.OUTPUT)
            self.assertEqual(len(rows),2)
            old=next(r for r in rows if r["ero_number"]=="026-1152")
            self.assertEqual(old["same_site_history_id"],"OAKVILLE:FILE:140307101")
            self.assertEqual(old["project_match_status"],"")
            self.assertEqual(old["procurement_status"],"UNKNOWN")
            self.assertEqual(summary["ero_detail_successes_total"],2)
            self.assertEqual(summary["prior_equipment_candidates_preserved"],2)

if __name__=="__main__":
    unittest.main()
