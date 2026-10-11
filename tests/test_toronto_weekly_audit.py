import json, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from toronto_catalog_audit import due

class TorontoWeeklyAuditTests(unittest.TestCase):
 def test_missing_inventory_is_due(self):
  with tempfile.TemporaryDirectory() as folder:
   self.assertTrue(due(Path(folder)/'missing.json'))
 def test_recent_inventory_skips_then_expires(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'inventory.json'
   now=datetime(2026,10,11,tzinfo=timezone.utc)
   p.write_text(json.dumps({'observed_at':now.isoformat()}),encoding='utf-8')
   self.assertFalse(due(p,now=now+timedelta(days=6)))
   self.assertTrue(due(p,now=now+timedelta(days=7)))
 def test_corrupt_inventory_reaudited(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'inventory.json'
   p.write_text('broken json',encoding='utf-8')
   self.assertTrue(due(p))
if __name__=='__main__':unittest.main()
