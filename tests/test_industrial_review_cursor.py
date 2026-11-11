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
            self.assertEqual(list(chosen),["026-1148","026-1140"])
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


    def test_changed_notice_failed_recheck_holds_prior_equipment_signal(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            cards=sample_cards()
            old_notice=cards["026-1152"]
            existing={
                "signal_id":"pintys-physical-replace",
                "ero_number":"026-1152",
                "official_notice_url":old_notice["official_notice_url"],
                "site_address":"2714 Bristol Circle",
                "city":"Oakville",
                "equipment":"Dust collection",
                "action":"REPLACEMENT",
                "replacement_equipment":"Scrubber",
                "notice_stage":"Proposal",
                "review_status":"MANUAL_REVIEW_REQUIRED",
                "procurement_status":"UNKNOWN",
                "buyer_verified":"NO",
            }
            with (out/pilot.OUTPUT).open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=list(existing))
                writer.writeheader()
                writer.writerow(existing)
            cursor.save(out,{"version":1,"notices":{
                "026-1152":{"status":"DETAIL_RETRIEVED",
                            "card_fingerprint":cursor.fingerprint(old_notice)}
            }})
            cards["026-1152"]["notice_stage"]="Decision"
            captured=[]
            def failed_fetch(selected,max_notices):
                captured.extend(selected)
                return [],[{"ero_number":no,"status":"DETAIL_REJECTED",
                           "reason":"HTTP_503"} for no in selected]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                summary=pilot.run(out,db=out/"unused.sqlite",fetch_official=True,
                                  fetch_limit=1,official_fetcher=failed_fetch)
            self.assertEqual(captured,["026-1152"])
            signals=pilot._read_csv(out/pilot.OUTPUT)
            self.assertEqual(len(signals),1)
            self.assertEqual(signals[0]["review_status"],"SOURCE_CHANGED_OR_RECHECK_FAILED_HOLD")
            self.assertEqual(signals[0]["procurement_status"],"UNKNOWN")
            self.assertEqual(signals[0]["buyer_verified"],"NO")
            self.assertEqual(summary["carried_forward_source_recheck_holds"],1)
            self.assertIn("Evidence status",(out/pilot.HTML).read_text(encoding="utf-8"))
            # A previously failed notice must remain retryable, not falsely complete.
            retry=cursor.load(out,cards)
            self.assertIn("026-1152",cursor.select(cards,retry,10))

    def test_failed_unchanged_notice_recheck_does_not_hide_prior_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            cards=sample_cards()
            existing={
                "signal_id":"old-replacement","ero_number":"026-1152",
                "official_notice_url":"https://ero.ontario.ca/notice/026-1152",
                "site_address":"2714 Bristol Circle","city":"Oakville",
                "equipment":"Dust collection","action":"REPLACEMENT",
                "review_status":"MANUAL_REVIEW_REQUIRED",
                "notice_stage":"Proposal","procurement_status":"UNKNOWN",
                "buyer_verified":"NO",
            }
            with (out/pilot.OUTPUT).open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(existing))
                w.writeheader()
                w.writerow(existing)
            cursor.save(out,{"version":1,"notices":{
                "026-1152":{"status":"DETAIL_RETRIEVED",
                            "card_fingerprint":cursor.fingerprint(cards["026-1152"])}
            }})
            # Re-fetch another notice; the unchanged old source keeps its
            # existing review-only status rather than being marked new.
            def recheck(selected,max_notices):
                return [],[{"ero_number":no,"status":"DETAIL_REJECTED"} for no in selected]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                summary=pilot.run(out,db=out/"unused.sqlite",fetch_official=True,
                                  fetch_limit=1,official_fetcher=recheck)
            prior=pilot._read_csv(out/pilot.OUTPUT)
            self.assertEqual(prior[0]["review_status"],"MANUAL_REVIEW_REQUIRED")
            self.assertEqual(summary["carried_forward_source_recheck_holds"],0)


    def test_success_audit_without_parsed_payload_does_not_poison_cursor(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            cards=sample_cards()
            chosen=[]
            def missing_payload(selected,max_notices):
                chosen.extend(selected)
                return [],[{"ero_number":no,"status":"DETAIL_RETRIEVED"}
                          for no in selected]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                status=pilot.run(out,db=out/"unused.sqlite",fetch_official=True,
                                 fetch_limit=1,official_fetcher=missing_payload)
            self.assertEqual(len(chosen),1)
            self.assertEqual(status["official_fetch_audit"][0]["status"],"DETAIL_REJECTED")
            self.assertEqual(status["official_fetch_audit"][0]["reason"],
                             "SUCCESS_AUDIT_WITHOUT_VALID_SOURCE_PAYLOAD")
            self.assertEqual(status["ero_detail_successes_total"],0)
            state=cursor.load(out,cards)
            self.assertEqual(state["notices"][chosen[0]]["status"],"DETAIL_REJECTED")
            self.assertIn(chosen[0],cursor.select(cards,state,10))

    def test_mismatched_fetched_record_never_marks_source_retrieved(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            cards=sample_cards()
            seen=[]
            def wrong_payload(selected,max_notices):
                seen.extend(selected)
                no=next(iter(selected))
                record={"ero_number":no,"official_notice_url":
                            "https://ero.ontario.ca/notice/999-9999",
                        "content_provenance":"FETCHED_EXACT_ERO_OFFICIAL_NOTICE",
                        "proposal_details":"Install a new industrial boiler at this site.",
                        "site_address":"2714 Bristol Circle","city":"Oakville"}
                return [record],[{"ero_number":no,"status":"DETAIL_RETRIEVED"}]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                status=pilot.run(out,db=out/"unused.sqlite",fetch_official=True,
                                 fetch_limit=1,official_fetcher=wrong_payload)
            self.assertEqual(status["official_notice_excerpts_loaded"],0)
            self.assertEqual(status["equipment_change_candidates"],0)
            self.assertEqual(status["official_fetch_audit"][0]["status"],"DETAIL_REJECTED")
            self.assertEqual(status["ero_detail_successes_total"],0)
            self.assertIn(seen[0],cursor.select(cards,cursor.load(out,cards),10))


    def test_accepted_ero_notice_overrides_older_manual_excerpt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);manual=root/"manual.csv"
            row={"ero_number":"026-1155",
                 "official_notice_url":"https://ero.ontario.ca/notice/026-1155",
                 "site_address":"890 Harrington Court","city":"Burlington",
                 "proposal_details":"This application is to replace the boiler."}
            with manual.open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
            cards={"026-1155":sample_cards()["026-1155"]}
            def fresh(selected,max_notices):
                self.assertEqual(list(selected),["026-1155"])
                return [{
                    "ero_number":"026-1155",
                    "official_notice_url":cards["026-1155"]["official_notice_url"],
                    "content_provenance":"FETCHED_EXACT_ERO_OFFICIAL_NOTICE",
                    "site_address":"890 Harrington Court","city":"Burlington",
                    "proposal_details":"This application is for the installation of two human cremation units.",
                    "notice_stage":"Proposal",
                }],[{"ero_number":"026-1155","status":"DETAIL_RETRIEVED"}]
            with patch.object(pilot,"read_radar_ero",return_value=cards):
                result=pilot.run(root/"out",db=root/"unused.sqlite",notice_csv=manual,
                                 fetch_official=True,fetch_limit=1,official_fetcher=fresh)
            signals=pilot._read_csv(root/"out"/pilot.OUTPUT)
            self.assertEqual(result["equipment_change_candidates"],1)
            self.assertEqual(signals[0]["equipment"],"Cremation equipment")
            self.assertEqual(signals[0]["evidence_basis"],
                             "FETCHED_EXACT_ERO_OFFICIAL_NOTICE")
            self.assertFalse(any(r["equipment"]=="Boiler" for r in signals))

    def test_failed_changed_ero_recheck_keeps_prior_held_instead_of_manual_republish(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);out=root/"out";out.mkdir()
            card=sample_cards()["026-1152"].copy()
            old={"signal_id":"old-source-signal","ero_number":"026-1152",
                 "official_notice_url":card["official_notice_url"],
                 "site_address":"2714 Bristol Circle","city":"Oakville",
                 "equipment":"Dust collection","action":"REPLACEMENT",
                 "notice_stage":"Proposal","review_status":"MANUAL_REVIEW_REQUIRED",
                 "procurement_status":"UNKNOWN","buyer_verified":"NO"}
            with (out/pilot.OUTPUT).open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(old));w.writeheader();w.writerow(old)
            cursor.save(out,{"version":1,"notices":{
                "026-1152":{"status":"DETAIL_RETRIEVED",
                            "card_fingerprint":cursor.fingerprint(card)}}})
            card["notice_stage"]="Decision"
            manual=root/"stale.csv"
            row={"ero_number":"026-1152",
                 "official_notice_url":card["official_notice_url"],
                 "site_address":"2714 Bristol Circle","city":"Oakville",
                 "proposal_details":"Install a new industrial boiler."}
            with manual.open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
            def unavailable(selected,max_notices):
                return [],[{"ero_number":no,"status":"DETAIL_REJECTED",
                            "reason":"HTTP_503"} for no in selected]
            with patch.object(pilot,"read_radar_ero",return_value={"026-1152":card}):
                summary=pilot.run(out,db=root/"unused.sqlite",notice_csv=manual,
                                  fetch_official=True,fetch_limit=1,
                                  official_fetcher=unavailable)
            signals=pilot._read_csv(out/pilot.OUTPUT)
            self.assertEqual(len(signals),1)
            self.assertEqual(signals[0]["signal_id"],"old-source-signal")
            self.assertEqual(signals[0]["review_status"],
                             "SOURCE_CHANGED_OR_RECHECK_FAILED_HOLD")
            self.assertEqual(signals[0]["procurement_status"],"UNKNOWN")
            self.assertEqual(summary["new_equipment_candidates_this_run"],0)
            self.assertEqual(summary["unverified_manual_excerpt_ids_held_on_official_recheck"],
                             ["026-1152"])


    def test_bulletin_exclusion_not_retried_until_source_card_changes(self):
        cards=sample_cards()
        source=cards["026-1148"]
        state={"version":1,"notices":{}}
        cursor.update(state,cards,[{"ero_number":"026-1148",
            "status":"NON_INSTRUMENT_BULLETIN",
            "reason":"BULLETIN_WITHOUT_SITE_OR_PROPOSAL"}])
        self.assertEqual(cursor.non_instrument_excluded_count(state,cards),1)
        selected=cursor.select({"026-1148":source},state,10)
        self.assertEqual(selected,{})
        cards["026-1148"]["last_updated"]="2026-11-09"
        self.assertEqual(cursor.non_instrument_excluded_count(state,cards),0)
        selected=cursor.select({"026-1148":cards["026-1148"]},state,10)
        self.assertEqual(list(selected),["026-1148"])

if __name__=="__main__":
    unittest.main()
