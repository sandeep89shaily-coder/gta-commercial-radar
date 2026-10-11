import io
import sqlite3
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
import brampton_network as b

class HtmlResponse:
 def __init__(self, text, url):self.text=text;self.url=url

class DocumentCollectorTests(unittest.TestCase):
 def test_rejects_external_documents_and_stores_page_and_link(self):
  db=sqlite3.connect(':memory:');b.setup(db)
  html='<html><main><p>This planning and council page has a genuine published update with sufficient details for collection.</p><a href="/docs/report.pdf">Planning report</a><a href="https://evil.example/report.pdf">External report</a></main></html>'
  def get_fake(session,url,**kwargs):
   if url.endswith('report.pdf'):
    class Pdf:
     content=b'<html>not a PDF</html>'
    return Pdf()
   return HtmlResponse(html,'https://www.brampton.ca/planning/')
  with patch.object(b,'get',get_fake),patch.dict(b.os.environ,{'BRAMPTON_PDFS_PER_SOURCE':'1'}):
   status,seen,created,changed,detail=b.content_monitor(db,None,'planning','https://www.brampton.ca/planning/','now')
  self.assertEqual(status,'PARTIAL')
  self.assertEqual(db.execute("SELECT COUNT(*) FROM records WHERE source_id='planning'").fetchone()[0],2)
  self.assertIn('PDF failures',detail)
  db.close()
if __name__=='__main__':unittest.main()
