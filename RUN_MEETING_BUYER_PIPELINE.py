"""One review-only municipal meeting discovery-to-buyer research entrypoint.

The public official discovery page is read first; user may explicitly authorize
a selected recording's caption capture. Procurement checks remain unverified.
"""
import argparse,json
from pathlib import Path
from municipal_meeting_capture import discover,capture
from municipal_captions_to_transcript import convert
from municipal_official_buyer_research import shortlist
from municipal_buyer_procurement import PORTALS
from municipal_evidence_graph import graph
from municipal_agenda_video_link import match_video
def pipeline(city,out,*,recording_url=None,capture_authorized=False,address=None,
             fetch=None,runner=None,research_fetch=None,discover_archive=False,deepseek_buyer=False,results=None,agenda_url=None,agenda_html=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 meeting=discover(city,fetch=fetch)
 if discover_archive and city=="Toronto":
  try:
   from municipal_youtube_api import list_videos
   import os
   api=list_videos("Toronto",os.environ.get("YOUTUBE_DATA_API_KEY",""))
   archive=[{"recording_url":x["recording_url"],"meeting_title_unverified":x["title"],"discovery_source":"OFFICIAL_YOUTUBE_DATA_API"} for x in api["records"]]
   meeting["archive_discovery_status"]=api["status"]
   known={x["recording_url"] for x in meeting["meetings"]}
   for m in archive:
    if m["recording_url"] not in known:
     meeting["meetings"].append({"recording_url":m["recording_url"],
       "official_discovery_url":meeting["official_page"],
       "agenda_directory_url":"https://www.toronto.ca/city-government/council/council-committee-meetings/",
       "agenda_match":"UNRESOLVED_NEEDS_OFFICIAL_MEETING_ID",
       "title_hint":m["meeting_title_unverified"],"city":city,
       "capture_status":"LINK_ONLY_NOT_DOWNLOADED",
       "archive_channel_url":m["discovery_source"]})
   meeting["discovered"]=len(meeting["meetings"])
  except Exception as exc:
   meeting["archive_discovery_status"]="UNAVAILABLE_"+type(exc).__name__
 if agenda_url and agenda_html and recording_url:
  association=match_video(recording_url,agenda_url,Path(agenda_html).read_text(encoding="utf-8"))
  for item in meeting["meetings"]:
   if item["recording_url"]==association["recording_url"]:
    item["agenda_match"]=association["agenda_match"]
    item["agenda_evidence_url"]=agenda_url
 discovery=out/(city.upper()+"_MEETINGS.json")
 discovery.write_text(json.dumps(meeting,indent=2),encoding="utf-8")
 state={"city":city,"official_videos_discovered":meeting["discovered"],
    "meeting_index":str(discovery),"caption_status":"NOT_REQUESTED",
    "buyer_evidence_status":"NOT_REQUESTED","verified_leads":0}
 if recording_url:
  official={x["recording_url"] for x in meeting["meetings"]}
  if recording_url not in official:
   state["caption_status"]="RECORDING_NOT_MATCHED_TO_OFFICIAL_INDEX"
  elif capture_authorized:
   result=capture(recording_url,out/"CAPTIONS",authorized=True,
                  **({"runner":runner} if runner else {}))
   state["caption_status"]=result["status"]
   state["caption_audit"]=result
   if result["status"]=="CAPTIONS_CAPTURED":
    from municipal_meeting_capture import normalize_video
    import hashlib
    folder=out/"CAPTIONS"/hashlib.sha256(normalize_video(recording_url).encode()).hexdigest()[:20]
    cap=next((x for x in sorted(folder.iterdir()) if x.suffix.lower() in (".vtt",".srt")),None)
    if cap:
     state["transcript"]=convert(cap,out/"MEETING_TRANSCRIPT.csv",recording_url)
 if address:
  research=shortlist(address,list(PORTALS.values()),fetch=research_fetch) if research_fetch else shortlist(address,list(PORTALS.values()))
  buyer_file=out/"BUYER_OFFICIAL_SOURCE_AUDIT.json"
  buyer_file.write_text(json.dumps(research,indent=2),encoding="utf-8")
  state["buyer_evidence_status"]="SOURCE_CHECKED_NOT_VERIFIED"
  state["buyer_audit"]=str(buyer_file)
 buyer_ai_file=None
 if deepseek_buyer and address:
  if not results:raise ValueError("Existing shared results folder needed for DeepSeek")
  from municipal_deepseek_buyer_research import propose
  source_rows=[x for x in research["observations"] if x.get("quote")]
  if source_rows:
   buyer_ai_file=out/"DEEPSEEK_BUYER_REVIEW.json"
   state["buyer_ai_result"]=propose(source_rows[:8],results,buyer_ai_file,paid=True)
 graph_data=graph(meeting=str(discovery),buyer_ai=str(buyer_ai_file) if buyer_ai_file and buyer_ai_file.is_file() else None)
 (out/"PROJECT_EVIDENCE_GRAPH.json").write_text(json.dumps(graph_data,indent=2),encoding="utf-8")
 (out/"INTEGRATED_PILOT_AUDIT.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
 return state
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--city",choices=["Toronto","Brampton"],required=True)
 p.add_argument("--out",required=True)
 p.add_argument("--recording-url")
 p.add_argument("--authorize-caption-capture",action="store_true")
 p.add_argument("--address")
 p.add_argument("--discover-archive",action="store_true")
 p.add_argument("--deepseek-buyer",action="store_true")
 p.add_argument("--results")
 p.add_argument("--agenda-url")
 p.add_argument("--agenda-html")
 a=p.parse_args()
 print(json.dumps(pipeline(a.city,a.out,recording_url=a.recording_url,
   capture_authorized=a.authorize_caption_capture,address=a.address,
   discover_archive=a.discover_archive,deepseek_buyer=a.deepseek_buyer,results=a.results,agenda_url=a.agenda_url,agenda_html=a.agenda_html),indent=2))
if __name__=="__main__":main()
