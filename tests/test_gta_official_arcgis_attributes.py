import json,unittest
from gta_official_arcgis_attributes import is_official_query,parse_features,retrieve
URL="https://services6.arcgis.com/hM5ymMLbxIyWTjn2/arcgis/rest/services/Issued_Building_Permits/FeatureServer/0/query?where=BP_NO%3D%27BP+3ALT+26-2522%27&outFields=%2A&returnGeometry=false&f=json"
class ArcGISAttributesTests(unittest.TestCase):
 def test_exact_id_and_without_schema_bloat(self):
  body={"fields":[{"name":"BP_NO","description":"X"*5000}],
        "features":[{"attributes":{"BP_NO":"BP 3ALT 26-2522","STATUS":"ISSUED","DESCRIPTION":"Interior retail alteration","ADDRESS":"3899 TRELAWNY CIR"}}]}
  result=retrieve(URL,"BP 3ALT 26-2522",transport=lambda _:json.dumps(body))
  self.assertIn("Interior retail alteration",result)
  self.assertNotIn("XXXXX",result)
  self.assertIsNone(parse_features(body,"WRONG"))
 def test_blocks_nonofficial_hosts(self):
  self.assertFalse(is_official_query(URL.replace("services6.arcgis.com","evil.example")))
if __name__=="__main__":unittest.main()
