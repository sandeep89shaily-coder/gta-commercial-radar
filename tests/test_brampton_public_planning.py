from datetime import date
from unittest import TestCase
from unittest.mock import patch

from bs4 import BeautifulSoup

import gta_brampton_public_planning as portal


class BramptonPublicPlanningTests(TestCase):
    def test_search_uses_bounded_dates_and_follows_published_pagination(self):
        form = """
        <form action="./CapHome.aspx?TabName=Planning&amp;module=Planning">
        <input type="hidden" name="__VIEWSTATE" value="test" />
        <input type="text" name="ctl00$PlaceHolderMain$generalSearchForm$txtGSStartDate" />
        <input type="text" name="ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate" />
        </form>"""

        def grid(file_id, next_page=""):
            return f"""
            <table id="{portal.GRID}">
            <tr><th>Date</th><th>File Number</th><th>File Type</th><th>Address</th><th>Status</th></tr>
            <tr><td>11/23/2026</td><td><a href="{portal.DETAIL_PATH}?agencyCode=BRAMPTON">{file_id}</a></td>
            <td>Site Plan</td><td>1 Test Road</td><td>Submitted</td></tr>
            </table>""".replace("</table>", next_page + "</table>")

        next_page = (
            "<a href=\"javascript:__doPostBack('ctl00$PlaceHolderMain$dgvPermitList"
            "$gdvPermitList$ctl13$ctl03','')\">2</a>"
        )
        pages = [form, form + grid("26TMP-123", next_page), form + grid("SPA-2026-0001")]
        with patch.object(portal, "evaluate", return_value=(True, "ALLOWED")), patch.object(
            portal, "_page", side_effect=[BeautifulSoup(page, "html.parser") for page in pages]
        ) as fetch:
            rows, status = portal.collect(today=date(2026, 11, 26))

        assert status == {"pages_fetched": 2, "pagination_complete": True}
        assert [row["application_id"] for row in rows] == ["SPA-2026-0001"]
        assert rows[0]["source_date"] == "2026-11-23"
        assert rows[0]["first_publication_verified"] == "False"
        assert rows[0]["licence_status"] == portal.LICENCE
        assert fetch.call_args_list[1].args[2][
            portal.FORM_PREFIX + "generalSearchForm$txtGSStartDate"
        ] == "11/13/2026"
        assert fetch.call_args_list[2].args[2]["__EVENTTARGET"].endswith("$ctl13$ctl03")
