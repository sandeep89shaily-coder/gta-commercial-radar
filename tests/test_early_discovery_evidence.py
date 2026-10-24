"""No network/unit-only: discover only official links and refuse incomplete sources."""
import sqlite3
import json
import tempfile
import unittest
from pathlib import Path
import early_discovery_watch as d
import early_evidence_match as m

HOME="""<html><body><nav><div>Current Development Projects
<a href="/en/news/current-development-projects/ward1.aspx">Ward 1</a>
<a href="/en/news/current-development-projects/ward2.aspx">Ward 2</a>
<a href="/en/news/current-development-projects/ward3.aspx">Ward 3</a>
<a href="/en/news/current-development-projects/ward4.aspx">Ward 4</a>
<a href="/en/news/current-development-projects/ward5.aspx">Ward 5</a>
<a href="/en/news/current-development-projects/ward6.aspx">Ward 6</a>
</div></nav></body></html>"""
WARD="""<html><body><h1>Current Development Projects Ward 1</h1>
<a href="/en/news/current-development-projects/new-industrial-center.aspx">Factory upgrade</a>
<a href="https://example.com/other.aspx">Outside site</a></body></html>"""
PROJECT="""<html><body><h1>New industrial center</h1>
<p>Status - Pre-Application</p><h2>Ward 1 Site Address</h2><p>100 Test Road</p>
<h3>Applicant</h3><p>Example Industries</p><h3>Proposed Development</h3>
<p>Industrial warehouse and loading dock expansion.</p>
<h3>Public Meetings</h3><p>Pre-Application Community Meeting</p></body></html>"""
CAL="""<html><body><div class="meeting-row">
<h3>Planning and Development Committee</h3><a href="Meeting.aspx?Agenda=Agenda&amp;Id=25022e86-016b-490b-b051-1bae3971fa77&amp;lang=English">See more</a>
</div><div class="meeting-row"><h3>City Council</h3>
<a href="Meeting.aspx?Agenda=Agenda&amp;Id=b1b11e86-016b-490b-b051-1bae3971fa77&amp;lang=English">See more</a></div>
</body></html>"""
AGENDA="""<html><body><h1>Agenda</h1><h2>Planning and Development Committee</h2>
<p>Date: Monday, May 11, 2026</p><h3>6.1</h3>
<p>File: OZS-2026-0006 - Public Meeting</p>
<p>Applicant/Consultant: Example Services, Example Developments Inc.</p>
<p>Purpose: To permit a new industrial distribution centre and loading dock development.</p>
<p>Location: 100 Test Road, Ward 4</p>
<h3>7.2</h3><p>File: OZS-2026-0009</p>
<p>Applicant/Consultant: Residential Development Ltd.</p>
<p>Purpose: To permit 18 townhouse dwellings.</p><p>Location: 200 House Road, Ward 5</p>
</body></html>"""


class Reply:
    def __init__(self,txt):self.text=txt
    def raise_for_status(self):pass
class Session:
    def __init__(self,urls):self.urls=urls
    def get(self,url,**kwargs):
        if url not in self.urls:raise d.requests.RequestException("mock missing")
        return Reply(self.urls[url])


