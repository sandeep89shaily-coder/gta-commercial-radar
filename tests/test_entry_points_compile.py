import re
import unittest
from pathlib import Path

import desktop_update

ROOT = Path(__file__).resolve().parent.parent


class EntryPointTests(unittest.TestCase):
    def test_every_top_level_python_file_compiles(self):
        """A syntax error anywhere in the code folder (as in PR #83) fails the build."""
        self.assertEqual(desktop_update.compile_errors(ROOT), [])

    def test_every_launcher_points_at_a_script_that_exists(self):
        missing = {}
        for launcher in sorted([*ROOT.glob("*.bat"), *ROOT.glob("*.cmd"), *ROOT.glob("*.ps1")]):
            text = launcher.read_text(encoding="utf-8", errors="replace").replace("%~dp0", "")
            for name in set(re.findall(r"([A-Za-z0-9_\-]+\.py)\b", text)):
                if not (ROOT / name).is_file():
                    missing.setdefault(launcher.name, []).append(name)
        self.assertEqual(missing, {})

    def test_every_launched_script_compiles(self):
        """Every script a launcher runs must exist and compile (script-style entry points such as main.py are fine)."""
        launched = set()
        for launcher in ROOT.glob("*.bat"):
            text = launcher.read_text(encoding="utf-8", errors="replace").replace("%~dp0", "")
            launched.update(re.findall(r"([A-Za-z0-9_\-]+\.py)\b", text))
        self.assertTrue(launched, "expected launchers to reference scripts")
        for name in sorted(launched):
            path = ROOT / name
            if not path.is_file():
                continue
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_new_modules_are_importable(self):
        import importlib
        for module in ("radar_config", "robots_policy", "source_dates", "candidate_scoring",
                       "reviewed_evidence", "desktop_update", "gta_execute_ai_project_research",
                       "gta_commercial_review_html", "gta_release_acceptance"):
            importlib.import_module(module)


if __name__ == "__main__":
    unittest.main()
