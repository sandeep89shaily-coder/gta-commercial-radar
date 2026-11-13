import pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class BudgetSingleSourceTests(unittest.TestCase):
    def test_no_hardcoded_old_or_duplicate_ceiling_in_code(self):
        offenders = []
        for path in ROOT.glob("*.py"):
            if path.name == "radar_config.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?<![\d.])0\.49(?![\d])", text):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "ceiling must come from radar_config")

    def test_all_investigators_share_the_configured_ceiling(self):
        import radar_config, v5_investigator, v8_deepseek_native
        self.assertEqual(radar_config.DEEPSEEK_DAILY_LIMIT_USD, 2.00)
        self.assertEqual(v5_investigator.DAILY_BUDGET, 2.00)
        self.assertEqual(v8_deepseek_native.DAILY_LIMIT, 2.00)


if __name__ == "__main__":
    unittest.main()
