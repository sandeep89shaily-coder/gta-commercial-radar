import unittest, sqlite3
from unittest.mock import patch
from pathlib import Path
import tempfile
import brampton_network as b

class Response:
 def __init__(self,data):self.data=data
 def json(self):return self.data

class ArcGISSmallTests(unittest.TestCase):
 def test_sparse_ids_and_resume(self):
  db=sqlite3.connect(':memory:');b.setup(db)
  calls=[]
  def fake_get(session,url,params=None,**kw):
   calls.append(params)
   if params.get('returnIdsOnly')=='true':return Response({'objectIds':[9,2,17]})
   if params.get('f')=='json' and params.get('objectIds'):
    return Response({'features':[{'attributes':{'OBJECTID':int(x),'NAME':'Project'}} for x in params['objectIds'].split(',')]})
   return Response({'objectIdField':'OBJECTID','maxRecordCount':100})
  with patch.object(b,'get',fake_get),patch.object(b.time,'sleep'):
   status,n,*_=b.arcgis_small_by_ids(db,None,'t','https://example.com/FeatureServer/3','now',limit=2)
   self.assertEqual((status,n),('PARTIAL',2))
   self.assertEqual(db.execute('SELECT last_oid FROM arcgis_progress WHERE source_id=?',('t',)).fetchone()[0],9)
   status,n,*_=b.arcgis_small_by_ids(db,None,'t','https://example.com/FeatureServer/3','later',limit=2)
   self.assertEqual((status,n),('OK',1))
   self.assertEqual(db.execute('SELECT COUNT(*) FROM records WHERE source_id=?',('t',)).fetchone()[0],3)
  db.close()
 def test_missing_id_never_advances_checkpoint(self):
  db=sqlite3.connect(':memory:');b.setup(db)
  def fake_get(session,url,params=None,**kw):
   if params.get('returnIdsOnly')=='true':return Response({'objectIds':[2,9]})
   if params.get('objectIds'):return Response({'features':[{'attributes':{'OBJECTID':2}}]})
   return Response({'objectIdField':'OBJECTID'})
  with patch.object(b,'get',fake_get):
   with self.assertRaises(ValueError):b.arcgis_small_by_ids(db,None,'u','https://example.com/4','now')
  self.assertIsNone(db.execute("SELECT last_oid FROM arcgis_progress WHERE source_id='u'").fetchone())
  db.close()
if __name__=='__main__':unittest.main()
