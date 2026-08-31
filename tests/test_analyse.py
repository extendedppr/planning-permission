import sqlite3

from scripts import analyse


def test_database_paths_includes_new_local_register_counties(tmp_path):
    for county in ("laois", "roscommon", "leitrim"):
        county_dir = tmp_path / county
        county_dir.mkdir()
        (county_dir / "db.sqlite").write_bytes(b"sqlite")

    assert list(analyse.database_paths(tmp_path)) == [
        ("laois", tmp_path / "laois" / "db.sqlite"),
        ("roscommon", tmp_path / "roscommon" / "db.sqlite"),
        ("leitrim", tmp_path / "leitrim" / "db.sqlite"),
    ]


def test_analyse_database_reads_shared_local_register_schema(tmp_path):
    path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE planning_applications (
            application_number TEXT, received_date TEXT, decision_date TEXT,
            decision TEXT, application_status TEXT, application_type TEXT,
            description TEXT, address TEXT
        )"""
    )
    connection.execute(
        "INSERT INTO planning_applications VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "24123",
            "01/02/2024",
            "15/04/2024",
            "Granted (Conditional)",
            "Application Finalised",
            "PERMISSION",
            "An extension",
            "Main Street",
        ),
    )
    connection.commit()
    connection.close()

    rows, metric = analyse.analyse_database("roscommon", path)

    assert len(rows) == 1
    assert rows[0]["outcome"] == "Granted"
    assert metric["records"] == 1
    assert metric["dated_pct"] == 100
