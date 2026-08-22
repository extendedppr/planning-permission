import argparse

from planning_permission.clare import download_clare
from planning_permission.cork import download_cork
from planning_permission.dublin import download_dublin
from planning_permission.donegal import download_donegal
from planning_permission.galway import download_galway
from planning_permission.kerry import download_kerry
from planning_permission.kildare import download_kildare
from planning_permission.limerick import download_limerick
from planning_permission.louth import download_louth
from planning_permission.mayo import download_mayo
from planning_permission.meath import download_meath
from planning_permission.tipperary import download_tipperary
from planning_permission.waterford import download_waterford
from planning_permission.wexford import download_wexford
from planning_permission.wicklow import download_wicklow

COUNTY_FUNC_MAP = {
    "dublin": download_dublin,
    "cork": download_cork,
    "galway": download_galway,
    "kildare": download_kildare,
    "meath": download_meath,
    "limerick": download_limerick,
    "tipperary": download_tipperary,
    "donegal": download_donegal,
    "wexford": download_wexford,
    "kerry": download_kerry,
    "wicklow": download_wicklow,
    "louth": download_louth,
    "mayo": download_mayo,
    "clare": download_clare,
    "waterford": download_waterford,
}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download planning permissions county by county"
    )
    parser.add_argument("--county", type=str)

    args = parser.parse_args(argv)

    if args.county:
        COUNTY_FUNC_MAP[args.county.lower()]()
    else:
        for download_func in COUNTY_FUNC_MAP.values():
            download_func()


if __name__ == "__main__":
    main()
