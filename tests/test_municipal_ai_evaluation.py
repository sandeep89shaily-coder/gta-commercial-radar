import unittest
from municipal_ai_evaluation import evaluate

class AIEvaluationTest(unittest.TestCase):
    def test_citations_precision_recall_are_independent(self):
        gold={"pages":[{"page":1,"text":"Developer: Acme Holdings. Planning Application: 26 132130 STE 14 OZ"}],
              "expected":[{"field":"developer","value":"Acme Holdings"},{"field":"application_ids","value":"26 132130 STE 14 OZ"}],
              "verified_real_pdf":False}
        response={"supported_claims":[
            {"field":"developer","value":"Acme Holdings","page":1,"evidence_excerpt":"Developer: Acme Holdings"},
            {"field":"stage","value":"Under construction","page":1,"evidence_excerpt":"Planning Application"}]}
        report=evaluate(response,gold)
        self.assertEqual(report["precision"],0.5)
        self.assertEqual(report["recall"],0.5)
        self.assertEqual(report["quotes_on_cited_page"],2)
        self.assertFalse(report["real_document_validated"])
        self.assertFalse(report["buyer_verified"])
if __name__=="__main__":
    unittest.main()
