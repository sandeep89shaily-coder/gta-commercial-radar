import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock
from regional_pipeline import assess_record_sample,make_html

class RegionalPipelineTests(unittest.TestCase):
    def test_sample_keys(self):
        http=Mock()
        http.get.return_value.json.return_value={'features':[{'attributes':{'CASE_ID':'123'}}]}
        s={'query_url':'https://example.test/query','key_fields':['CASE_ID']}
        self.assertEqual((1,''),assess_record_sample(s,http))
    def test_sample_key_missing(self):
        http=Mock()
        http.get.return_value.json.return_value={'features':[{'attributes':{'OTHER':'123'}}]}
        s={'query_url':'https://example.test/query','key_fields':['CASE_ID']}
        self.assertIn('absent',assess_record_sample(s,http)[1])
    def test_report_escapes_remote_text(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'audit.html'
            make_html([{'region':'Hamilton','id':'abc','result':'REVIEW','full_count':1,'recent_count':0,'sample_count':3,'issues':'<script>alert(1)</script>','sample_issue':''}],path)
            h=path.read_text()
            self.assertNotIn('<script>',h)
            self.assertIn('&lt;script&gt;',h)
if __name__=='__main__':unittest.main()
