import unittest
from unittest.mock import Mock
from disabled_source_sample_audit import probe
class SampleTests(unittest.TestCase):
    def test_sample_reads_only_three_and_never_writes(self):
        reply=Mock(content=b'{}')
        reply.json.return_value={"features":[{"attributes":{"APP":"1","DATE":123}},{"attributes":{"APP":"2","DATE":456}}]}
        session=Mock();session.get.return_value=reply
        result=probe({"id":"test","collector":"arcgis","query_url":"https://example.org/query","key_fields":["APP"],"date_fields":["DATE"]},session)
        self.assertEqual(result["status"],"SAMPLE_KEYS_PRESENT")
        self.assertEqual(result["date_field_present"],"True")
        self.assertEqual(session.get.call_args.kwargs["params"]["resultRecordCount"],3)
    def test_duplicate_keys_flagged(self):
        reply=Mock(content=b'{}')
        reply.json.return_value={"features":[{"attributes":{"APP":"1"}},{"attributes":{"APP":"1"}}]}
        session=Mock();session.get.return_value=reply
        result=probe({"id":"test","collector":"arcgis","url":"https://example.org/0","key_fields":["APP"]},session)
        self.assertEqual(result["status"],"KEY_QUALITY_REVIEW")
    def test_empty_sample_not_success(self):
        reply=Mock(content=b'{}');reply.json.return_value={"features":[]}
        session=Mock();session.get.return_value=reply
        result=probe({"id":"test","collector":"arcgis","url":"https://example.org/0"},session)
        self.assertEqual(result["status"],"EMPTY_SAMPLE_NOT_VALIDATED")
if __name__=="__main__":unittest.main()
