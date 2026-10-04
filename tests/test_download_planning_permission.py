from unittest.mock import Mock, patch

import pytest

from scripts import download_planning_permission


def test_downloads_selected_county_case_insensitively():
    download = Mock()
    with patch.dict(
        download_planning_permission.COUNTY_FUNC_MAP,
        {"dublin": download},
        clear=True,
    ):
        download_planning_permission.main(["--county", "DuBlIn"])

    download.assert_called_once_with()


def test_downloads_every_county_in_order():
    calls = []
    downloads = {
        county: lambda county=county: calls.append(county)
        for county in ("dublin", "cork", "galway")
    }
    with patch.dict(
        download_planning_permission.COUNTY_FUNC_MAP, downloads, clear=True
    ):
        download_planning_permission.main([])

    assert calls == ["dublin", "cork", "galway"]


def test_unknown_county_is_rejected():
    with pytest.raises(SystemExit, match="2"):
        download_planning_permission.main(["--county", "unknown"])


def test_failure_continues_other_counties(capsys):
    failed = Mock(side_effect=RuntimeError("source unavailable"))
    good = Mock(return_value={"records_fetched": 3, "records_saved": 3})
    with patch.dict(
        download_planning_permission.COUNTY_FUNC_MAP,
        {"dublin": failed, "cork": good},
        clear=True,
    ):
        result = download_planning_permission.main([])
    assert result == 1
    good.assert_called_once()
    output = capsys.readouterr()
    assert output.out == ""
    assert "dublin: RuntimeError: source unavailable" in output.err
