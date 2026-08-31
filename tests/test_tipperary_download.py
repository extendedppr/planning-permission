from unittest.mock import Mock, patch

from planning_permission import tipperary


DETAIL_HTML = """
<div id="planningApplicationDetails">
  <div id="Details"><table>
    <tr><th>File Number</th><td>001302</td></tr>
    <tr><th>Received Date</th><td>01/07/2001</td></tr>
  </table></div>
  <div id="Applicant"><table></table></div>
  <div id="Development"><table></table></div>
  <div id="Decision"><table>
    <tr><th>Decision Type</th><td>Granted</td></tr>
    <tr><th>Decision Date</th><td>21/08/2001</td></tr>
  </table></div>
</div>
"""


def test_tipperary_details_supply_received_date_without_national_register():
    response = Mock(text=DETAIL_HTML)
    response.raise_for_status.return_value = None
    record = {"FileNumber": "001302", "decision_date": 998352000000}
    with patch.object(tipperary, "_mayo_request", return_value=response):
        enriched = tipperary.get_tipperary_details([record])

    source, details = enriched[0]
    assert source["decision_date"] == 998352000000
    assert details["ReceivedDate"] == "01/07/2001"
    assert details["PlanningAuthority"] == "Tipperary County Council"
    assert "IrishPlanningApplications" not in tipperary.TIPPERARY_DETAIL_URL
