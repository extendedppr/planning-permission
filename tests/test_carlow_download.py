from unittest.mock import Mock, patch

from planning_permission import carlow


DETAIL_HTML = """
<div id="planningApplicationDetails">
  <div id="Details"><table>
    <tr><th>File Number:</th><td>04368</td></tr>
    <tr><th>Planning Status:</th><td>Application Finalised</td></tr>
    <tr><th>Received Date:</th><td>12/03/2004</td></tr>
  </table></div>
  <div id="Applicant"><table></table></div>
  <div id="Development"><table>
    <tr><th>Development Address:</th><td>Coppenagh, Carlow</td></tr>
  </table></div>
  <div id="Decision"><table>
    <tr><th>Decision Type:</th><td>Granted with Conditions</td></tr>
    <tr><th>Decision Date:</th><td>06/05/2004</td></tr>
  </table></div>
</div>
"""


def test_carlow_download_enriches_map_record_with_processing_dates():
    response = Mock(text=DETAIL_HTML)
    response.raise_for_status.return_value = None
    with (
        patch.object(
            carlow,
            "arcgis_download",
            return_value=[{"Planning_R": "04368", "Decision": "Granted"}],
        ),
        patch.object(carlow, "_mayo_request", return_value=response),
    ):
        records = carlow.get_all_carlow_applications()

    assert records[0]["ReceivedDate"] == "12/03/2004"
    assert records[0]["DecisionDate"] == "06/05/2004"
    assert records[0]["PlanningAuthority"] == "Carlow County Council"
