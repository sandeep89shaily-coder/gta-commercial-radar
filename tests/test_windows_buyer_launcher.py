import unittest
from pathlib import Path

class WindowsLauncherRegression(unittest.TestCase):
    def test_release_check_avoids_quoted_trailing_backslash(self):
        script=(Path(__file__).resolve().parents[1]/"RUN_FREE_BUYER_PROCUREMENT_TEST.bat").read_text(encoding="utf-8")
        self.assertIn('--code-dir "%CODE%."',script)
        self.assertNotIn('--code-dir "%CODE%"',script)
        self.assertIn('if errorlevel 1',script)
if __name__=="__main__":unittest.main()
