"""Exactly identified applications never inherit adverse stage from neighbours."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
import early_project_scope_audit as audit

FIXTURE="research/hamilton_scope_stage_evidence_20261024.json"

class Tests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads(Path(FIXTURE).read_text(encoding="utf-8"))

    def test_strict_inputs_and_real_sources(self):
        self.assertTrue(audit.validate(self.data))
        self.assertEqual(len(self.data["checks"]),9)
        copy=json.loads(json.dumps(self.data))
        copy["checks"][0]["transfer_to_other_same_address_scopes"]=True
        with self.assertRaisesRegex(RuntimeError,"Cross-project"):
            audit.validate(copy)

    def test_withdrawal_applies_only_to_its_own_ero_file(self):
        records=audit._summary(self.data["checks"])
        cases={x["exact_scope_id"]:x for x in records}
        self.assertEqual(cases["ERO-019-8711"]["stage_assessment"],
            "SCOPE_WITHDRAWN_OR_CLOSED")
        self.assertEqual(cases["FC-2026-00239"]["stage_assessment"],
            "PREAPPLICATION_STAGE_CURRENTNESS_UNVERIFIED")
        self.assertEqual(cases["HAMILTON-PERMIT-26-101057"]["stage_assessment"],
            "DEMOLITION_PERMIT_ALREADY_ISSUED")
        self.assertEqual(cases["HOPA-COMMERCIAL-PROPERTY-1133"]["stage_assessment"],
            "COMMERCIAL_LEASING_NOT_CONSTRUCTION_PROCUREMENT")
        self.assertEqual(cases["FC-2026-00239"]["sale_ready"],"NO")
        self.assertGreater(cases["FC-2026-00239"]["distinct_other_scopes_same_site"],1)

    def test_date_precision_and_purchasing_trap(self):
        cases={x["exact_scope_id"]:x for x in audit._summary(self.data["checks"])}
        self.assertEqual(cases["HAMILTON-PERMIT-26-101057"]["original_public_date"],"")
        self.assertEqual(cases["ERO-019-8711"]["original_public_date"],"2024-05-21")
        self.assertEqual(cases["DPA-2026-00043"]["original_public_date"],"2026-05-11")
        self.assertTrue(all(c["project_specific_procurement"]=="NOT_VERIFIED" for c in cases.values()))
        changed=json.loads(json.dumps(self.data))
        changed["checks"][2]["event_date"]="2026-05-20"
        with self.assertRaisesRegex(RuntimeError,"Permit month"):
            audit.validate(changed)
        changed=json.loads(json.dumps(self.data))
        changed["procurement_portals"][0]["project_specific_open_bid_verified"]=True
        with self.assertRaisesRegex(RuntimeError,"Organizational portal"):
            audit.validate(changed)

    def test_consolidated_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(audit.run(FIXTURE,d),0)
            with (Path(d)/"HAMILTON_EXACT_SCOPE_STAGE_AUDIT.csv").open(
                encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertGreaterEqual(len(rows),7)
            self.assertTrue(all(r["sale_ready"]=="NO" for r in rows))
            with (Path(d)/"HAMILTON_SCOPE_STAGE_SUMMARY.csv").open(
                encoding="utf-8-sig",newline="") as f:
                metrics={x["metric"]:x["value"] for x in csv.DictReader(f)}
            self.assertEqual(metrics["verified_private_open_bid_packages"],"0")
            self.assertEqual(metrics["qualified_sale_ready_leads"],"0")
            self.assertEqual(metrics["explicit_withdrawn_scopes"],"1")
            with (Path(d)/"EARLY_OFFICIAL_PUBLIC_PROCUREMENT_CHANNELS.csv").open(
                 encoding="utf-8-sig",newline="") as f:
                portals=list(csv.DictReader(f))
            self.assertEqual(len(portals),3)
            self.assertTrue(all(r["project_specific_open_bid_verified"]=="False" for r in portals))

if __name__=="__main__":unittest.main()
