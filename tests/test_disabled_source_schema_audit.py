import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from disabled_source_schema_audit import probe,audit

class SchemaAuditTests(unittest.TestCase):
    def test_matching_metadata_is_not_live_collection(self):
        response=Mock(status_code=200,content=b'{}')
        response.json.return_value={"fields":[{"name":"APP_ID"},{"name":"SUBMITTED"}]}
        session=Mock();session.get.return_value=response
        source={"id":"test","enabled":False,"collector":"arcgis",
                "url":"https://official.example/FeatureServer/0",
                "key_fields":["APP_ID"],"date_fields":["SUBMITTED"]}
        row=probe(source,session)
        self.assertEqual(row["schema_status"],"FIELDS_MATCH_CONFIG")
        self.assertEqual(session.get.call_args.kwargs["params"],{"f":"json"})
    def test_missing_key_is_a_mismatch(self):
        response=Mock(status_code=200,content=b'{}')
        response.json.return_value={"fields":[{"name":"OTHER"}]}
        session=Mock();session.get.return_value=response
        row=probe({"id":"a","collector":"arcgis","url":"https://official.example/FeatureServer/0",
                   "key_fields":["APP_ID"],"date_fields":[]},session)
        self.assertEqual(row["schema_status"],"CONFIG_FIELD_MISMATCH")
        self.assertEqual(row["missing_keys"],"APP_ID")
    def test_non_arcgis_not_misreported_as_healthy(self):
        row=probe({"id":"history","collector":"ckan"})
        self.assertEqual(row["schema_status"],"NOT_ARCGIS_REQUIRES_OTHER_PROBE")
    def test_invalid_url_does_not_call_network(self):
        session=Mock()
        row=probe({"id":"invalid","collector":"arcgis","url":"http://local"},session)
        self.assertEqual(row["schema_status"],"INVALID_ENDPOINT")
        session.get.assert_not_called()

if __name__=="__main__":unittest.main()
