import sqlite3, tempfile, unittest
from pathlib import Path
import peel_pilot as p
class TestPeelPilot(unittest.TestCase):
 def test_caledon_parsing(self):
  x=p.parse_caledon('<ul><li>SPA 2026-0012 - 123 Main St</li><li>RZ 2025-0027 - 20836 Kennedy Road</li></ul>',p.SOURCES['caledon_development_register']['url'])
  self.assertEqual(len(x),2)
  self.assertEqual(x[0]['date_basis'],'NO_SOURCE_DATE')
 def test_peel_parsing(self):
  x=p.parse_peel('<ul><li>Project 25-1340 A - Baker Road watermain replacement</li></ul>',p.SOURCES['peel_flow_projects']['url'])
  self.assertEqual(len(x),1)
 def test_baseline_suppressed(self):
  with tempfile.TemporaryDirectory() as d:
   with sqlite3.connect(':memory:') as c:
    p.init(c)
    html='<ul><li>SPA 2026-0012 - 123 Main St</li></ul>'
    self.assertEqual(p.collect(c,'caledon_development_register',html)[1],'OK_BASELINE')
    self.assertEqual(c.execute('select count(*) from events').fetchone()[0],0)
    self.assertEqual(p.collect(c,'caledon_development_register',html)[3],0)
    p.collect(c,'caledon_development_register','<ul><li>SPA 2026-0012 - 123 Main St (revised)</li></ul>')
    self.assertEqual(c.execute('select count(*) from events').fetchone()[0],1)
 def test_empty_does_not_clear(self):
  with sqlite3.connect(':memory:') as c:
   p.init(c);p.collect(c,'caledon_development_register','<p>SPA 2026-0012 location</p>')
   self.assertEqual(p.collect(c,'caledon_development_register','<p>no data</p>')[1],'ERROR')
   self.assertEqual(c.execute('select count(*) from observations').fetchone()[0],1)
if __name__=='__main__':unittest.main()
