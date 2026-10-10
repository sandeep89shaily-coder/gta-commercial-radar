import unittest
from ai_investigator import validate_answer,compact_evidence,extract_response
class TestAIInvestigator(unittest.TestCase):
    def test_rejects_unverified_fields(self):
        evidence=[{'id':'E1','url':'https://example.com','notes':'ABC Ltd owner Jane Doe jane@example.com'}]
        output=validate_answer({'evidence_ids':['E1'],'legal_company':'ABC Ltd','decision_maker':'Jane Doe','business_email':'fake@example.com'},evidence)
        self.assertEqual(output['decision_maker'],'Jane Doe')
        self.assertEqual(output['business_email'],'')
    def test_ignores_unsourced_evidence_ids(self):
        evidence=[{'id':'E1','url':'https://example.com','notes':'ABC Ltd'}]
        output=validate_answer({'evidence_ids':['E999'],'legal_company':'ABC Ltd'},evidence)
        self.assertEqual(output['legal_company'],'')
    def test_only_http_urls(self):
        evidence=compact_evidence([{'url':'file:///c:/secret','notes':'Local'},{'url':'https://example.com','notes':'Public'}])
        self.assertEqual(len(evidence),1)
if __name__=='__main__':unittest.main()
