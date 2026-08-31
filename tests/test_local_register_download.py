from unittest.mock import patch

from planning_permission import kilkenny
from planning_permission import laois, roscommon
from planning_permission.local_register import _merge_objects


def test_local_register_county_download_persists_records():
    record = {
        "OBJECTID": 42,
        "ApplicationNumber": "24/123",
        "DevelopmentAddress": "1 Main Street, Kilkenny",
        "PlanningAuthority": "Kilkenny County Council",
        "DevelopmentDescription": "An extension",
        "ReceivedDate": 1711929600000,
    }
    with (
        patch(
            "planning_permission.local_register.arcgis_download", return_value=[record]
        ) as download,
        patch("planning_permission.local_register.write_to_db") as write,
    ):
        kilkenny.download_kilkenny()

    assert download.call_args.args[0] == kilkenny.KILKENNY_URL
    assert download.call_args.kwargs["skip_sort"] is True
    db, model, objects = write.call_args.args
    assert db is kilkenny.kilkenny_db
    assert model is kilkenny.KilkennyObject
    assert objects[0].application_number == "24/123"
    assert objects[0].searchable_address == "1mainstkilkenny"


def test_laois_uses_the_live_council_viewer_layer():
    urls = [url for _, url in laois.LAOIS_URLS]
    assert any("Planning_Sites_Laois" in url for url in urls)
    assert not any("Applicaion_Points_2021" in url for url in urls)
    assert not any("IrishPlanningApplications" in url for url in urls)


def test_roscommon_combines_current_and_historical_council_layers():
    labels = [label for label, _ in roscommon.ROSCOMMON_URLS]
    assert labels == ["historical", "current"]
    assert all("Planning_Finder_App" in url for _, url in roscommon.ROSCOMMON_URLS)


def test_sparse_overlapping_layer_does_not_erase_decision():
    detailed = laois.LaoisObject.parse(
        {"OBJECTID": 1, "Applicatio": "98769", "Decision": "Granted"},
        "Laois County Council",
    )
    sparse = laois.LaoisObject.parse(
        {"OBJECTID": 2, "FileNumber": "98769", "ReceivedDate": 123},
        "Laois County Council",
    )

    merged = _merge_objects(detailed, sparse)

    assert merged.decision == "Granted"
    assert merged.received_date == 123
