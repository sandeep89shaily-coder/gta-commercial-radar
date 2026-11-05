"""Vaughan access denial is audited, never treated as successful collection."""
from urllib.error import HTTPError
from municipal_meeting_capture import discover, OFFICIAL
from RUN_MEETING_BUYER_PIPELINE import pipeline
import json


def forbidden(url):
    raise HTTPError(url,403,"Forbidden",{},None)


def test_vaughan_403_not_exception_or_false_evidence():
    record=discover("Vaughan",fetch=forbidden)
    assert record["official_index_status"]=="HTTP_403_ACCESS_DENIED"
    assert record["discovered"]==0
    assert record["meetings"]==[]
    assert record["agenda_candidates"]==[]
    assert record["publication_dates_verified"]==0


def test_403_keeps_meeting_audit_and_status(tmp_path):
    result=pipeline("Vaughan",tmp_path,fetch=forbidden)
    assert result["official_index_status"]=="HTTP_403_ACCESS_DENIED"
    assert result["official_videos_discovered"]==0
    assert result["agenda_links_discovered"]==0
    persisted=json.loads((tmp_path/"VAUGHAN_MEETINGS.json").read_text())
    assert persisted["source_access_error"]=="HTTP 403 Forbidden"
    assert persisted["agenda_candidates"]==[]


def test_404_still_errors_for_other_diagnostics():
    import pytest
    def missing(url):
        raise HTTPError(url,404,"Not Found",{},None)
    with pytest.raises(HTTPError) as context:
        discover("Vaughan",fetch=missing)
    assert context.value.code==404


def test_all_other_meetings_remain_unchanged():
    markup='<main><a href="https://www.toronto.ca/meetings/2026-11-05.pdf">Council agenda November 5 2026</a></main>'
    result=discover("Toronto",fetch=lambda url:markup)
    assert result["official_index_status"]=="INDEX_FETCHED_LINK_ONLY"
    assert len(result["agenda_candidates"])==1
