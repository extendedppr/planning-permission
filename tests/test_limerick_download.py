from unittest.mock import Mock, patch

from planning_permission import limerick


DETAIL_HTML = """
<div id="planningApplicationDetails">
  <div id="Details"><table>
    <tr><th>File Number</th><td>001</td></tr>
    <tr><th>Planning Status</th><td>Application Finalised</td></tr>
    <tr><th>Received Date</th><td>01/01/2000</td></tr>
  </table></div>
  <div id="Applicant"><table></table></div>
  <div id="Development"><table>
    <tr><th>Development Address</th><td>Glenmore East, Limerick</td></tr>
  </table></div>
  <div id="Decision"><table>
    <tr><th>Decision Type</th><td>CONDITIONAL</td></tr>
    <tr><th>Decision Date</th><td>01/03/2000</td></tr>
  </table></div>
</div>
"""


def test_limerick_details_supply_dates_without_national_register():
    response = Mock(text=DETAIL_HTML)
    response.raise_for_status.return_value = None
    record = {"file_number": "001"}
    with patch.object(limerick, "_mayo_request", return_value=response):
        enriched = limerick.get_limerick_details([record])

    _, details = enriched[0]
    assert details["ReceivedDate"] == "01/01/2000"
    assert details["DecisionDate"] == "01/03/2000"
    assert details["PlanningAuthority"] == "Limerick County Council"
    assert "IrishPlanningApplications" not in limerick.LIMERICK_DETAIL_URL
