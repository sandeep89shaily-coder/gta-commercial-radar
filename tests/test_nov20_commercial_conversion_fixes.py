"""Reproduce November 20 conversion issues without paying providers."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gta_24_city_ai_selection import finalize
from gta_federal_capex_qualification import run as qualify
from gta_industrial_buyer_investigation_queue import run as handoff
from municipal_deepseek_buyer_research import propose

def write(path, data):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]))
        w.writeheader();w.writerows(data)

def read(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

class CommercialConversionNov20(unittest.TestCase):
    def test_model_conflict_and_deprioritize_do_not_reach_top10(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            queue=[
                {"canonical_id":"ST._CATHARINES:FILE:26112777OP26112778ZA",
                 "city":"St. Catharines","cohort":"EXPANSION_8","source_date":"2026-10-22",
                 "address":"8 Gale Crescent"},
                {"canonical_id":"BARRIE:FILE:D110222026","city":"Barrie",
                 "cohort":"EXPANSION_8","source_date":"2026-09-28",
                 "address":"131 Lockhart Road"},
                {"canonical_id":"GUELPH:FILE:OZS26021","city":"Guelph",
                 "cohort":"CORE_16","source_date":"2026-11-15",
                 "address":"36 Wellington St East"},
            ]
            write(root/"GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv",queue)
            write(root/"GTA_RADAR_COMBINED_28_CITY_RESEARCH_TOP10.csv",queue)
            ids=[q["canonical_id"] for q in queue]
            pool=[{"record_id":q["canonical_id"],"city":q["city"],
                   "cohort":q["cohort"],
                   "internal_research_priority_score_not_sale_probability":90,
                   "source_date":q["source_date"]} for q in queue]
            decisions=["DEPRIORITIZE","NEUTRAL","CHECK_CONFLICT"]
            state={"status":"AI_TOP10_REVIEW_ONLY","input_fingerprint":"fixture",
                   "reviewed_count":3,"applies_to_top10":True,
                   "recheck_date":"2026-11-20",
                   "reviews":[{"record_id":rid,"decision":dec} for rid,dec in zip(ids,decisions)]}
            with patch("gta_24_city_ai_selection.ai_fingerprint",return_value="fixture"):
                report=finalize(root,state=state,pool=pool,
                                today=dt.date(2026,11,20),universe=28)
            self.assertEqual(report["top10_count"],1)
            self.assertEqual(report["ai_rejected_or_held_count"],2)
            winners=read(root/"GTA_RADAR_COMBINED_28_CITY_TOP10.csv")
            self.assertEqual([x["canonical_id"] for x in winners],[ids[1]])
            self.assertEqual(winners[0]["deepseek_decision"],"NEUTRAL")

    def test_federal_public_garden_grant_excluded_and_equipment_kept(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            data=[
                {"funding_record_id":"SHEL","recipient":"The Corporation of the Town of Shelburne",
                 "activity_excerpt":"This project aims to purchase garden supplies, cold storage, processing equipment and other kitchen appliances.",
                 "date_as_published":"2025-03-07","source_dataset":"https://open.canada.ca"},
                {"funding_record_id":"CNC1","recipient":"CMI Heavy Industries Inc",
                 "activity_excerpt":"To onshore manufacturing production through acquisition and installation of a CNC Floor Boring Mill.",
                 "date_as_published":"2025-12-15","source_dataset":"https://open.canada.ca"}
            ]
            write(root/"GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_CANDIDATES.csv",data)
            report=qualify(root,as_of=dt.date(2026,11,20))
            self.assertEqual(report["qualified_records"],1)
            self.assertEqual(read(root/"GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv")[0]["recipient"],"CMI Heavy Industries Inc")

    def test_federal_top20_has_a_real_queued_handoff_without_fake_project_link(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            write(root/"GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv",[{
                "research_rank":"1","recipient":"Maxxit Systems Inc",
                "funding_record_id":"FED-1","evidence_scope":"CNC bending equipment",
                "recipient_city_not_project_site":"Toronto",
            }])
            write(root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv",[{
                "company":"Maxxit Systems Inc","source_type":"SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT",
                "source_url":"https://www.canada.ca/news",
            }])
            report=handoff(root)
            self.assertEqual(report["investigation_queue_rows"],1)
            self.assertEqual(report["existing_company_name_matches_only"],1)
            self.assertEqual(report["exact_project_matches_verified"],0)
            self.assertEqual(report["paid_model_calls"],0)
            row=read(root/"GTA_RADAR_INDUSTRIAL_BUYER_INVESTIGATION_QUEUE.csv")[0]
            self.assertEqual(row["buyer_verified"],"False")
            self.assertEqual(row["research_state"],"PROJECT_SPECIFIC_BUYER_RESEARCH_NOT_YET_DONE")

    def test_invalid_buyer_json_retained_without_crashing_or_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=[{"project_id":"example:123","source_url":"https://www.toronto.ca/test",
                   "quote":"Example Equipment Inc owns the plant."}]
            def malformed(endpoint,payload):
                return {"choices":[{"finish_reason":"stop",
                        "message":{"content":'{"relationships": [this is invalid]'}}]}
            report=propose(rows,root,root/"buyer.json",paid=True,key="test",
                           transport=malformed)
            self.assertEqual(report["status"],"MODEL_INVALID_JSON_REVIEW_ONLY")
            self.assertFalse(report["automatic_retry"])
            saved=json.loads((root/"buyer.json").read_text(encoding="utf-8"))
            self.assertIn("invalid",saved["raw_model_excerpt"])
            self.assertEqual(saved["verified_buyers"],0)

if __name__=="__main__":unittest.main()
