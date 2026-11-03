"""Policy-safe, bounded Guelph active application GIS regression tests."""
import datetime as dt
import unittest
from gta_guelph_gis import run,LAYER

META={"fields":[{"name":k} for k in (
    "REFERENCEFILE","FOLDERDESCRIPTION","ADDRESS","OBJECTID")]}
RAW={"features":[{"attributes":{
    "OBJECTID":1,"REFERENCEFILE":"OZS26-014",
    "ADDRESS":"175 Stone Road West","FOLDERDESCRIPTION":
    "Department-store associated industrial outdoor storage and service yard",
    "INDATE":1791504000000,"SUBDESC":"Zoning By-law Amendment",
    "url":"https://guelph.ca/2026/10/175-stone-road-west/"} }]}

class GuelphGIS(unittest.TestCase):
    def test_successful_baseline_then_unchanged(self):
        import tempfile
        def fetch(url,params):
            return META if url==LAYER else RAW
        with tempfile.TemporaryDirectory() as folder:
            first=run(folder,today=dt.date(2026,11,2),fetcher=fetch)
            second=run(folder,today=dt.date(2026,11,2),fetcher=fetch)
            self.assertEqual(first["commercial_candidates"],1)
            self.assertEqual(first["new_or_changed"],0)
            self.assertEqual(second["new_or_changed"],0)

    def test_reject_malformed_schema_without_baseline(self):
        import tempfile
        from pathlib import Path
        def fetch(url,params):
            return {"fields":[{"name":"OBJECTID"}]} if url==LAYER else RAW
        with tempfile.TemporaryDirectory() as folder:
            result=run(folder,fetcher=fetch)
            self.assertEqual(result["source_status"][0]["status"],"FAILED")
            self.assertFalse((Path(folder)/"GTA_RADAR_GUELPH_GIS_SEEN.json").exists())
