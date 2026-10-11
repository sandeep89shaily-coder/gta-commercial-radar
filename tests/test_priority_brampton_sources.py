import sqlite3,unittest
from unittest.mock import patch
import brampton_network as b
class Response:
 def __init__(self,obj):self.obj=obj
 def json(self):return self.obj
class PrioritySourcesTests(unittest.TestCase):
 def test_roadworks_uses_safe_id_fallback(self):
  db=sqlite3.connect(':memory:');b.setup(db)
  calls=[]
  def getter(session,url,params=None,**kwargs):
   calls.append(params)
   if params.get('returnIdsOnly')=='true':return Response({'objectIds':[12,18]})
   if params.get('objectIds'):return Response({'error':{'code':400,'message':'query rejected'}})
   if ' IN (' in params.get('where',''):return Response({'features':[{'attributes':{'OBJECTID':12}},{'attributes':{'OBJECTID':18}}]})
   return Response({'objectIdField':'OBJECTID','maxRecordCount':25})
  with patch.object(b,'get',side_effect=getter),patch.object(b.time,'sleep'):
   status,n,*_=b.arcgis_small_by_ids(db,None,'road','https://example.com/0','now')
  self.assertEqual((status,n),('OK',2))
  self.assertTrue(any(' IN (' in p.get('where','') for p in calls))
  db.close()
 def test_public_tender_source_monitored(self):
  matches=[r for r in b.SOURCES if r[0]=='brampton_procurement_bid_opportunities']
  self.assertEqual(len(matches),1)
  self.assertIn('brampton.bidsandtenders.ca',matches[0][3])
  self.assertEqual(matches[0][4],'content_monitor')
if __name__=='__main__':unittest.main()