class DiscoveryTests(unittest.TestCase):
    def test_burlington_ward_and_project_discovery(self):
        wards=d.discover_burlington_ward_urls(HOME)
        self.assertEqual(len(wards),6)
        links=d.discover_burlington_project_urls(WARD,wards[0])
        self.assertEqual(len(links),1)
        self.assertIn("new-industrial-center.aspx",list(links)[0])
        session=Session({d.BURLINGTON_HOME:HOME,
                 **{url:WARD for url in wards},
                 "https://www.burlington.ca/en/news/current-development-projects/new-industrial-center.aspx":PROJECT})
        records,stat=d.burlington_records(session)
        self.assertEqual(stat["discovered"],1)
        self.assertEqual(records[0]["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(records[0]["stage"],"Pre-Application")
        self.assertEqual(records[0]["source_date"],"")
        self.assertEqual(records[0]["procurement_status"],"UNKNOWN")

    def test_burlington_incomplete_ward_fails(self):
        with self.assertRaisesRegex(RuntimeError,"ward"):
            d.discover_burlington_ward_urls("<html><p>not linked</p></html>")

    def test_brampton_calendar_selects_only_planning_meetings(self):
        meetings=d.parse_calendar(CAL)
        self.assertEqual(len(meetings),1)
        self.assertIn("25022e86",next(iter(meetings.values())))
        self.assertNotIn("b1b11e86",str(meetings))

    def test_brampton_agenda_extracts_planning_items_not_buyers(self):
        url=next(iter(d.parse_calendar(CAL).values()))
        records=d.parse_meeting_agenda(AGENDA,url)
        self.assertEqual(len(records),2)
        self.assertIn("OZS-2026-0006",records[0]["record_id"])
        self.assertEqual(records[0]["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(records[0]["source_date"],"")
        self.assertEqual(records[0]["meeting_date"],"2026-05-11")
        self.assertEqual(records[0]["procurement_status"],"UNKNOWN")
        self.assertEqual(records[1]["commercial_fit"],"RESIDENTIAL_LIKELY")

    def test_blocked_source_keeps_prior_snapshots(self):
        with tempfile.TemporaryDirectory() as t:
            opts=dict(data_dir=Path(t)/"db",out_dir=Path(t)/"results",
                      source=["brampton_planning_agendas"])
            url=next(iter(d.parse_calendar(CAL).values()))
            self.assertEqual(d.run(**opts,session=Session({
                d.BRAMPTON_CALENDAR:CAL,url:AGENDA}),now="2026-10-24T11:00:00+00:00"),0)
            self.assertEqual(d.run(**opts,session=Session({}),
                now="2026-10-25T11:00:00+00:00"),1)
            db=sqlite3.connect(Path(t)/"db"/"early_discovery_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            db.close()


class EvidenceTests(unittest.TestCase):
    def test_strict_normalization_and_identity_not_autoproven(self):
        self.assertEqual(m.norm_address("55 Hereford St."),"55 HEREFORD ST")
        self.assertEqual(m.norm_address("55 Hereford Street"),"55 HEREFORD ST")
        self.assertEqual(m.norm_address("56 Hereford Street"),"56 HEREFORD ST")
        self.assertEqual(m.norm_address("0 Mayfield Road"),"") # unknown parcel not valid site
        self.assertEqual(m.norm_city("York Region (Vaughan included)"),"")
        self.assertEqual(m.norm_city("Brampton"),"BRAMPTON")

    def test_proposal_dates_are_not_automatically_post_dates(self):
        a=m.unpack(dict(source_id="brampton_site_plans",city="Brampton",
          location="55 Hereford Street",source_application_date="2026-10-15",
          feature_id="3",commercial_signal="POSSIBLE_COMMERCIAL"),"s","2026-10-24T10:00:00")
        b=m.unpack(dict(source_id="brampton_planning_agendas",site="55 Hereford St",
          record_id="x",source_date="",company="Consulting firm",
          commercial_fit="POSSIBLE_COMMERCIAL"),"p","2026-10-23T10:00:00")
        self.assertEqual(a["source_application_date"],"2026-10-15")
        self.assertEqual(a["source_public_posted"],"")
        links=m.join_signals([a,b])
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]["match_status"],
             "POSSIBLE_SAME_ADDRESS_NOT_VERIFIED_SAME_PROJECT")
        self.assertEqual(links[0]["earlier_public_date_advantage_days"],"")
        gate=m.gates([a,b],links)
        self.assertEqual(gate[0]["lead_status"],"NOT_SALE_READY_RESEARCH_ONLY")
        self.assertEqual(gate[0]["vendor_status"],"UNKNOWN")

    def test_no_cross_city_or_ambiguous_site_link(self):
        a=m.unpack(dict(source_id="pickering_proposals",site="55 King Road",
                record_id="a",commercial_fit="POSSIBLE_COMMERCIAL"),"p","2026-10-21")
        b=m.unpack(dict(source_id="milton_notices",site="55 King Rd",
                record_id="b",commercial_fit="POSSIBLE_COMMERCIAL"),"m","2026-10-21")
        self.assertEqual(len(m.join_signals([a,b])),0)


if __name__=="__main__":unittest.main()
