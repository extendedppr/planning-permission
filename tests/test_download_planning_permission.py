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
    with pytest.raises(KeyError, match="unknown"):
        download_planning_permission.main(["--county", "unknown"])
