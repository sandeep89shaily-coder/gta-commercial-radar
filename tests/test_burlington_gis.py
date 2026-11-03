"""Burlington GIS source integrity: project signals are not applications."""
import tempfile
import unittest
from pathlib import Path
from gta_burlington_gis import LAYER,run

class BurlingtonGIS(unittest.TestCase):
    def test_baseline_no_fresh_applications(self):
        def fake(url,params):
            if url==LAYER:
                return {"fields":[{"name":k} for k in
                    ("OBJECTID","NAME","PROJECTWEBSITE","LOCATION","WARD")]}
            return {"features":[{"attributes":{
                "OBJECTID":22,"NAME":"Industrial warehouse at 800 Burloak",
                "LOCATION":"800 Burloak Drive","WARD":5,
                "PROJECTWEBSITE":"https://www.burlington.ca/800Burloak/"}}]}
        with tempfile.TemporaryDirectory() as folder:
            one=run(folder,fetcher=fake)
            two=run(folder,fetcher=fake)
            self.assertEqual(one["project_only_signals"],1)
            self.assertEqual(one["application_id_rows"],0)
            self.assertEqual(one["new_or_changed"],0)
            self.assertEqual(two["new_or_changed"],0)
            self.assertTrue((Path(folder)/"GTA_RADAR_BURLINGTON_GIS_SEEN.json").exists())
    def test_bad_schema_does_not_create_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            result=run(folder,fetcher=lambda url,p:{"fields":[]})
            self.assertEqual(result["status"],"FAILED")
            self.assertFalse((Path(folder)/"GTA_RADAR_BURLINGTON_GIS_SEEN.json").exists())
