import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from gta_federal_capex_qualification import run,SOURCE,OUTPUT,TOP

class FederalCapexQualificationTests(unittest.TestCase):
    def test_discards_irrelevant_duplicates_and_flags_company_not_project(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=[
                {"funding_record_id":"DFIP-1","recipient":"Farm Inc","recipient_city":"London","activity_excerpt":"The Dairy Farm Investment Program helps dairy farmers upgrade manufacturing equipment.","agreement_title":"Dairy Farm Investment Program","date_as_published":"2016-11-10","source_dataset":"https://open.canada.ca"},
                {"funding_record_id":"G-1","recipient":"Maxxit Systems Inc. | Maxxit Systems Inc.","recipient_city":"Toronto","activity_excerpt":"To modernize architectural metal manufacturing through advanced digital printing and CNC bending equipment, increasing production efficiency.","agreement_title":"Modernization","date_as_published":"2026-03-01","source_dataset":"https://open.canada.ca"},
                {"funding_record_id":"G-1","recipient":"Maxxit Systems Inc.","recipient_city":"Toronto","activity_excerpt":"To modernize architectural metal manufacturing through advanced digital printing and CNC bending equipment, increasing production efficiency.","agreement_title":"Modernization","date_as_published":"2026-03-01","source_dataset":"https://open.canada.ca"},
                {"funding_record_id":"RTI-1","recipient":"Researcher","recipient_city":"Toronto","activity_excerpt":"The Research Tools and Instruments grants foster university researchers in manufacturing equipment.","agreement_title":"Research Tools and Instruments","date_as_published":"2026-04-01","source_dataset":"https://open.canada.ca"},
                {"funding_record_id":"G-2","recipient":"Old Steel Ltd","recipient_city":"Toronto","activity_excerpt":"Install robotic welding equipment at manufacturing plant.","agreement_title":"Automation","date_as_published":"2021-01-01","source_dataset":"https://open.canada.ca"},
            ]
            with (root/SOURCE).open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            with (root/"GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv").open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["company"]);w.writeheader();w.writerow({"company":"Maxxit Systems Inc."})
            r=run(root,as_of=dt.date(2026,11,19))
            self.assertEqual(r["qualified_records"],1)
            self.assertEqual(r["company_name_matches_only"],1)
            self.assertEqual(r["exact_projects_matched"],0)
            self.assertEqual(r["purchase_verified"],0)
            with (root/TOP).open(encoding="utf-8-sig",newline="") as f: x=list(csv.DictReader(f))
            self.assertEqual(len(x),1)
            self.assertEqual(x[0]["radar_company_match_status"],"COMPANY_NAME_ONLY_REVIEW")
            self.assertEqual(x[0]["buyer_verified"],"False")
            self.assertTrue((root/OUTPUT).is_file())

    def test_empty_input_does_not_claim_verified_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            r=run(d,as_of=dt.date(2026,11,19))
            self.assertEqual(r["qualified_records"],0)
            self.assertEqual(r["status"],"NO_FEDERAL_CANDIDATES_INPUT")

if __name__=="__main__":unittest.main()
