"""Regression tests for offline all-city quarterly reconciliation."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_quarterly_application_reconciliation import reconcile, MASTER, COVERAGE, IMPORTS, DETAIL, SCORE


def csvwrite(path, rows, fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class QuarterAudit(unittest.TestCase):
    def test_unlicensed_sources_held_and_exact_id_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cities=["Hamilton","Windsor"]+[f"City {i}" for i in range(29)]
            csvwrite(root/COVERAGE,[{"city":c} for c in cities],["city"])
            csvwrite(root/MASTER,[{"city":"Hamilton","record_kind":"APPLICATION","application_id":"SPA-12/26","address":"1 Main St","scope":"Industrial"},
                {"city":"Windsor","record_kind":"APPLICATION","application_id":"Z-001/26","address":"2 Main St","scope":"Zoning"}],
                ["city","record_kind","application_id","address","scope"])
            folder=root/IMPORTS
            csvwrite(folder/"hamilton.csv",[
                {"city":"Hamilton","application_id":"SPA 12-26","address":"1 Main St","scope":"Industrial"},
                {"city":"Hamilton","application_id":"SPA-13/26","address":"5 Bay St","scope":"Warehouse"},
                {"city":"Hamilton","application_id":"SPA-13/26","address":"5 Bay St","scope":"Warehouse"}],
                ["city","application_id","address","scope"])
            (folder/"hamilton.source.json").write_text(json.dumps({"city":"Hamilton",
                "source_url":"https://hamilton.ca/dataset","licence_evidence_url":"https://hamilton.ca/licence",
                "rights_scope":"PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE","reference_period":"2026-Q3"}))
            csvwrite(folder/"windsor.csv",[{"city":"Windsor","application_id":"Z-100/26"}],["city","application_id"])
            result=reconcile(root)
            self.assertEqual(result["cities_with_reference"],1)
            self.assertEqual(result["reference_only_review_candidates"],1)
            self.assertEqual(result["commercial_leads_created"],0)
            self.assertEqual(len(result["input_exports_rejected"]),1)
            with (root/SCORE).open(encoding="utf-8-sig") as f:
                rows={r["city"]:r for r in csv.DictReader(f)}
            self.assertEqual(rows["Hamilton"]["matched_exact_ids"],"1")
            self.assertEqual(rows["Hamilton"]["reference_only_ids"],"1")
            self.assertEqual(rows["Windsor"]["reference_state"],"NO_AUTHORIZED_REFERENCE")
            with (root/DETAIL).open(encoding="utf-8-sig") as f:
                data=list(csv.DictReader(f))
            self.assertEqual(len([r for r in data if r["comparison"]=="REFERENCE_ONLY_REVIEW"]),1)

    def test_missing_current_master_refuses_stale_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                reconcile(Path(tmp))


if __name__=="__main__":
    unittest.main()
