import json
import unittest
from municipal_ai_document_review import analyze, run

URL="https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf"
class MunicipalAIReviewTest(unittest.TestCase):
    def test_ai_calls_provider_with_report_and_rejects_unsupported_quotes(self):
        pages=[{"page":1,"text":"Planning Application Number: 26 132130 STE 14 OZ\nThis is a zoning report."}]
        def fake(path,payload):
            self.assertEqual(path,"/chat/completions")
            self.assertEqual(payload["messages"][1]["role"],"user")
            return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps({
                "claims":[
                    {"field":"application_ids","value":"26 132130 STE 14 OZ","page":1,"evidence_excerpt":"26 132130 STE 14 OZ"},
                    {"field":"developer","value":"Invented Developments","page":1,"evidence_excerpt":"A nonexistent sentence"}
                ],"supplier_selected":"UNKNOWN"})}}],"usage":{"prompt_tokens":100,"completion_tokens":80}}
        ans=analyze(pages,URL,"fake",transport=fake)
        self.assertEqual(len(ans["supported_claims"]),1)
        self.assertEqual(ans["rejected_claims"],1)
        self.assertEqual(ans["status"],"AI_REVIEW_ONLY_NOT_SALE_READY")

    def test_no_cost_without_explicit_paid_flag(self):
        self.assertEqual(run("nonexistent.pdf","x.json",URL)["paid_ai_calls"],0)

if __name__=="__main__":
    unittest.main()
