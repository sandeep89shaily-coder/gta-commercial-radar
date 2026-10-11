from pathlib import Path
import unittest

class StartupRequirementsTests(unittest.TestCase):
 def test_launcher_checks_all_critical_imports(self):
  launcher=(Path(__file__).resolve().parents[1]/'START_RADAR.bat').read_text(encoding='utf-8')
  for module in ('requests','bs4','pypdf','pandas','openpyxl'):
   self.assertIn(module,launcher)
if __name__=='__main__':unittest.main()
