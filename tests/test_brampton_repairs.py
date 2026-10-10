import sqlite3,sys,tempfile,unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import brampton_network as b

class FakeResponse:
 def __init__(self,data):self.data=data
 def json(self):return self.data

class TestBramptonRepairs(unittest.TestCase):
 def test_parser_split_columns_and_reject_combined(self):
  soup=BeautifulSoup('<table><tr><th>Organization Name</th><th>Contractor Operating Name</th><th>Business Address</th><th>Expiry Date</th><th>File Number</th></tr><tr><td>123 Ontario Inc.</td><td>Cafe</td><td>1 Main St Brampton</td><td>2027-01-31</td><td>FH123</td></tr></table>','html.parser')
  rows=b.parse_licence_table(soup.table)
  self.assertEqual(rows[0]['operating_name'],'Cafe')
  self.assertEqual(rows[0]['file_number'],'FH123')
  bad=BeautifulSoup('<table><tr><th>Organization Name Contractor Operating Name Business Address Expiry Date File Number</th></tr><tr><td>all fields mashed together</td></tr></table>','html.parser')
  self.assertEqual(b.parse_licence_table(bad.table),[])
 def test_cursor_resume_no_restarts(self):
  with tempfile.TemporaryDirectory() as td:
   con=sqlite3.connect(':memory:');b.setup(con)
   values=[{'OBJECTID':i,'label':str(i)} for i in range(1,8)]
   previous=b.get
   def fake(session,url,params=None,**kw):
    if url.endswith('/query'):
     if params.get('returnCountOnly'):return FakeResponse({'count':len(values)})
     n=int(params['where'].split('>')[1]);k=params['resultRecordCount']
     return FakeResponse({'features':[{'attributes':x} for x in values if x['OBJECTID']>n][:k]})
    return FakeResponse({'objectIdField':'OBJECTID','maxRecordCount':2})
   b.get=fake
   try:
    a=b.arcgis(con,None,'brampton_permit_activity','any','now',limit=3)
    self.assertEqual(a[1:4],(3,3,0))
    q=con.execute('SELECT last_oid FROM arcgis_progress').fetchone()[0];self.assertEqual(q,3)
    a=b.arcgis(con,None,'brampton_permit_activity','any','later',limit=3)
    self.assertEqual(a[1:4],(3,3,0))
    self.assertEqual(con.execute('SELECT COUNT(*) FROM records').fetchone()[0],6)
   finally:b.get=previous
 def test_retry_http_failure(self):
  import requests
  class S:
   calls=0
   def get(self,*args,**kwargs):
    self.calls+=1
    raise requests.exceptions.Timeout('timed out')
  old=b.time.sleep;b.time.sleep=lambda n:None
  try:
   s=S()
   with self.assertRaises(requests.exceptions.Timeout):b.get(s,'https://example.invalid',attempts=2)
   self.assertEqual(s.calls,2)
  finally:b.time.sleep=old
if __name__=='__main__':unittest.main()
