"""Refresh counties independently."""

import argparse
import sys

from planning_permission.registry import REGISTRY

COUNTY_FUNC_MAP = {name: entry.download for name, entry in REGISTRY.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download planning permissions county by county"
    )
    parser.add_argument(
        "--county",
        type=str.casefold,
        choices=COUNTY_FUNC_MAP,
        action="append",
        help="Refresh only this county; may be repeated",
    )
    args = parser.parse_args(argv)
    failed = False
    for county in dict.fromkeys(args.county or COUNTY_FUNC_MAP):
        try:
            COUNTY_FUNC_MAP[county]()
        except Exception as error:
            failed = True
            print(f"{county}: {type(error).__name__}: {error}", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
