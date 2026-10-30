import tempfile,unittest
from pathlib import Path
from municipal_full_document_ai import sections,extract_section,run
class FullDocumentTests(unittest.TestCase):
 def test_coverage_all_pages_and_long_page(self):
  pages=[{"page":1,"text":"A"*5001},{"page":2,"text":"Property 130 Augusta Avenue"},{"page":3,"text":""}]
  chunks=sections(pages,max_chars=2200)
  self.assertEqual([x["pages"][0]["page"] for x in chunks],[1,1,1,2])
  self.assertEqual(sum(len(x["pages"][0]["text"]) for x in chunks),5028)
 def test_multi_property_evidence_quote_is_checked(self):
  def transport(path,payload):
   self.assertEqual(payload["thinking"],{"type":"disabled"})
   import json
   return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps({"event_type":"tax_exemption","properties":[{"address":"130 Augusta Avenue","event_type":"tax_exemption","evidence_page":1,"evidence_excerpt":"130 Augusta Avenue"},{"address":"Fake address","evidence_page":1,"evidence_excerpt":"fabricated"}]})}}]}
  output,_=extract_section({"section":1,"pages":[{"page":1,"text":"Tax exemption for 130 Augusta Avenue"}]},"https://www.toronto.ca/report.pdf","demo",transport)
  self.assertEqual([x["grounded"] for x in output["properties"]],[True,False])
if __name__=="__main__":unittest.main()
