import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import daily_radar
class DailyManifestTests(unittest.TestCase):
 def test_missing_db_is_failure(self):
  with tempfile.TemporaryDirectory() as td:
   with patch.object(daily_radar,'DATA',Path(td)):
    rc=daily_radar.main()
    self.assertEqual(rc,1)
    manifest=json.loads((Path(td)/'daily_run_manifest.json').read_text())
    self.assertEqual(manifest['status'],'FAILED')
 def test_required_step_failure_is_reported_not_swallowed(self):
  with tempfile.TemporaryDirectory() as td:
   data=Path(td);(data/'radar.sqlite').write_bytes(b'placeholder')
   codes=[1]+[0]*(len(daily_radar.STEPS)-1)
   class Done:
    def __init__(self,code):self.returncode=code
   with patch.object(daily_radar,'DATA',data),patch.object(daily_radar.subprocess,'run',side_effect=lambda *a,**k:Done(codes.pop(0))):
    rc=daily_radar.main()
   self.assertEqual(rc,1)
   manifest=json.loads((data/'daily_run_manifest.json').read_text())
   self.assertEqual(manifest['status'],'FAILED')
   self.assertEqual(len(manifest['steps']),len(daily_radar.STEPS))
   self.assertEqual(manifest['steps'][0]['status'],'FAILED')
 def test_optional_step_failure_is_partial(self):
  with tempfile.TemporaryDirectory() as td:
   data=Path(td);(data/'radar.sqlite').write_bytes(b'placeholder')
   codes=[0]*len(daily_radar.STEPS)
   optional_index=next(i for i,(_,_,required) in enumerate(daily_radar.STEPS) if not required)
   codes[optional_index]=1
   class Done:
    def __init__(self,code):self.returncode=code
   with patch.object(daily_radar,'DATA',data),patch.object(daily_radar.subprocess,'run',side_effect=lambda *a,**k:Done(codes.pop(0))):
    rc=daily_radar.main()
   self.assertEqual(rc,0)
   self.assertEqual(json.loads((data/'daily_run_manifest.json').read_text())['status'],'PARTIAL')
if __name__=='__main__':unittest.main()
