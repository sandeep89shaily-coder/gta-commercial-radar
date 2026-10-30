import unittest
from gta_lead_time_proof import validate,audit
class DateProofTests(unittest.TestCase):
 def test_real_dates_and_matched_id_required(self):
  base={"official_project_id":"A-1","same_project_match_reviewed":True,
  "first_public_url":"https://example.org/notice","first_public_at":"2026-01-01T12:00:00-05:00",
  "radar_first_seen_at":"2026-01-03T12:00:00-05:00",
  "later_permit_url":"https://example.org/permit","later_permit_public_at":"2026-02-01T12:00:00-05:00"}
  proof=validate(base)
  self.assertEqual(proof["status"],"MEASURABLE")
  self.assertEqual(proof["days_radar_after_first_public"],2)
  self.assertEqual(proof["days_radar_to_permit"],29)
  self.assertEqual(validate({**base,"same_project_match_reviewed":False})["status"],"PROJECT_IDENTITY_NOT_VERIFIED")
  self.assertEqual(validate({**base,"first_public_url":""})["status"],"INSUFFICIENT_PROVENANCE")
  self.assertEqual(validate({**base,"radar_first_seen_at":"2025-12-30T12:00:00-05:00"})["status"],"CHRONOLOGY_CONFLICT")
if __name__=="__main__":unittest.main()
