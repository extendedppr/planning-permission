import argparse
import json

from tabulate import tabulate

from planning_permission.utils import clean_address_for_comparison, search


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
    parser.add_argument(
        "--output",
        choices=("table", "json"),
        default="table",
        help="Output format",
    )

    args = parser.parse_args(argv)

    results_dict = search(
        args.address_substr_csv,
        args.exclude_address_substr_csv,
        include_all_features=args.all_features,
        truncate=not args.all and args.output == "table",
    )

    if args.output == "json":
        print(json.dumps(results_dict, indent=2))
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
