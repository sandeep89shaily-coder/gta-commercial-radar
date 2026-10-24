"""Offline regression of real official Ajax ArcGIS source schema and full-batch baseline."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_ajax_arcgis as gis
import early_ajax_watch as app

FIELDS=["OBJECTID","REF_ID","ADDRESS","DESCRIPTION","STATUS","APPLICANT","SUBMISSION_DATE"]
def attributes(layer,oid):
    return dict(OBJECTID=oid,REF_ID=f"SPA-{oid}/26",
      ADDRESS="500 Salem Road North" if layer==1 else "595 Mackenzie Avenue",
      DESCRIPTION="Industrial warehouse with loading dock" if layer==1 else "",
      STATUS="Active",APPLICANT="Published Test Developer" if layer==1 else None,
      TYPE="Industrial" if layer==1 else "",SUBMISSION_DATE=1790208000000 if layer==1 else None,
      TOTAL_NONRES_SQ=2100 if layer==1 else 0)
class R:
    def __init__(self,body):self.body=body
    def raise_for_status(self):pass
    def json(self):return self.body
class Session:
    def __init__(self,broken=False):self.broken=broken
    def get(self,url,params=None,**kwargs):
        layer=int(url.split("/MapServer/")[1].split("/")[0])
        if not url.endswith("/query"):
            return R({"fields":[{"name":x} for x in FIELDS],"name":"Pre-consultation" if layer==0 else "Active Applications"})
        if params.get("returnIdsOnly")=="true":
            return R({"objectIds":[1,2]})
        ids=[int(x) for x in params["objectIds"].split(",")]
        if self.broken and layer==1:ids=ids[:-1]
        return R({"features":[{"attributes":attributes(layer,k)} for k in ids]})
    def post(self,url,data=None,**kwargs):
        return self.get(url,data,**kwargs)

class Tests(unittest.TestCase):
    def test_live_gis_source_layers_and_real_submission_dates(self):
        rows,counts=gis.collect(Session())
        self.assertEqual(counts,{0:2,1:2})
        self.assertEqual(len(rows),4)
        pre,active=rows[0],rows[2]
        self.assertEqual(pre["stage"],"PRECONSULTATION_Active")
        self.assertEqual(active["company"],"Published Test Developer")
        self.assertEqual(active["source_application_date"],"2026-09-24")
        self.assertEqual(active["source_date"],"")
        self.assertEqual(active["procurement_status"],"UNKNOWN")
        self.assertEqual(active["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(active["attributes"]["nonres_floor_area_m2"],2100)

    def test_incomplete_feature_response_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"incomplete"):
            gis.collect(Session(broken=True))

    def test_no_blind_zero_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            opts=dict(data_dir=d/"data",out_dir=d/"out")
            self.assertEqual(app.run(**opts,session=Session(),stamp="2026-10-24T16:00:00Z"),0)
            self.assertEqual(app.run(**opts,session=Session(),stamp="2026-10-25T16:00:00Z"),0)
            db=sqlite3.connect(d/"data"/"early_ajax_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],4)
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            db.close()
            self.assertEqual(app.run(**opts,session=Session(broken=True),stamp="2026-10-26T16:00:00Z"),1)

if __name__=="__main__":unittest.main()
