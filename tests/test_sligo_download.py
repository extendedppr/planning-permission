from unittest.mock import Mock, patch

from planning_permission import sligo


DETAIL_HTML = """
<div id="planningApplicationDetails">
  <div id="Details"><table>
    <tr><th>File Number:</th><td>011045</td></tr>
    <tr><th>Planning Status:</th><td>Application Finalised</td></tr>
    <tr><th>Received Date:</th><td>01/03/2001</td></tr>
  </table></div>
  <div id="Applicant"><table></table></div>
  <div id="Development"><table>
    <tr><th>Development Address:</th><td>Castletown, Sligo</td></tr>
  </table></div>
  <div id="Decision"><table>
    <tr><th>Decision Type:</th><td>Granted with Conditions</td></tr>
    <tr><th>Decision Date:</th><td>10/05/2001</td></tr>
  </table></div>
</div>
"""


def test_sligo_download_enriches_map_record_with_processing_dates():
    response = Mock(text=DETAIL_HTML)
    response.raise_for_status.return_value = None
    with (
        patch.object(
            sligo,
            "arcgis_download",
            return_value=[{"ApplicationNumber": "011045"}],
        ),
        patch.object(sligo, "_mayo_request", return_value=response),
    ):
        records = sligo.get_all_sligo_applications()

    assert records[0]["ReceivedDate"] == "01/03/2001"
    assert records[0]["DecisionDate"] == "10/05/2001"
    assert records[0]["Decision"] == "Granted with Conditions"
