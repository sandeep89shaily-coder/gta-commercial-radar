import unittest
from unittest.mock import patch, Mock
from toronto_public_records import parse_public_xml, fetch, SPECS

class TorontoXMLTests(unittest.TestCase):
 def test_repeated_records_are_normalized(self):
  xml=b'<Contracts><Contract><Request_Number>100</Request_Number><Vendor_Name>XYZ</Vendor_Name><Contract_Amount>2500</Contract_Amount></Contract><Contract><Request_Number>200</Request_Number><Vendor_Name>ABC</Vendor_Name><Contract_Amount>3600</Contract_Amount></Contract></Contracts>'
  out=parse_public_xml(xml)
  self.assertEqual(len(out),2)
  self.assertEqual(out[0]['VENDOR_NAME'],'XYZ')
  self.assertEqual(out[1]['REQUEST_NUMBER'],'200')
 def test_reject_dtd_and_ambiguous_nested_data(self):
  with self.assertRaises(ValueError):
   parse_public_xml(b'<!DOCTYPE records [<!ENTITY spy "bad">]><records/>')
  with self.assertRaises(ValueError):
   parse_public_xml(b'<records><row><nested><x>1</x></nested><name>test</name></row></records>')
 def test_xml_resource_can_be_fetched_and_parsed(self):
  class Http:
   def get(self,url,**kwargs):
    return Mock(content=b'<Contracts><Contract><Request_Number>100</Request_Number><Vendor_Name>XYZ</Vendor_Name></Contract><Contract><Request_Number>200</Request_Number><Vendor_Name>ABC</Vendor_Name></Contract></Contracts>')
  pkg={'id':'p','name':'tobids-non-competitive-contracts'}
  res={'id':'r','name':'Non-Competitive Contracts','format':'XML','url':'https://example.com/contract.xml'}
  with patch('toronto_public_records.resolve_ckan_package',return_value=pkg):
   with patch('toronto_public_records.choose_ckan_resource',return_value=res):
    rows,meta=fetch(Http(),next(s for s in SPECS if s['id']=='toronto_noncompetitive_contracts'))
  self.assertEqual(len(rows),2)
  self.assertEqual(meta['format'],'XML')
if __name__=='__main__':unittest.main()
