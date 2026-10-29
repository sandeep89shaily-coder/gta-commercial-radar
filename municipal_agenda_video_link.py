"""Conservative explicit-link association of meeting video with official agenda.

Only an exact recording URL in a municipality-authored agenda is VERIFIED.
Date/name similarity is not a verified association.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from municipal_meeting_capture import normalize_video,public_https,Links
OFFICIAL_AGENDA_HOSTS={"pub-brampton.escribemeetings.com","www.toronto.ca",
                       "secure.toronto.ca","www1.brampton.ca","www.brampton.ca"}
def match_video(recording_url,agenda_url,agenda_html):
 p=urlparse(agenda_url)
 if not public_https(agenda_url) or p.hostname not in OFFICIAL_AGENDA_HOSTS:
  raise ValueError("Only official municipal agenda URL allowed")
 video=normalize_video(recording_url)
 if not video:raise ValueError("Valid single recording URL required")
 parser=Links();parser.feed(agenda_html)
 found={normalize_video(urljoin(agenda_url,u)) for tag,u,title in parser.values}
 if video in found:
  return {"agenda_url":agenda_url,"recording_url":video,
          "agenda_match":"VERIFIED_OFFICIAL_AGENDA_VIDEO_LINK",
          "evidence":"EXACT_VIDEO_LINK_IN_OFFICIAL_AGENDA"}
 return {"agenda_url":agenda_url,"recording_url":video,
         "agenda_match":"NOT_VERIFIED","evidence":"NO_EXACT_LINK_FOUND"}
