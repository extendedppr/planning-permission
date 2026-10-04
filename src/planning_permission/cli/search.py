import argparse
import json
import csv
import sys
from datetime import date

from tabulate import tabulate

from planning_permission.utils import (
    PLANNING_COUNTIES,
    clean_address_for_comparison,
    search,
)


def address_substr_csv(value: str):
    return (
        [clean_address_for_comparison(addr).lower() for addr in value.split(",")]
        if value
        else []
    )


def get_headers(rows):
    headers = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def align_rows(rows, headers):
    return [[row.get(header, "") for header in headers] for row in rows]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Search downloaded Irish planning applications"
    )
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
        "--county",
        action="append",
        type=str.casefold,
        choices=PLANNING_COUNTIES,
        help="Only search this county (may be supplied more than once)",
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
    parser.add_argument(
        "--output",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format",
    )

    parser.add_argument(
        "--reference", help="Exact application reference (case insensitive)"
    )
    parser.add_argument(
        "--received-from",
        type=date.fromisoformat,
        help="Inclusive received date, YYYY-MM-DD",
    )
    parser.add_argument(
        "--received-to",
        type=date.fromisoformat,
        help="Inclusive received date, YYYY-MM-DD",
    )
    parser.add_argument(
        "--decision", help="Decision text contains this value (case insensitive)"
    )
    parser.add_argument(
        "--status", help="Status text contains this value (case insensitive)"
    )
    args = parser.parse_args(argv)
    if (
        args.received_from
        and args.received_to
        and args.received_from > args.received_to
    ):
        parser.error("--received-from must not be after --received-to")

    results_dict = search(
        args.address_substr_csv,
        args.exclude_address_substr_csv,
        counties=args.county,
        reference=args.reference,
        received_from=args.received_from.isoformat() if args.received_from else None,
        received_to=args.received_to.isoformat() if args.received_to else None,
        decision=args.decision,
        status=args.status,
        include_all_features=args.all_features,
        truncate=not args.all and args.output == "table",
    )

    if args.output == "json":
        print(json.dumps(results_dict, indent=2))
    elif args.output == "csv":
        headers = get_headers(results_dict)
        if headers:
            writer = csv.DictWriter(sys.stdout, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results_dict)
    else:
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
