import unittest
from lead_candidates import candidates_from_changes
class CandidateTests(unittest.TestCase):
    def test_multi_buyer_hypotheses_not_qualified(self):
        c=candidates_from_changes([dict(source_id='x',change_type='NEW',entity_name='New Restaurant',address='10 Main St',description='Restaurant fitout',commercial_relevance='HIGH')])
        self.assertGreaterEqual(len(c),2)
        self.assertTrue(all(x['review_status']=='UNVERIFIED_NOT_FOR_SALE' for x in c))
    def test_low_and_removed_ignored(self):
        for typ,rel in [('NEW','LOW'),('REMOVED','HIGH')]:
            self.assertEqual(candidates_from_changes([dict(change_type=typ,commercial_relevance=rel,entity_name='Restaurant',address='1 Main')]),[])
    def test_unknown_no_keyword_ignored(self):
        self.assertEqual(candidates_from_changes([dict(change_type='UPDATED',entity_name='Applicant',address='1 Main',description='site plan',commercial_relevance='UNKNOWN')]),[])
