from unittest.mock import MagicMock, patch

import requests

from planning_permission import mayo


def response(text="", payload=None, status_code=200, url="https://example.test"):
    result = MagicMock(status_code=status_code, text=text, url=url)
    result.json.return_value = payload
    return result


def test_parse_live_format_mayo_detail():
    document = """
    <div id="planningApplicationDetails">
      <div id="Details"><table>
        <tr><th>File Number:</th><td>011661</td></tr>
        <tr><th>Application Type:</th><td>PERMISSION</td>
            <th>Planning Status:</th><td>APPLICATION FINALISED</td></tr>
        <tr><th>Received Date:</th><td>17/07/2001</td>
            <th>Decision Due Date:</th><td>16/09/2001</td></tr>
      </table></div>
      <div id="Applicant"><table><tr><th>Applicant name:</th>
        <td>DEIRDRE DURKAN</td></tr></table></div>
      <div id="Development"><table>
        <tr><th>Development Description:</th><td>RETAIN DWELLINGHOUSE</td></tr>
        <tr><th>Development Address:</th><td>BOFAAN, CROSSMOLINA</td></tr>
      </table></div>
      <div id="Decision"><table><tr><th>Decision Date:</th>
        <td>13/09/2001</td></tr></table></div>
    </div>
    """
    record = mayo._parse_mayo_detail(document, "https://example.test/011661")
    assert record["ApplicationNumber"] == "011661"
    assert record["ApplicantName"] == "DEIRDRE DURKAN"
    assert record["DevelopmentAddress"] == "BOFAAN, CROSSMOLINA"
    assert record["DecisionDate"] == "13/09/2001"
    assert record["LinkAppDetails"] == "https://example.test/011661"


def test_parse_mayo_detail_rejects_missing_application():
    assert mayo._parse_mayo_detail("<p>Not found</p>") is None


def test_missing_application_error_page_is_not_retried_or_raised():
    document = """
    <h1>Sorry</h1>
    <p>The ePlan server is experiencing a problem with the page you requested.</p>
    <p>Full technical details of this error has been logged and sent to support staff.</p>
    """
    missing = response(
        document,
        status_code=500,
        url="https://www.eplanning.ie/MayoCC/AppFileRefDetails/does-not-exist/0",
    )
    session = MagicMock()
    session.request.return_value = missing

    actual = mayo._mayo_request(session, "GET", missing.url)

    assert actual is missing
    session.request.assert_called_once()


def test_get_mayo_index_layer_pages_numbers_only():
    session = MagicMock()
    session.request.side_effect = [
        response(
            payload={
                "features": [{"attributes": {"FileNumber": "0015"}}],
                "exceededTransferLimit": True,
            }
        ),
        response(
            payload={
                "features": [
                    {"attributes": {"FileNumber": " 003061 "}},
                    {"attributes": {"FileNumber": "????01"}},
                ],
                "exceededTransferLimit": False,
            }
        ),
    ]
    with patch.object(mayo.requests, "Session", return_value=session):
        numbers = mayo._get_mayo_index_layer(
            "https://example.test/query", "1=1", "FileNumber", batch_size=1
        )
    assert numbers == ["0015", "003061"]
    assert (
        session.request.call_args_list[0].kwargs["params"]["outFields"] == "FileNumber"
    )
    assert session.request.call_args_list[1].kwargs["params"]["resultOffset"] == 1


def test_application_number_index_deduplicates_layers_in_precedence_order():
    with patch.object(
        mayo,
        "_get_mayo_index_layer",
        side_effect=lambda url, where, field: {
            "file_number": ["OLD", "DUP"],
            "FileNumber": ["DUP", "PACE"],
            "ApplicationNumber": ["NEW"],
        }[field],
    ):
        assert mayo.get_all_mayo_application_numbers() == ["OLD", "DUP", "PACE", "NEW"]


def test_individual_pages_use_canonical_urls_and_ten_workers():
    detail = """<div id="planningApplicationDetails"><div id="Details"><table>
      <tr><th>File Number:</th><td>0015</td></tr>
    </table></div></div>"""
    session = MagicMock()
    session.request.return_value = response(detail)
    with patch.object(mayo.requests, "Session", return_value=session):
        records = mayo.get_all_mayo_applications(["0015"])
    assert len(records) == 1
    assert session.request.call_args.args[1] == (
        "https://www.eplanning.ie/MayoCC/AppFileRefDetails/0015/0"
    )
    assert mayo.MAYO_REQUEST_WORKERS == 10


def test_mayo_request_retries_dropped_connections():
    session = MagicMock()
    expected = response("ok")
    session.request.side_effect = [requests.ConnectionError("dropped"), expected]
    with patch.object(mayo.time, "sleep") as sleep:
        actual = mayo._mayo_request(session, "GET", "https://example.test")
    assert actual is expected
    sleep.assert_called_once_with(1)


def test_download_mayo_stores_detail_records():
    record = {
        "_source_layer": "eplanning",
        "ApplicationNumber": "011661",
        "DevelopmentAddress": "BOFAAN",
        "ReceivedDate": "17/07/2001",
    }
    with (
        patch.object(mayo, "get_all_mayo_applications", return_value=[record]),
        patch.object(mayo, "write_to_db") as write_to_db,
    ):
        mayo.download_mayo()
    saved = write_to_db.call_args.args[2][0]
    assert saved.application_number == "011661"
    assert saved.received_date == 995328000000
