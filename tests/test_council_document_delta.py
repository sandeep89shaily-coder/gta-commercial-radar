"""Offline acceptance for Datum-inspired meeting document discovery checks."""
import csv
import unittest
import datetime as dt
import json

from gta_council_document_delta import run, EVENTS, LEDGER, STATUS
from municipal_meeting_capture import OFFICIAL

NOW = dt.datetime(2026, 11, 12, 19, 0, tzinfo=dt.timezone.utc)


def html_for(*items):
    links = "".join(f'<a href="{url}">{title}</a>' for url, title in items)
    return "<html><body>" + links + "</body></html>"


def rows(folder):
    with (folder / EVENTS).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def check_initial_baseline_never_claims_new_publication(tmp_path):
    html = html_for(("/agenda-2026-11-12.pdf", "Planning staff report 2026 industrial development"))
    status = run("Brampton", tmp_path, fetch=lambda _: html, now=NOW)
    assert status["status"] == "INDEX_LINK_BASELINE_ONLY"
    assert status["first_observed_links"] == 0
    assert status["new_publications_verified"] == 0
    assert len(rows(tmp_path)) == 1
    assert rows(tmp_path)[0]["event"] == "BASELINE_EXISTING_LINK_NOT_NEW_PUBLICATION"
    assert rows(tmp_path)[0]["source_content_checked"] == "false"


def check_new_link_and_title_change_are_not_project_events(tmp_path):
    one = ("/agenda-2026-11-12.pdf", "Planning staff report 2026 industrial development")
    two = ("/minutes-2026-11-13.pdf", "Planning committee minutes 2026")
    run("Toronto", tmp_path, fetch=lambda _: html_for(one), now=NOW)
    after = run("Toronto", tmp_path, fetch=lambda _: html_for(
        (one[0], "Planning report 2026 revised industrial development"), two),
        now=NOW + dt.timedelta(days=1))
    assert after["first_observed_links"] == 1
    assert after["changed_link_titles"] == 1
    assert after["verified_projects"] == 0
    assert {r["event"] for r in rows(tmp_path)} == {
        "INDEX_LINK_TITLE_CHANGED_NOT_PROJECT_UPDATE",
        "FIRST_OBSERVED_LINK_NOT_NEW_PUBLICATION"}
    assert all(not r["publication_date"] for r in rows(tmp_path))


def check_blocked_source_keeps_prior_evidence_and_no_false_zero(tmp_path):
    run("Brampton", tmp_path, fetch=lambda _: html_for(
        ("/agenda-2026-11-12.pdf", "Planning report 2026 industrial")), now=NOW)
    prior = (tmp_path / LEDGER).read_bytes()
    from urllib.error import HTTPError
    def deny(_):
        raise HTTPError(OFFICIAL["Brampton"], 403, "Forbidden", {}, None)
    status = run("Brampton", tmp_path, fetch=deny, now=NOW + dt.timedelta(days=1))
    assert status["status"] == "SOURCE_HELD_NO_LEDGER_MUTATION"
    assert status["official_index_status"] == "HTTP_403_ACCESS_DENIED"
    assert (tmp_path / LEDGER).read_bytes() == prior


def check_missing_link_is_retained_without_removal_claim(tmp_path):
    first = ("/agenda-2026-11-12.pdf", "Planning report 2026 industrial")
    run("Toronto", tmp_path, fetch=lambda _: html_for(first), now=NOW)
    result = run("Toronto", tmp_path, fetch=lambda _: "<html></html>",
                 now=NOW + dt.timedelta(days=1))
    assert result["historical_links_retained"] == 1
    assert result["links_missing_from_current_index_not_removed"] == 1
    assert result["verified_projects"] == 0
    assert rows(tmp_path) == []


def check_invalid_city_refuses_unknown_public_source(tmp_path):
    try:
        run("Imaginary City", tmp_path, now=NOW)
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown city was accepted")
    assert not (tmp_path / LEDGER).exists()


class CouncilDocumentDeltaTests(unittest.TestCase):
    def test_baseline_and_observations(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        for case in (check_initial_baseline_never_claims_new_publication,
                     check_new_link_and_title_change_are_not_project_events,
                     check_blocked_source_keeps_prior_evidence_and_no_false_zero,
                     check_missing_link_is_retained_without_removal_claim,
                     check_invalid_city_refuses_unknown_public_source):
            with self.subTest(case=case.__name__), TemporaryDirectory() as directory:
                case(Path(directory))
