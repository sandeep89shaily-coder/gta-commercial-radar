"""YouTube Data API v3: approved metadata-only municipal video discovery.
No scraping, content downloads or caption downloads. Requires user's API key.
"""
import argparse,json,os
from urllib.parse import urlencode
from urllib.request import urlopen,Request
BASE="https://www.googleapis.com/youtube/v3/"
HANDLES={"Toronto":"@TorontoCityCouncilLive"}
def fetch_json(endpoint,params,*,fetch=None):
 if fetch:return fetch(endpoint,params)
 u=BASE+endpoint+"?"+urlencode(params)
 with urlopen(Request(u,headers={"User-Agent":"GTARadarMunicipalMeetingMetadata/1.0"}),timeout=15) as h:
  if h.status!=200:raise RuntimeError("YouTube Data API unavailable")
  raw=h.read(500001)
  if len(raw)>500000:raise ValueError("API result over bounded size")
 return json.loads(raw)
def list_videos(city,api_key,*,limit=20,fetch=None):
 if city not in HANDLES:raise ValueError("Unknown municipality")
 if not api_key:return {"status":"API_KEY_REQUIRED","records":[]}
 q={"part":"contentDetails","forHandle":HANDLES[city],"key":api_key}
 channels=fetch_json("channels",q,fetch=fetch).get("items",[])
 if not channels:return {"status":"OFFICIAL_CHANNEL_NOT_FOUND","records":[]}
 uploads=channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
 items=fetch_json("playlistItems",{"part":"snippet","playlistId":uploads,"maxResults":min(50,max(1,limit)),"key":api_key},fetch=fetch).get("items",[])
 rows=[]
 for item in items:
  meta=item.get("snippet",{});video=meta.get("resourceId",{}).get("videoId","")
  import re
  if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video):continue
  rows.append({"recording_url":"https://www.youtube.com/watch?v="+video,
    "title":meta.get("title",""),"published_at":meta.get("publishedAt"),
    "official_channel_handle":HANDLES[city],"agenda_match":"UNRESOLVED",
    "downloaded":False})
 return {"status":"OFFICIAL_API_METADATA_ONLY","records":rows}
def main():
 p=argparse.ArgumentParser();p.add_argument("--city",choices=list(HANDLES),required=True)
 p.add_argument("--out",required=True);a=p.parse_args()
 from pathlib import Path
 key=os.environ.get("YOUTUBE_DATA_API_KEY","")
 result=list_videos(a.city,key)
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2),encoding="utf-8")
 print(json.dumps({"status":result["status"],"recordings":len(result["records"])},indent=2))
if __name__=="__main__":main()
