"""Regression checks for buyer/procurement proof separation."""
import csv
from gta_buyer_verification import run, INPUT, EVIDENCE, REVIEW


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_no_buyer_inferred_from_named_company(tmp_path):
    write(tmp_path / INPUT,[{"rank":1,"opportunity_id":"A1","city":"Brampton","address":"1 Test Road","project_name":"Factory","named_company_role_unverified":"Some Co","source_url":"https://example.com/source"}])
    status=run(tmp_path)
    with (tmp_path / REVIEW).open(encoding="utf-8-sig") as f:
        row=next(csv.DictReader(f))
    assert status["independently_verified_open_packages"] == 0
    assert row["buyer_organization"] == ""
    assert row["procurement_stage"] == "UNKNOWN"
    assert row["review_state"] == "HOLD_MANUAL_VERIFICATION"


def test_conflicting_site_not_promoted(tmp_path):
    write(tmp_path / INPUT,[{"opportunity_id":"A1","city":"Toronto","address":"10 One St"}])
    write(tmp_path / EVIDENCE,[{"opportunity_id":"A1","city":"Toronto","address":"20 Two St","buyer_organization":"Test Buyer","buyer_role":"OWNER","buyer_evidence_url":"https://example.com/owner","procurement_stage":"OPEN","procurement_evidence_url":"https://example.com/bid"}])
    run(tmp_path)
    with (tmp_path / REVIEW).open(encoding="utf-8-sig") as f: row=next(csv.DictReader(f))
    assert "EVIDENCE_IDENTITY_CONFLICT" in row["review_flags"]
    assert row["buyer_organization"] == ""
    assert row["procurement_stage"] == "UNKNOWN"


def test_fully_evidenced_claim_still_human_review_only(tmp_path):
    write(tmp_path / INPUT,[{"opportunity_id":"A1","city":"Toronto","address":"10 One St"}])
    write(tmp_path / EVIDENCE,[{"opportunity_id":"A1","city":"Toronto","address":"10 One St","buyer_organization":"Test Buyer","buyer_role":"OWNER","buyer_evidence_url":"https://example.com/owner","public_business_contact":"procurement@example.com","contact_role":"BUYER PROCUREMENT","contact_evidence_url":"https://example.com/contact","procurement_stage":"OPEN","procurement_evidence_url":"https://example.com/tender"}])
    status=run(tmp_path)
    with (tmp_path / REVIEW).open(encoding="utf-8-sig") as f: row=next(csv.DictReader(f))
    assert row["review_state"]=="EVIDENCE_READY_FOR_INDEPENDENT_RECHECK"
    assert status["customer_ready_claims"] == 0
    assert status["independently_verified_open_packages"] == 0
