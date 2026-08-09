import argparse

from tabulate import tabulate

from planning_permission.planning_permission_db import planning_permission_db
from planning_permission.cork import cork_db
from planning_permission.dcc import dcc_db
from planning_permission.galway import galway_db
from planning_permission.kildare import kildare_db
from planning_permission.utils import clean_address_for_comparison


DEFAULT_FIELDS = {
    "general": (
        ("application_number", "application_number"),
        ("status", "application_status"),
        ("type", "application_type"),
        ("decision", "decision"),
        ("received", "received_date"),
        ("decision_date", "decision_date"),
        ("description", "development_description"),
    ),
    "dublin": (
        ("application_number", "objid"),
        ("status", "status_description"),
        ("type", "application_type"),
        ("decision", "decision_text"),
        ("received", "received_date"),
        ("decision_date", "decision_date"),
        ("description", "proposal"),
    ),
    "cork": (
        ("application_number", "application_number"),
        ("status", "application_status"),
        ("type", "application_type"),
        ("decision", "decision"),
        ("received", "received_date"),
        ("decision_date", "decision_date"),
        ("description", "description"),
    ),
    "galway": (
        ("application_number", "application_number"),
        ("status", "application_status"),
        ("type", "application_type"),
        ("decision", "decision"),
        ("received", "received_date"),
        ("decision_date", "decision_date"),
        ("description", "description"),
    ),
    "kildare": (
        ("application_number", "application_number"),
        ("status", "application_status"),
        ("type", "application_type"),
        ("decision", "decision"),
        ("received", "received_date"),
        ("decision_date", "decision_date"),
        ("description", "description"),
    ),
}

MAX_FIELD_LENGTH = 50


def address_substr_csv(value: str):
    return (
        [clean_address_for_comparison(addr).lower() for addr in value.split(",")]
        if value
        else []
    )


def format_value(value, truncate=True):
    if value is None:
        return ""
    value = str(value)
    if truncate and len(value) > MAX_FIELD_LENGTH:
        return f"{value[:MAX_FIELD_LENGTH]}..."
    return value


def build_default_row(source, result, address_field, truncate=True):
    row = {
        "source": source,
        "address": format_value(getattr(result, address_field), truncate=truncate),
    }
    for output_field, model_field in DEFAULT_FIELDS[source]:
        row[output_field] = format_value(
            getattr(result, model_field, None),
            truncate=truncate,
        )
    return row


def build_all_row(source, result, truncate=True):
    row = {"source": source}
    for field in result._meta.sorted_fields:
        row[field.name] = format_value(
            getattr(result, field.name),
            truncate=truncate,
        )
    return row


def search_db(
    source,
    db,
    address_field,
    address_substrs,
    exclude_address_substrs,
    include_all_features=False,
    truncate=True,
):
    rows = []
    for result in db.filter(
        address_substrs=address_substrs,
        exclude_address_substrs=exclude_address_substrs,
        partial=True,
    ):
        if include_all_features:
            rows.append(build_all_row(source, result, truncate=truncate))
        else:
            rows.append(
                build_default_row(
                    source,
                    result,
                    address_field,
                    truncate=truncate,
                )
            )
    return rows


def get_headers(rows):
    headers = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def align_rows(rows, headers):
    return [[row.get(header, "") for header in headers] for row in rows]


def main():
    parser = argparse.ArgumentParser(description="Get all stats around a point")
    parser.add_argument(
        "--address-substr-csv",
        dest="address_substr_csv",
        type=address_substr_csv,
        help="CSV values of address substrings that must be within the found address (e.g. '13,dublin,grand canal')",
        default=[],
    )
    parser.add_argument(
        "--exclude-address-substr-csv",
        dest="exclude_address_substr_csv",
        type=address_substr_csv,
        help="CSV values of address substrings that must not be within the found address (e.g. '13,dublin,grand canal')",
        default=[],
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Do not truncate field values",
    )
    parser.add_argument(
        "--all-features",
        action="store_true",
        help="Show every field returned by each matching planning source",
    )

    args = parser.parse_args()

    results_dict = []
    for source, db, address_field in (
        ("general", planning_permission_db, "development_address"),
        ("dublin", dcc_db, "address"),
        ("cork", cork_db, "address"),
        ("galway", galway_db, "address"),
        ("kildare", kildare_db, "address"),
    ):
        results_dict.extend(
            search_db(
                source,
                db,
                address_field,
                args.address_substr_csv,
                args.exclude_address_substr_csv,
                include_all_features=args.all_features,
                truncate=not args.all,
            )
        )

    headers = get_headers(results_dict)
    print(
        tabulate(
            align_rows(results_dict, headers),
            headers=headers,
            tablefmt="fancy_grid",
        )
    )


if __name__ == "__main__":
    main()
