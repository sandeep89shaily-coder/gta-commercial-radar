"""Read-only policy-safe audit of City of Barrie planning GIS layer metadata."""
from __future__ import annotations
import json
from gta_additional_city_gis import _read_json

ROOT="https://gispublic.barrie.ca/arcgis/rest/services/Public/AnnexedLand_ActiveApplications_WA_Static/MapServer"
def probe(fetch=_read_json):
 result={"source":ROOT,"status":"NOT_AVAILABLE","planning_layers":[]}
 try:
  meta=fetch(ROOT,{"f":"json"})
  layers=[x for x in meta.get("layers",[]) if
      "planning" in str(x.get("name","")).lower() and
      "application" in str(x.get("name","")).lower()]
  if not layers:
   result.update(status="NO_PLANNING_APPLICATION_LAYER");return result
  for x in layers:
   layer=fetch(ROOT+"/"+str(x["id"]),{"f":"json"})
   result["planning_layers"].append({"id":x["id"],"name":x["name"],
     "fields":[y.get("name") for y in layer.get("fields",[])],
     "capabilities":layer.get("capabilities","")})
  result["status"]="LAYER_METADATA_AVAILABLE"
 except Exception as e:
  result["status"]="SOURCE_POLICY_OR_NETWORK_FAILURE"
  result["error"]=type(e).__name__+":"+str(e)[:160]
 return result
if __name__=="__main__":
 print("BARRIE_GIS_SCHEMA_AUDIT",json.dumps(probe(),sort_keys=True),flush=True)
