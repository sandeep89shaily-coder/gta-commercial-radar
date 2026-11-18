"""No-network acceptance: one 16+8 Radar collection and contact-first research."""
from __future__ import annotations
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
import gta_24_city_combined as m


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fp:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


class Combined24CityTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        write_csv(self.root/"GTA_RADAR_COLLECTION_HEALTH.csv", [
            {"city": city, "source_failures": "2" if city=="Brampton" else "0",
             "source_notes":"ROBOTS_DENIED" if city=="Brampton" else ""}
            for city in m.CORE_CITIES])
        write_csv(self.root/"GTA_RADAR_COLLECTION_MASTER.csv", [
            {"canonical_id":"TORONTO:FILE:SPA2026021","city":"Toronto",
             "application_id":"SPA-2026-021","record_kind":"APPLICATION_ID",
             "description":"Under review industrial warehouse addition to a factory",
             "current_status":"UNDER REVIEW", "date":"2026-11-12",
             "date_basis":"OFFICIAL_APPLICATION_RECEIVED_NOT_FIRST_PUBLICATION",
             "address":"100 Example Industrial Road",
             "source_types":"TORONTO_CKAN","evidence_urls":"https://www.toronto.ca/plan/21",
             "first_seen_local":"2026-11-17", "observation":"FIRST_OBSERVED"},
            {"canonical_id":"MISSISSAUGA:FILE:21TM153","city":"Mississauga",
             "application_id":"21T-M 15-3","record_kind":"APPLICATION_ID",
             "description":"Site plan for a new industrial warehousing complex",
             "current_status":"Under review", "date":"",
             "date_basis":"", "address":"7140 Hurontario Street",
             "source_types":"EARLY_HTML",
             "evidence_urls":"https://www.mississauga.ca/plan/7140",
             "first_seen_local":"2026-11-02", "observation":"UNCHANGED"}])
        write_csv(self.root/"GTA_RADAR_MISSISSAUGA_DETAIL_APPLICATIONS.csv",[
            {"city":"Mississauga","application_id":"21T-M15-3",
             "address":"7140 Hurontario Street",
             "project_title":"7140 Hurontario industrial application",
             "description":"Seven industrial buildings with an internal private road",
             "applicant_name_source_claim":"1105239 Ontario Inc.",
             "city_planner_name":"Connor Di Pietro",
             "city_planner_email":"connor.dipietro@mississauga.ca",
             "publisher_page_posted_date":"2025-12-01",
             "record_source_url":"https://www.mississauga.ca/plan/7140",
             "observation":"UNCHANGED"}])
        write_csv(self.root/"GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv",[
            {"project_id":"N1","city":"Niagara Falls",
             "application_id":"AM-2026-013","address":"8168 McLeod Road",
             "description":"Zoning bylaw amendment","applicant":"",
             "official_record_url":"https://webpublic.niagarafalls.ca/Planning/Details/411",
             "first_seen_local":"2026-11-12","observation":"UNCHANGED"},
            {"project_id":"P1","city":"Peterborough",
             "application_id":"SPC-2026-112","address":"10 Peterborough Road",
             "description":"Industrial warehouse and logistics distribution centre",
             "applicant":"Example Planning Group",
             "official_record_url":"https://www.peterborough.ca/planning/112",
             "first_seen_local":"2026-11-11","observation":"UNCHANGED"}])
        write_csv(self.root/"GTA_RADAR_THREE_CITY_EVIDENCE_CANDIDATES.csv",[
            {"city":"Niagara Falls","candidate_key":"NF-1",
             "source_lane":"NIAGARA_APPLICATION_DETAIL",
             "application_id":"AM-2026-013","address":"8168 McLeod Road",
             "scope":"Proposed commercial pharmacy and retail store with parking",
             "application_status":"PLANNING_APPLICATION_MEETING",
             "meeting_date":"2026-11-24",
             "source_url":"https://webpublic.niagarafalls.ca/Planning/Details/411",
             "record_kind":"OFFICIAL_APPLICATION_OR_NOTICE_REVIEW",
             "first_seen_local":"2026-11-17","observation":"INITIAL_BASELINE_NOT_NEW_PUBLICATION"},
            {"city":"St. Catharines","candidate_key":"SC-1",
             "source_lane":"STC_PLANNING_NOTICE",
             "application_id":"26 106602 OP",
             "address":"109 St. Paul Crescent",
             "scope":"A 15-room institutional and mixed-use commercial annex building",
             "application_status":"PUBLIC_PLANNING_NOTICE",
             "notice_posted_date":"2026-11-12",
             "application_complete_date":"2025-10-16",
             "planner_name":"Dasha Litviniuc",
             "planner_email_public":"dlitviniuc@stcatharines.ca",
             "source_url":"https://www.stcatharines.ca/news/posts/notice/",
             "record_kind":"OFFICIAL_APPLICATION_NOTICE",
             "first_seen_local":"2026-11-17", "observation":"UNCHANGED"}])
        write_csv(self.root/"GTA_RADAR_NORTHERN_MAJOR_CITY_EVIDENCE.csv",[
            {"candidate_id":"BPL","city":"Barrie","source_lane":"BARRIE_PLANNING",
             "record_kind":"OFFICIAL_BARRIE_PLANNING_APPLICATION",
             "application_id":"D11-022-2026","address":"131 Lockhart Road",
             "scope":"Industrial building for crane manufacturing with 4151 square metres",
             "current_status":"UNDER REVIEW",
             "applicant_name_source_claim":"ISM Architects on behalf of Canadian Crane",
             "source_date":"2026-09-28",
             "source_date_basis":"OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION",
             "original_record_url":"https://gispublic.barrie.ca/plan/4",
             "first_seen_local":"2026-11-17","observation":"UNCHANGED"},
            {"candidate_id":"BPM","city":"Barrie","source_lane":"BARRIE_ISSUED_PERMITS",
             "record_kind":"OFFICIAL_BARRIE_ISSUED_PERMIT",
             "application_id":"PMT26-0331","address":"130 Storage Road",
             "scope":"New industrial shell permit issued in 2025",
             "current_status":"Issued",
             "source_date":"2025-10-01",
             "source_date_basis":"OFFICIAL_PERMIT_STATUS_DATE_NOT_PUBLICATION",
             "original_record_url":"https://gispublic.barrie.ca/permit/1",
             "first_seen_local":"2026-11-17","observation":"UNCHANGED"}])
        write_csv(self.root/"GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_REVIEW.csv",[
            {"city":"Whitby","record_id":"WHITBY-ONE",
             "record_kind":"PROJECT_NOTICE_SIGNAL",
             "application_id":"", "project_title":"114 Winchester Road",
             "description":"Mixed use commercial retail zoning planning notice",
             "official_notice_url":"https://www.whitby.ca/public-meetings/",
             "first_seen_local":"2026-11-11","observation":"UNCHANGED"}])
        (self.root/"GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json").write_text(
            json.dumps({"sources":[{"city":"Brantford","source_lane":"PLANNING",
                "status":"SOURCE_BLOCKED_OR_UNSUPPORTED",
                "failures":["ROBOTS_ACCESS_DENIED"]}]}))
        # Real source readiness is accepted only when status files are newer
        # than this integrated full run's reported start time.
        (self.root/"MONDAY_FULL_RADAR").mkdir(exist_ok=True)
        (self.root/"MONDAY_FULL_RADAR"/"MONDAY_FULL_RADAR_STATUS.json").write_text(
            json.dumps({"started_utc": (
                dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=60)
                ).isoformat()}))
        (self.root/"GTA_RADAR_NORTHERN_MAJOR_CITY_STATUS.json").write_text(
            json.dumps({"source_details":[
                {"city":"Greater Sudbury","lane":"PENDING_PLANNING",
                 "status":"INDEX_ONLY_OR_NO_EXACT_COMMERCIAL_IDS",
                 "supplemental_notice_document_links":20},
                {"city":"North Bay","lane":"PUBLIC_PLANNING_NOTICES",
                 "status":"NO_EXACT_PLANNING_NOTICES_DISCOVERED"}]}))

    def test_all_24_cities_combined_without_inventing_coverage(self):
        status=m.run(self.root,today=dt.date(2026,11,18))
        self.assertEqual(status["configured_city_count"],24)
        self.assertEqual(status["core_city_count"],16)
        self.assertEqual(status["expansion_city_count"],8)
        self.assertEqual(len(m.CITIES),len(set(m.CITIES)))
        allrows=read_csv(self.root/m.MASTER)
        allcity=read_csv(self.root/m.COVERAGE)
        self.assertEqual(len(allcity),24)
        self.assertEqual(len(allrows),8)
        self.assertEqual(status["unique_application_files_in_combined_master"],6)
        self.assertEqual(status["historical_permit_records_separate_from_applications"],1)
        self.assertEqual(status["project_only_signals_not_applications"],1)
        self.assertEqual(status["verified_buyers"],0)
        self.assertEqual(status["verified_new_publications"],0)
        self.assertIn("Brantford",status["cities_without_application_files"])
        self.assertEqual(next(x for x in allcity if x["city"]=="Brantford")[
            "source_health"],"PARTIAL_SOURCE_FAILURE_OR_BLOCKED")
        self.assertEqual(next(x for x in allcity if x["city"]=="Greater Sudbury")[
            "application_files"],"0")
        self.assertFalse(status["standard_paid_ai_top10_includes_expansion"])

    def test_city_id_dedup_keeps_mississauga_company_and_niagara_scope(self):
        m.run(self.root,today=dt.date(2026,11,18))
        rows=read_csv(self.root/m.MASTER)
        miss=[r for r in rows if r["city"]=="Mississauga"]
        niag=[r for r in rows if r["city"]=="Niagara Falls"]
        self.assertEqual(len(miss),1)
        self.assertEqual(miss[0]["applicant_or_agent_source_claim"],"1105239 Ontario Inc.")
        self.assertEqual(miss[0]["published_contact_email"],
                         "connor.dipietro@mississauga.ca")
        self.assertEqual(miss[0]["purchasing_contact_verified"],"False")
        self.assertEqual(len(niag),1)
        self.assertIn("retail store",niag[0]["scope"])
        self.assertIn("GGH_APPLICATION",niag[0]["source_lanes"])
        self.assertIn("NIAGARA_APPLICATION_DETAIL",niag[0]["source_lanes"])

    def test_top10_spans_both_cohorts_without_permits_or_false_buyers(self):
        m.run(self.root,today=dt.date(2026,11,18))
        chosen=read_csv(self.root/m.TOP10)
        self.assertGreaterEqual(len(chosen),3)
        self.assertEqual({r["cohort"] for r in chosen},{"CORE_16","EXPANSION_8"})
        self.assertNotIn("PERMIT",{r["record_kind"] for r in chosen})
        self.assertTrue(all(r["purchasing_contact_verified"]=="False" for r in chosen))
        self.assertTrue(all(r["open_supplier_contract_verified"]=="False" for r in chosen))

    def test_paid_ai_candidate_pool_uses_original_and_expansion_cities(self):
        from gta_24_city_ai_selection import candidates
        m.run(self.root,today=dt.date(2026,11,18))
        selected=candidates(self.root,today=dt.date(2026,11,18))
        self.assertGreaterEqual(len(selected),3)
        self.assertEqual({r["cohort"] for r in selected},
                         {"CORE_16","EXPANSION_8"})
        self.assertTrue(all(r["origin"]=="COMBINED_24" for r in selected))
        self.assertTrue(all(r["application_id"] and r["record_id"] and
                            r["source_url"].startswith("https://")
                            for r in selected))
        self.assertNotIn("PMT26-0331",{r["application_id"] for r in selected})

    def test_final_combined_ai_top10_evidence_guard_and_fallback(self):
        from gta_24_city_ai_selection import (
            candidates, finalize, FINAL_TOP10, FINAL_STATUS)
        from gta_commercial_qualification_review import ai_fingerprint
        m.run(self.root,today=dt.date(2026,11,18))
        day=dt.date(2026,11,18)
        pool=candidates(self.root,today=day)
        bad=finalize(self.root,pool=pool,today=day,state={
            "status":"AI_PRESELECTION_INCOMPLETE", "reviewed_count":1,
            "reviews":[{"record_id":pool[0]["record_id"],"decision":"PREFER"}],
            "input_fingerprint":ai_fingerprint(pool),
        })
        self.assertFalse(bad["model_decisions_applied"])
        self.assertEqual(bad["top10_count"],len(read_csv(self.root/m.TOP10)))
        self.assertTrue(all(x["ai_reviewed"]=="False" for x in
                            read_csv(self.root/FINAL_TOP10)))
        reviews=[
            {"record_id":p["record_id"],
             "decision":"PREFER" if i==0 else "NEUTRAL",
             "reason":"Verify exact project role and original notice",
             "next_check":"Search original applicant and construction firm",
             "cited_live_source":{"url":p["source_url"],
                "quote":"Literal independently fetched project text"}
                    if i==0 else None,
             "buyer_function_hypothesis":{"function":"UNKNOWN"}}
            for i,p in enumerate(pool)
        ]
        state={
            "status":"AI_TOP10_REVIEW_ONLY","input_fingerprint":ai_fingerprint(pool),
            "reviewed_count":len(pool),"applies_to_top10":True,
            "recheck_date":day.isoformat(),"reviews":reviews}
        good=finalize(self.root,pool=pool,today=day,state=state)
        self.assertTrue(good["model_decisions_applied"])
        self.assertEqual(good["candidate_pool_count"],len(pool))
        selected=read_csv(self.root/FINAL_TOP10)
        self.assertTrue(all(x["ai_reviewed"]=="True" for x in selected))
        self.assertTrue(all(x["purchasing_contact_verified"]=="False" and
                            x["open_supplier_contract_verified"]=="False"
                            for x in selected))
        canonical=json.loads((self.root/"GTA_RADAR_COMBINED_24_CITY_STATUS.json").read_text())
        self.assertTrue(canonical["standard_paid_ai_top10_includes_expansion"])
        self.assertFalse(canonical["standard_paid_ai_top10_already_runs_in_upstream_daily_stage"])

    def test_all_24_sources_report_live_readiness_not_fictitious_citywide(self):
        from gta_24_city_source_readiness import run as source_readiness
        from gta_24_city_source_readiness import OUTPUT
        m.run(self.root,today=dt.date(2026,11,18))
        report=source_readiness(self.root,today=dt.date(2026,11,18))
        self.assertEqual(report["configured_cities"],24)
        self.assertTrue(report["source_health_checked_for_every_configured_city"])
        self.assertEqual(report["citywide_complete_coverage_verified"],0)
        self.assertIn("Brantford",report["blocked_city_names"])
        self.assertIn("Greater Sudbury",
                      report["cities_without_live_application_source_rows"])
        rows=read_csv(self.root/OUTPUT)
        self.assertEqual(len(rows),24)
        self.assertTrue(all(x["citywide_complete_coverage_verified"]=="False"
                            for x in rows))
        self.assertIn("FAILED",next(r for r in rows if r["city"]=="Brantford")[
            "measured_source_readiness"])
        self.assertEqual(next(r for r in rows if r["city"]=="Greater Sudbury")[
            "live_sources_with_application_ids"],"0")

    def test_stale_source_status_not_mistaken_for_current_collection(self):
        import os
        from gta_24_city_source_readiness import run as source_readiness, OUTPUT
        m.run(self.root,today=dt.date(2026,11,18))
        path=self.root/"GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json"
        start=json.loads((self.root/"MONDAY_FULL_RADAR"/
            "MONDAY_FULL_RADAR_STATUS.json").read_text())["started_utc"]
        old=dt.datetime.fromisoformat(start).timestamp()-3600
        os.utime(path, (old,old))
        result=source_readiness(self.root,today=dt.date(2026,11,18))
        status=next(r for r in read_csv(self.root/OUTPUT)
                    if r["city"]=="Brantford")
        self.assertEqual(status["blocked_or_failed_lanes"],"0")
        self.assertEqual(result["citywide_complete_coverage_verified"],0)

    def test_unchanged_must_not_falsely_become_changed_and_gain_rank_points(self):
        self.assertFalse(m._explicit_source_change("UNCHANGED"))
        self.assertFalse(m._explicit_source_change("INITIAL_BASELINE_NOT_NEW"))
        self.assertFalse(m._explicit_source_change("HISTORICAL_OR_UNCHANGED_BASELINE"))
        self.assertTrue(m._explicit_source_change("SOURCE_CHANGED_NOT_VERIFIED_NEW_PROJECT"))
        self.assertTrue(m._explicit_source_change("DETAIL_PAGE_CHANGED_NOT_NEW_PUBLICATION"))
        m.run(self.root,today=dt.date(2026,11,18))
        master=read_csv(self.root/m.MASTER)
        miss=next(row for row in master if row["city"]=="Mississauga")
        niag=next(row for row in master if row["city"]=="Niagara Falls")
        self.assertEqual(miss["source_observation"],
                         "HISTORICAL_OR_UNCHANGED_BASELINE")
        self.assertEqual(niag["source_observation"],
                         "HISTORICAL_OR_UNCHANGED_BASELINE")
        older=dict(miss)
        changed=dict(miss)
        changed["source_observation"]="SOURCE_CHANGED_NEEDS_REVIEW"
        self.assertEqual(m._rank(changed,dt.date(2026,11,18))-
                         m._rank(older,dt.date(2026,11,18)), 7)

    def test_explicit_inactive_project_is_excluded_even_if_stage_under_review(self):
        from gta_24_city_ai_selection import _model_row
        original={
            "canonical_id":"TORONTO:FILE:12228867ESC40SA",
            "city":"Toronto","cohort":"CORE_16","application_id":"12 228867 ESC 40 SA",
            "record_kind":"APPLICATION","address":"30 Progress Avenue",
            "scope":"INACTIVE Proposed place of worship in existing industrial building",
            "project_title":"", "current_status":"Under Review",
            "source_date":"", "source_date_basis":"UNKNOWN",
            "official_evidence_urls":"https://open.toronto.ca/dataset/development-applications/",
            "source_observation":"HISTORICAL_OR_UNCHANGED_BASELINE",
            "commercial_text_match":"True",
            "applicant_or_agent_source_claim":"", "published_contact_email":"",
        }
        self.assertIsNone(m._rank(original,dt.date(2026,11,18)))
        self.assertIsNone(_model_row(original))
        original["scope"]="ACTIVE Site plan proposal for a new industrial building"
        self.assertIsNotNone(m._rank(original,dt.date(2026,11,18)))
        self.assertIsNotNone(_model_row(original))

    def test_core16_required_cannot_replace_with_eight_pilots(self):
        (self.root/"GTA_RADAR_COLLECTION_HEALTH.csv").unlink()
        with self.assertRaisesRegex(ValueError,"CORE_16_COLLECTION_MISSING"):
            m.run(self.root,today=dt.date(2026,11,18))

    def test_municipal_coverage_is_not_sale_ready_even_with_names(self):
        status=m.run(self.root,today=dt.date(2026,11,18))
        self.assertEqual(status["status"],
            "COMBINED_16_PLUS_8_RESEARCH_ONLY_NOT_CUSTOMER_RELEASE")
        self.assertFalse(status["all_citywide_coverage_verified"])
        self.assertEqual(status["verified_open_supplier_contracts"],0)
        self.assertEqual(status["additional_paid_ai_calls"],0)


if __name__ == "__main__":
    unittest.main()
