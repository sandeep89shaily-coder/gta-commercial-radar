import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import gta_industrial_equipment_run as launcher


class ManualIndustrialLauncherTests(unittest.TestCase):
    def test_reads_existing_db_and_writes_only_to_pilot_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "GTA_RADAR_RESULTS").mkdir()
            fake_db = root / "data" / "radar.sqlite"
            def pretend(out, **kwargs):
                self.assertEqual(out, root / "GTA_RADAR_RESULTS" / "INDUSTRIAL_PILOT")
                self.assertEqual(kwargs["db"], fake_db)
                self.assertEqual(kwargs["results"], root / "GTA_RADAR_RESULTS")
                self.assertEqual(kwargs["fetch_official"], True)
                self.assertEqual(kwargs["fetch_limit"], 5)
                return {"official_notice_excerpts_loaded": 0,
                        "equipment_change_candidates": 0,
                        "official_fetch_audit": [{"status": "ROBOTS_POLICY_UNAVAILABLE"}]}
            with patch.object(launcher, "find_workspace", return_value=root), \
                 patch.object(launcher, "choose_database", return_value=fake_db):
                result = launcher.execute(limit=5, pilot=pretend)
            self.assertEqual(result["equipment_change_candidates"], 0)
            self.assertFalse(fake_db.exists())  # launcher never creates a replacement

    def test_missing_workspace_fails_without_new_data(self):
        with patch.object(launcher, "find_workspace",
                          side_effect=FileNotFoundError("no workspace")):
            with self.assertRaises(FileNotFoundError):
                launcher.execute(pilot=lambda *args, **kwargs: self.fail("must not run"))


if __name__ == "__main__":
    unittest.main()
