"""Western corridor evidence integrity, publisher rights and Windsor reuse."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_24_city_combined import COLS,COVERAGE_COLS,CORE_CITIES,EXPANSION_CITIES
from gta_four_city_live_daily import CITIES as FOUR
import gta_western_corridor_source_audit as sources
import gta_western_31_city_combined as combine

class WestCorridor(unittest.TestCase):
    def write(self,path,fields,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",newline="",encoding="utf-8-sig") as fp:
            w=csv.DictWriter(fp,fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def seed(self,root):
        cities=list(CORE_CITIES)+list(EXPANSION_CITIES)+list(FOUR)
        self.assertEqual(len(cities),28)
        status={"configured_city_count":28}
        (root/combine.CURRENT28).write_text(json.dumps(status))
        rows=[{"canonical_id":"WINDSOR:FILE:Z00826",
               "city":"Windsor","record_kind":"APPLICATION",
               "application_id":"Z-008/26","address":"825 Cabana Road East",
               "scope":"Zoning application","cohort":"ADDED_4"}]
        self.write(root/combine.SOURCE28,COLS,rows)
        self.write(root/combine.COVERAGE28,COVERAGE_COLS,
                   [{"city":c,"cohort":"CORE_16"} for c in cities])
        self.write(root/combine.QUEUE28,COLS,rows)
        self.write(root/combine.TOP28,COLS,rows)

    def test_no_unauthorized_web_fetch_and_31_configurations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.seed(root)
            audit=sources.run(root)
            self.assertEqual(len(audit["target_cities"]),4)
            for city in sources.NEW:
                self.assertEqual(
                    audit["source_states"][city]["status"],
                    "SOURCE_RIGHTS_NOT_VERIFIED_NO_AUTOMATED_FETCH")
            result=combine.run(root)
            self.assertEqual(result["configured_city_count"],31)
            self.assertEqual(result["candidate_rows_new_cities_promoted_to_ai"],0)
            with (root/combine.COVERAGE).open(encoding="utf-8-sig") as fp:
                rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),31)
            self.assertEqual(sum(x["city"]=="Windsor" for x in rows),1)
            self.assertTrue((root/combine.MASTER).exists())

    def test_windsor_live_evidence_from_existing_source_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json").write_text(
                json.dumps({"city_status":[{"city":"Windsor",
                  "status":"LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE"}]}))
            self.write(root/"GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv",
                ["city","application_id","address"],[
                    {"city":"Windsor","application_id":"Z-008/26",
                     "address":"825 Cabana Road East"},
                    {"city":"Windsor","application_id":"Z 008/26",
                     "address":"825 Cabana Road East"},
                    {"city":"Pickering","application_id":"SP-2026-01",
                     "address":"1 King Street"}])
            status=sources.windsor_audit(root)
            self.assertEqual(status["live_current_application_ids"],1)
            self.assertEqual(status["status"],"WINDSOR_EXISTING_FEED_LIVE_PARTIAL")

    def test_incomplete_publisher_rights_export_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/sources.IMPORT_DIR
            folder.mkdir()
            self.write(folder/"sarnia.csv",
                ["application_id","address","scope","source_url"],[
                {"application_id":"OPA-2026-1","address":"12 Factory Road",
                 "scope":"Industrial investment",
                 "source_url":"https://www.sarnia.ca/public-notices/example"}])
            audit=sources.run(root)
            self.assertEqual(audit["source_states"]["Sarnia"]["status"],
                "UNAUTHORIZED_OR_INVALID_SOURCE_EXPORT")
            self.assertEqual(audit["authorized_imported_application_ids"],0)

    def test_manually_authorized_exports_deduplicate_and_dont_fake_new(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.seed(root)
            folder=root/sources.IMPORT_DIR
            folder.mkdir()
            self.write(folder/"london.csv",
                ["application_id","address","scope","source_url"],
                [{"application_id":"OZ-26021","address":"412 Oxford Street West",
                  "scope":"Mixed use redevelopment",
                  "source_url":"https://london.ca/business-development/planning-development-applications/planning-applications/test"},
                 {"application_id":"OZ 26021","address":"412 Oxford Street West",
                  "scope":"Repeated row",
                  "source_url":"https://london.ca/business-development/planning-development-applications/planning-applications/test"}])
            (folder/"london.source.json").write_text(json.dumps({
                "city":"London",
                "official_source_url":"https://opendata.london.ca/datasets/approved-planning",
                "licence_evidence_url":"https://london.ca/government/council-civic-administration/open-data",
                "rights_scope":"PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE"}))
            audit=sources.run(root)
            self.assertEqual(audit["authorized_imported_application_ids"],1)
            result=combine.run(root)
            self.assertEqual(result["authorized_imported_new_city_rows"],1)
            self.assertEqual(result["candidate_rows_new_cities_promoted_to_ai"],0)
            with (root/combine.MASTER).open(encoding="utf-8-sig") as fp:
                rows=list(csv.DictReader(fp))
            self.assertEqual(len(rows),2)
            with (root/combine.TOP10).open(encoding="utf-8-sig") as fp:
                top=list(csv.DictReader(fp))
            self.assertEqual({x["city"] for x in top},{"Windsor"})

    def test_rejected_manifest_source_spoof(self):
        manifest={"city":"Sarnia",
            "rights_scope":"PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE",
            "official_source_url":"https://evil.org/path",
            "licence_evidence_url":"https://sarnia.ca/terms-of-service/"}
        with self.assertRaises(ValueError):
            sources.validate_manifest("Sarnia",manifest)
        self.assertFalse(sources.approved_url("http://maps.london.ca/path","London"))
        self.assertFalse(sources.approved_url("https://evil.org/path","London"))
if __name__=="__main__":
    unittest.main()
