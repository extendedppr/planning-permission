from unittest.mock import MagicMock, patch

from planning_permission import galway


def response(payload):
    result = MagicMock()
    result.json.return_value = payload
    return result


def test_get_all_galway_applications_counts_and_paginates_stably():
    session = MagicMock()
    session.get.side_effect = [
        response({"count": 3}),
        response(
            {
                "features": [
                    {"attributes": {"OBJECTID": 1}},
                    {"attributes": {"OBJECTID": 2}},
                ],
                "exceededTransferLimit": True,
            }
        ),
        response(
            {
                "features": [{"attributes": {"OBJECTID": 3}}],
                "exceededTransferLimit": False,
            }
        ),
    ]

    with patch.object(galway.progressbar, "ProgressBar"):
        records = galway.get_all_galway_applications(
            session,
            batch_size=2,
            layers=((galway.GALWAY_URL, "ApplicationNumber", "Galway: "),),
        )

    assert [record["OBJECTID"] for record in records] == [1, 2, 3]
    first_page_params = session.get.call_args_list[1].kwargs["params"]
    second_page_params = session.get.call_args_list[2].kwargs["params"]
    assert first_page_params["orderByFields"] == "OBJECTID ASC"
    assert first_page_params["resultOffset"] == 0
    assert second_page_params["resultOffset"] == 2


def test_download_galway_writes_only_after_all_records_are_parsed():
    records = [
        {
            "OBJECTID": 1,
            "Location": "Main Street, Galway",
            "ApplicationNumber": "123",
        }
    ]
    with (
        patch.object(galway, "get_all_galway_applications", return_value=records),
        patch.object(galway, "write_to_db") as write_to_db,
    ):
        galway.download_galway()

    db, model, objects = write_to_db.call_args.args
    assert db is galway.galway_db
    assert model is galway.GalwayObject
    assert len(objects) == 1
    assert objects[0].application_number == "123"


def test_get_all_galway_applications_combines_archives_and_prefers_newer_record():
    historical = [{"OBJECTID": 1, "Planning_Ref": "95/123"}]
    older = [
        {
            "OBJECTID": 2,
            "ApplicationNumber": "95123",
            "Description": "Detailed record",
        },
        {"OBJECTID": 3, "ApplicationNumber": "96/456"},
    ]
    modern = [{"OBJECTID": 4, "ApplicationNumber": "16/789"}]
    with patch.object(
        galway, "_get_galway_layer", side_effect=[historical, older, modern]
    ):
        records = galway.get_all_galway_applications(session=MagicMock())

    assert len(records) == 3
    by_object_id = {record["OBJECTID"]: record for record in records}
    assert 1 not in by_object_id
    assert by_object_id[2]["Description"] == "Detailed record"


def test_parse_galway_application_tolerates_missing_optional_fields():
    result = galway.parse_galway_application({"OBJECTID": 1})

    assert result.objid == 1
    assert result.address == ""
    assert result.application_number is None
