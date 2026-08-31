from unittest.mock import Mock, patch

from planning_permission import leitrim


DETAIL_HTML = """
<div id="planningApplicationDetails">
  <div id="Details"><table>
    <tr><th>File Number:</th><td>22100</td></tr>
    <tr><th>Application Type:</th><td>PERMISSION</td></tr>
    <tr><th>Planning Status:</th><td>Application Finalised</td></tr>
    <tr><th>Received Date:</th><td>01/02/2022</td></tr>
  </table></div>
  <div id="Applicant"><table>
    <tr><th>Applicant name:</th><td>Example Applicant</td></tr>
  </table></div>
  <div id="Development"><table>
    <tr><th>Development Address:</th><td>Main Street, Leitrim</td></tr>
    <tr><th>Development Description:</th><td>An extension</td></tr>
  </table></div>
  <div id="Decision"><table>
    <tr><th>Decision Type:</th><td>Granted with Conditions</td></tr>
    <tr><th>Decision Date:</th><td>15/04/2022</td></tr>
  </table></div>
</div>
"""


def test_compact_reference_handles_both_leitrim_layer_formats():
    assert leitrim._compact_reference({"file_year": "22", "file_num": "100"}) == "22100"
    assert leitrim._compact_reference({"FILENUMB_1": "23/456"}) == "23456"


def test_leitrim_download_enriches_map_record_with_eplanning_decision():
    response = Mock(text=DETAIL_HTML)
    response.raise_for_status.return_value = None
    with (
        patch.object(
            leitrim,
            "arcgis_download",
            side_effect=[[{"file_year": "22", "file_num": "100"}], []],
        ),
        patch.object(leitrim, "_mayo_request", return_value=response),
    ):
        records = leitrim.get_all_leitrim_applications()

    assert records[0]["Decision"] == "Granted with Conditions"
    assert records[0]["DecisionDate"] == "15/04/2022"
    assert records[0]["PlanningAuthority"] == "Leitrim County Council"
