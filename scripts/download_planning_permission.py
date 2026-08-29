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
from planning_permission.kilkenny import download_kilkenny
from planning_permission.westmeath import download_westmeath
from planning_permission.laois import download_laois
from planning_permission.offaly import download_offaly
from planning_permission.cavan import download_cavan
from planning_permission.roscommon import download_roscommon
from planning_permission.sligo import download_sligo
from planning_permission.monaghan import download_monaghan
from planning_permission.carlow import download_carlow
from planning_permission.longford import download_longford
from planning_permission.leitrim import download_leitrim

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
    "kilkenny": download_kilkenny,
    "westmeath": download_westmeath,
    "laois": download_laois,
    "offaly": download_offaly,
    "cavan": download_cavan,
    "roscommon": download_roscommon,
    "sligo": download_sligo,
    "monaghan": download_monaghan,
    "carlow": download_carlow,
    "longford": download_longford,
    "leitrim": download_leitrim,
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
