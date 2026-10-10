import unittest
from regional_activation import classify_result, summarize

class RolloutResultTests(unittest.TestCase):
    def test_skip_with_exit_two_is_not_failure(self):
        self.assertEqual(classify_result(2, '-> SKIPPED: scheduled snapshot not yet due (3-day cadence); existing records preserved')[0], 'SKIPPED_NOT_DUE')
    def test_weekly_skip(self):
        self.assertEqual(classify_result(2, '-> SKIPPED: scheduled snapshot not yet due (7-day cadence); existing records preserved')[0], 'SKIPPED_NOT_DUE')
    def test_successful_import(self):
        self.assertEqual(classify_result(0, '-> BASELINE/full: fetched=22; current=22\nFinished. Open: dashboard.html')[0], 'IMPORTED')
    def test_other_nonzero_is_failure(self):
        self.assertEqual(classify_result(2, 'ERROR: 401 unauthorized')[0], 'FAILED')
    def test_zero_without_success_evidence_is_failure(self):
        self.assertEqual(classify_result(0, 'Unexpected empty output')[0], 'FAILED')
    def test_counts(self):
        self.assertEqual(summarize([{'result':'IMPORTED'},{'result':'SKIPPED_NOT_DUE'},{'result':'FAILED'}])['SKIPPED_NOT_DUE'], 1)
if __name__=='__main__':unittest.main()
