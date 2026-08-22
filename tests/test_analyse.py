import sqlite3

from scripts.analyse import (
    analyse_database,
    application_type_counts,
    normalise_application_type,
    outcome,
    parse_application_date,
    parse_date,
    print_terminal_report,
    render_dashboard,
)


def test_parse_date_supports_common_formats_and_epoch_milliseconds():
    assert parse_date("15/03/2024").date().isoformat() == "2024-03-15"
    assert parse_date(1710460800000).date().isoformat() == "2024-03-15"
    assert parse_date(None) is None
    assert parse_date("20031119000000").date().isoformat() == "2003-11-19"
    assert parse_date(20251119).date().isoformat() == "2025-11-19"
    assert parse_application_date(4102444800000) is None


def test_outcome_prioritises_refusal_over_permission_word():
    assert outcome("REFUSE PERMISSION", None) == "Refused"
    assert outcome("GRANT", None) == "Granted"
    assert outcome(None, "Withdrawn") == "Withdrawn/invalid"
    assert outcome("CONDITIONAL", None) == "Granted"
    assert outcome("UNCONDITIONAL", None) == "Granted"
    assert outcome("Application withdrawn", "Permission") == "Withdrawn/invalid"


def test_application_types_are_grouped_case_insensitively():
    rows = [
        {"type": "PERMISSION"},
        {"type": "Permission"},
        {"type": "  permission  "},
        {"type": "Outline Permission"},
    ]

    assert normalise_application_type(" Permission ") == "PERMISSION"
    assert application_type_counts(rows) == {
        "PERMISSION": 3,
        "OUTLINE PERMISSION": 1,
    }


def test_analyse_database_uses_council_specific_decision_fallbacks(tmp_path):
    path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE applications (application_number TEXT, decision TEXT, "
        "decision_code TEXT, application_status TEXT, status TEXT)"
    )
    connection.executemany(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?)",
        [
            ("A1", None, "CONDITIONAL", None, "Decision made"),
            ("A2", "", "REFUSED", "", "Decision made"),
        ],
    )
    connection.commit()
    connection.close()

    _, metric = analyse_database("wicklow", path)

    assert metric["granted"] == 1
    assert metric["refused"] == 1
    assert metric["grant_rate"] == 50


def test_analyse_database_prefers_wicklow_outcome_status(tmp_path):
    path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE applications (application_number TEXT, decision TEXT, "
        "decision_code TEXT, application_status TEXT, status TEXT)"
    )
    connection.executemany(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?)",
        [
            ("A1", None, "C", "Application Finalised", "Grant"),
            ("A2", None, "R", "Application Finalised", "Refused"),
        ],
    )
    connection.commit()
    connection.close()

    _, metric = analyse_database("wicklow", path)

    assert metric["granted"] == 1
    assert metric["refused"] == 1
    assert metric["grant_rate"] == 50


def test_analyse_database_uses_dublin_registration_date(tmp_path):
    path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE applications (application_reference TEXT, "
        "registration_date TEXT, decision_date TEXT, decision_text TEXT)"
    )
    connection.execute(
        "INSERT INTO applications VALUES (?, ?, ?, ?)",
        ("1000/25", "2025-01-01", "2025-02-20", "GRANT PERMISSION"),
    )
    connection.commit()
    connection.close()

    _, metric = analyse_database("dublin", path)

    assert metric["dated_pct"] == 100
    assert metric["median_days"] == 50
    assert metric["granted"] == 1


def test_analyse_database_and_dashboard(tmp_path):
    path = tmp_path / "db.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE applications (application_number TEXT, received_date TEXT, decision_date TEXT, decision TEXT, application_type TEXT, description TEXT)"
    )
    connection.executemany(
        "INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "A1",
                "01/01/2024",
                "31/01/2024",
                "Grant Permission",
                "Retention",
                "house",
            ),
            ("A2", "01/02/2024", "12/03/2024", "Refuse Permission", "New", "shop"),
        ],
    )
    connection.commit()
    connection.close()
    rows, metric = analyse_database("galway", path)
    assert metric["records"] == 2
    assert metric["grant_rate"] == 50
    assert metric["median_days"] == 35
    assert rows[0]["received_raw"] == "01/01/2024"
    dashboard = render_dashboard(rows, [metric], [], None)
    assert "Planning Observatory" in dashboard
    assert "Galway" in dashboard
    assert "Received dates" in dashboard
    assert "not the share of council records downloaded" in dashboard


def test_terminal_report_prints_findings(capsys):
    rows = [
        {
            "county": "galway",
            "received": parse_date("01/01/2024"),
            "decided": parse_date("31/01/2024"),
            "outcome": "Granted",
            "type": "Retention",
            "reference": "A1",
            "address": "Main Street",
            "description": "A house",
            "decision": "Grant",
            "status": None,
        }
    ]
    metrics = [
        {
            "county": "galway",
            "records": 1,
            "decided": 1,
            "granted": 1,
            "refused": 0,
            "grant_rate": 100.0,
            "median_days": 30,
            "dated_pct": 100.0,
            "described_pct": 100.0,
        }
    ]
    print_terminal_report(rows, metrics, ["mayo"])
    output = capsys.readouterr().out
    assert "QUICK FINDINGS" in output
    assert "Recorded grant rate: 100.0%" in output
    assert "RETENTION: 1" in output
    assert "Databases not found: Mayo" in output
    assert "Duplicate references within a county" in output
    assert "Timeline anomalies" in output
    assert "County completeness outliers" in output
