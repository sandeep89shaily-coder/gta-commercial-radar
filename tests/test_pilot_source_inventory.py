"""Guard the exact 21 source definitions and the 17 feeds not in core V8."""
import ast
import csv
import tempfile
import unittest
from pathlib import Path
from unified_collector_inventory import PILOT_GROUPS, OVERLAP_V8, build

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "early_planning_pilot": "early_signal_watch.py",
    "early_industrial_cues": "early_cue_watch.py",
    "early_agendas": "early_discovery_watch.py",
    "early_hamilton": "early_hamilton_watch.py",
    "early_notices": "early_public_notices.py",
    "early_ajax": "early_ajax_watch.py",
    "early_oakville": "early_oakville_watch.py",
    "early_markham": "early_markham_circulation.py",
    "early_investment_tenders": "early_investment_tenders.py",
}

def ids_from_source(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id in ("SOURCES", "SOURCE")
                   for t in node.targets):
            continue
        value = node.value
        if isinstance(value, (ast.Tuple, ast.List)):
            if all(isinstance(e, ast.Constant) for e in value.elts):
                return tuple(e.value for e in value.elts)
            ids = []
            for e in value.elts:
                if not isinstance(e, ast.Call) or not isinstance(e.func, ast.Name) or e.func.id != "dict":
                    raise AssertionError("Unknown pilot source declaration")
                ids.extend(k.value.value for k in e.keywords if k.arg == "id")
            return tuple(ids)
        if isinstance(value, ast.Constant):
            return (value.value,)
    raise AssertionError("No source declaration in " + path)

class Coverage(unittest.TestCase):
    def test_all_actual_source_definitions_are_tracked(self):
        self.assertEqual(len(PILOT_GROUPS), 9)
        for runner, (_, _, ids) in PILOT_GROUPS.items():
            self.assertEqual(tuple(ids), ids_from_source(SCRIPTS[runner]), runner)
        found = [sid for _,_,items in PILOT_GROUPS.values() for sid in items]
        self.assertEqual(len(found), 21)
        self.assertEqual(len(set(found)), 21)
        self.assertEqual(len(set(found) - set(OVERLAP_V8)), 17)
    def test_successful_runner_without_per_source_status_is_not_proven_success(self):
        with tempfile.TemporaryDirectory() as t:
            target,_=build(Path(t),ROOT/"config"/"sources.json",
                           [{"step":"early_industrial_cues","status":"SUCCESS"}])
            rows=list(csv.DictReader(target.open(encoding="utf-8-sig")))
            ie=next(row for row in rows if row["source_id"]=="ieso_connections")
            self.assertEqual(ie["execution_status"],"SOURCE_STATUS_MISSING")
            self.assertEqual(ie["validation_state"],"UNVERIFIED_THIS_RUN")

    def test_missing_run_not_misreported_as_success(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t)
            config = ROOT / "config" / "sources.json"
            target, counters = build(out, config, [])
            rows = list(csv.DictReader(target.open(encoding="utf-8-sig")))
            self.assertEqual(len(rows), 53)  # 32 V8 configurations + 21 pilot definitions
            sample = next(r for r in rows if r["source_id"] == "brampton_preconsultation")
            self.assertEqual(sample["execution_status"], "NOT_RUN_THIS_RUN")
            self.assertEqual(counters["pilot_unique_outside_v8"],17)

if __name__ == "__main__":
    unittest.main()
