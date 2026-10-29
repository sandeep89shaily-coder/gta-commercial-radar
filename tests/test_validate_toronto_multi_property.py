import unittest
from validate_toronto_multi_property import evaluate
class GoldTest(unittest.TestCase):
 def test_missed_properties_reported_and_partial_coverage(self):
  gold={"source_url":"official","expected_properties":[{"address":"25 Eden Place","page":2},{"address":"175 Oak Street","page":3}]}
  rows=[{"address":"175 Oak Street","grounded":True}]
  result=evaluate(gold,rows,{"sections_total":9,"sections_succeeded":3,"sections_unprocessed":6})
  self.assertEqual(result["property_group_recall"],.5)
  self.assertEqual(result["missed_properties"],["25 Eden Place"])
  self.assertFalse(result["fully_processed"])
if __name__=="__main__":unittest.main()
