"""Hamilton human-researched candidate exports never certify contractors."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
import hamilton_company_evidence_export as evidence

class Tests(unittest.TestCase):
    def test_checked_in_cases_have_source_and_no_invented_buyer(self):
        path=Path("research/hamilton_public_business_evidence_20261024.json")
        cases=json.loads(path.read_text(encoding="utf-8"))["entries"]
        self.assertEqual(len(cases),12)
        self.assertTrue(evidence.validate(cases))
        self.assertTrue(all(r["contract_availability"]=="UNKNOWN" for r in cases))
        self.assertTrue(all(r["sale_ready"] is False for r in cases))
        self.assertEqual(sum(r["lane"]=="FUNDED_FACTORY_UPGRADE" for r in cases),9)

    def test_bad_sales_claims_rejected(self):
        template=json.loads(Path(
            "research/hamilton_public_business_evidence_20261024.json"
            ).read_text(encoding="utf-8"))["entries"][0]
        with self.assertRaisesRegex(RuntimeError,"sale-ready"):
            evidence.validate([{**template,"sale_ready":True}])
        with self.assertRaisesRegex(RuntimeError,"must stay unknown"):
            evidence.validate([{**template,"vendor_selection_status":"OPEN"}])

    def test_report_created_separately_from_gis(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(evidence.run(output_dir=d),0)
            with (Path(d)/"HAMILTON_EVIDENCE_BACKED_COMPANY_RESEARCH.csv").open(
                encoding="utf-8-sig",newline="") as handle:
                rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),12)
            self.assertEqual(rows[0]["organization"],"Alba Developments")
            self.assertEqual(rows[0]["sale_ready"],"NO")
            with (Path(d)/"HAMILTON_EVIDENCE_STATUS.csv").open(
                encoding="utf-8-sig",newline="") as handle:
                statuses={r["metric"]:r["value"] for r in csv.DictReader(handle)}
            self.assertEqual(statuses["sale_ready_verified_leads"],"0")

if __name__=="__main__":
    unittest.main()
