import unittest
from audit_batch import assess_schema
class BatchAuditTests(unittest.TestCase):
    def test_missing_configured_fields_flagged(self):
        s={'key_fields':['OBJECTID'],'incremental_fields':['LAST_EDIT']}
        m={'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}]}
        missing,_,_=assess_schema(s,m)
        self.assertIn('incremental_fields:LAST_EDIT',missing)
    def test_text_date_not_treated_as_incremental(self):
        s={'key_fields':['OBJECTID'],'incremental_fields':['RECEIVED']}
        m={'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'},{'name':'RECEIVED','type':'esriFieldTypeString'}]}
        missing,nondate,_=assess_schema(s,m)
        self.assertEqual([],missing)
        self.assertEqual(['RECEIVED'],nondate)
    def test_real_date_type_allowed(self):
        s={'incremental_fields':['MODIFIED']}
        m={'fields':[{'name':'MODIFIED','type':'esriFieldTypeDate'}]}
        self.assertEqual([],assess_schema(s,m)[1])
