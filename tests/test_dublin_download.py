from datetime import date
from unittest.mock import MagicMock, patch

import requests

from planning_permission import dublin


def test_dublin_request_retries_transient_failures():
    session = MagicMock()
    expected = MagicMock(status_code=200)
    session.get.side_effect = [requests.ConnectionError("dropped"), expected]

    with (
        patch.object(dublin, "_pace_dublin_requests"),
        patch.object(dublin.time, "sleep") as sleep,
    ):
        actual = dublin._dublin_request(session, "https://example.test")

    assert actual is expected
    sleep.assert_called_once_with(1)


def test_default_dublin_download_searches_concurrently_and_sorts_results():
    def result(_session, location, _searched, **_kwargs):
        return [{"id": {"aa": 2, "bb": 1}[location], "location": location}]

    progress = MagicMock()
    with (
        patch.object(dublin, "_get_dublin_search_results", side_effect=result),
        patch.object(dublin.requests, "Session", return_value=MagicMock()),
        patch.object(dublin.progressbar, "ProgressBar", return_value=progress),
    ):
        records = dublin.get_all_dublin_applications(search_terms=["aa", "bb"])

    assert [record["id"] for record in records] == [1, 2]
    assert progress.update.call_count == 2
    progress.finish.assert_called_once_with()
    assert dublin.DUBLIN_REQUEST_WORKERS == 10


def test_dublin_default_download_uses_monthly_date_ranges():
    session = MagicMock()
    session.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "total": 1,
            "results": [{"id": 7, "reference": "1000/25"}],
        },
    )
    with (
        patch.object(
            dublin,
            "_dublin_month_ranges",
            return_value=[(date(2025, 1, 1), date(2025, 1, 31))],
        ),
    ):
        records = dublin.get_all_dublin_applications(session=session)

    assert records == [{"id": 7, "reference": "1000/25"}]
    assert session.get.call_args.kwargs["params"] == {
        "registrationDateFrom": "2025-01-01",
        "registrationDateTo": "2025-01-31",
        "openApplications": "false",
    }


def test_dublin_date_search_splits_overlarge_ranges():
    session = MagicMock()
    too_many = MagicMock(status_code=400)
    too_many.json.return_value = [{"message": "Too many records have been found"}]
    first = MagicMock(status_code=200)
    first.json.return_value = {"results": [{"id": 1}]}
    second = MagicMock(status_code=200)
    second.json.return_value = {"results": [{"id": 2}]}
    session.get.side_effect = [too_many, first, second]

    with patch.object(dublin.time, "sleep"):
        records = dublin._get_dublin_date_results(
            session, date(2025, 1, 1), date(2025, 1, 2)
        )

    assert records == [{"id": 1}, {"id": 2}]


def test_dublin_request_pacing_is_global():
    with (
        patch.object(dublin.time, "monotonic", side_effect=[100.0, 100.25]),
        patch.object(dublin.time, "sleep") as sleep,
    ):
        dublin._DUBLIN_NEXT_REQUEST_AT = 0.0
        dublin._pace_dublin_requests()
        dublin._pace_dublin_requests()

    sleep.assert_called_once_with(0.75)
