"""Separate receipt date from PUBLIC publication date; reviewer evidence required."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
import early_leadtime_evidence as m

PAIR=dict(city="BRAMPTON",normalized_site="55 HEREFORD ST",
 first_source="brampton_preconsultation",first_record_id="PRE-2026-0042",
 other_source="brampton_site_plans",other_record_id="SPA-2026-0101",
 first_official_link="https://www.brampton.ca/planning/pre",
 other_official_link="https://www.brampton.ca/planning/site")

class Tests(unittest.TestCase):
    def test_publication_comparison_needs_verified_project(self):
        row=m._fresh(PAIR)
        self.assertEqual(m.measure(row,dt.date(2026,10,24))[0],
                         "SAME_PROJECT_NOT_VERIFIED")
        row.update(same_project_reviewed="YES",
            identity_evidence_url="https://www.brampton.ca/planning/record",
            earlier_public_notice_url="https://www.brampton.ca/notice/public",
            later_public_notice_url="https://www.brampton.ca/notice/site",
            earlier_public_date="2026-08-01",later_public_date="2026-10-10",
            earlier_public_event_type="PRE_APPLICATION_PUBLIC_NOTICE",
            later_public_event_type="FORMAL_SITE_PLAN_FIRST_PUBLIC_POSTED",
            reviewer="Human",reviewed_on="2026-10-24")
        state,days=m.measure(row,dt.date(2026,10,24))
        self.assertEqual(days,"70")
        self.assertEqual(state,"REVIEWER_ATTESTED_DATE_COMPARISON_VERIFY_URLS")
        row["earlier_public_event_type"]="APPLICATION_RECEIVED"
        self.assertEqual(m.measure(row,dt.date(2026,10,24))[0],
                         "EARLY_EVENT_TYPE_NOT_COMPARABLE")
        row["earlier_public_event_type"]="PRE_APPLICATION_PUBLIC_NOTICE"
        row["earlier_public_date"]="2026-11-01"
        self.assertEqual(m.measure(row,dt.date(2026,10,24))[0],
                         "PUBLICATION_DATES_UNVERIFIED")

    def test_earlier_vs_later_negative_requires_review(self):
        row=m._fresh(PAIR)
        row.update(same_project_reviewed="YES",
            identity_evidence_url="https://www.brampton.ca/planning/record",
            earlier_public_notice_url="https://www.brampton.ca/notice/public",
            later_public_notice_url="https://www.brampton.ca/notice/site",
            earlier_public_date="2026-10-22",later_public_date="2026-10-11",
            earlier_public_event_type="PRE_APPLICATION_PUBLIC_NOTICE",
            later_public_event_type="BUILDING_PERMIT_FIRST_PUBLIC_POSTED",
            reviewer="Human",reviewed_on="2026-10-24")
        self.assertEqual(m.measure(row,dt.date(2026,10,24)),
                         ("LATER_EVENT_PUBLISHED_FIRST_REVIEW","-11"))

    def test_prev_annotations_retained(self):
        prior=m._fresh(PAIR)
        prior["reviewer"]="Investigator"
        current=m.merge([PAIR],[prior])
        self.assertEqual(current[0]["reviewer"],"Investigator")
        self.assertEqual(current[0]["measurement_status"],"NOT_MEASURED")
        self.assertEqual(m.merge([],[prior])[0]["reviewer"],"Investigator")

    def test_no_matched_files_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.run(str(Path(d)/"notfound.csv"),d),1)

    def test_run_writes_zero_historical_proof(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            m._write(base/"MATCH.csv",tuple(PAIR.keys()),[PAIR])
            self.assertEqual(m.run(base/"MATCH.csv",base),0)
            with (base/"EARLY_LEADTIME_EVIDENCE_SUMMARY.csv").open(
                encoding="utf-8-sig",newline="") as f:
                data={r["metric"]:r["value"] for r in csv.DictReader(f)}
            self.assertEqual(data["positive_early_disclosure_examples"],"0")

if __name__=="__main__":unittest.main()
