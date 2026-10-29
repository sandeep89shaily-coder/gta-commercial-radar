import unittest,tempfile
from pathlib import Path
from municipal_youtube_api import list_videos
from municipal_meeting_capture import capture
from municipal_agenda_video_link import match_video
class SourceAPITests(unittest.TestCase):
 def test_official_data_api_discovers_metadata_without_downloading(self):
  calls=[]
  def fake(endpoint,params):
   calls.append(endpoint)
   if endpoint=="channels":return {"items":[{"contentDetails":{"relatedPlaylists":{"uploads":"PL_TEST"}}}]}
   return {"items":[{"snippet":{"resourceId":{"videoId":"abcdefghijk"},
     "title":"Toronto Planning and Housing Committee","publishedAt":"2026-10-15T00:00:00Z"}}]}
  result=list_videos("Toronto","test_api_key",fetch=fake)
  self.assertEqual(calls,["channels","playlistItems"])
  self.assertFalse(result["records"][0]["downloaded"])
  self.assertEqual(result["records"][0]["agenda_match"],"UNRESOLVED")
 def test_no_platform_permission_no_download(self):
  with tempfile.TemporaryDirectory() as td:
   result=capture("https://www.youtube.com/watch?v=abcdefghijk",td,authorized=True)
   self.assertFalse(result["media_downloaded"])
   self.assertEqual(result["status"],"PLATFORM_DOWNLOAD_PERMISSION_NOT_VERIFIED")
 def test_official_agenda_requires_actual_recording_link(self):
  url="https://pub-brampton.escribemeetings.com/Meeting.aspx?Id=test"
  found=match_video("https://www.youtube.com/watch?v=abcdefghijk",url,
    '<a href="https://www.youtube.com/watch?v=abcdefghijk">Recording</a>')
  self.assertEqual(found["agenda_match"],"VERIFIED_OFFICIAL_AGENDA_VIDEO_LINK")
  missing=match_video("https://www.youtube.com/watch?v=abcdefghijk",url,"<p>Video coming soon</p>")
  self.assertEqual(missing["agenda_match"],"NOT_VERIFIED")
if __name__=="__main__":unittest.main()
