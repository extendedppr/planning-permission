"""Common field names and date parsing; original adapter fields remain unchanged."""

from datetime import datetime, timezone

FIELD_ALIASES = {
    "reference": ("application_number", "application_reference"),
    "received": ("received_date", "registration_date", "application_date"),
    "decided": ("decision_date",),
    "decision": (
        "decision",
        "decision_text",
        "decision_code",
        "decision_description",
    ),
    # Some authorities (notably Wicklow) keep the actual Grant/Refused value in
    # `status`, while `application_status` only says "Application Finalised".
    "status": ("status", "application_status", "status_description"),
    "type": ("application_type",),
    "description": ("description", "development_description", "proposal"),
    "address": ("address",),
}
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y%m%d",
    "%Y%m%d%H%M",
    "%Y%m%d%H%M%S",
)


def parse_date(value):
    if value in (None, ""):
        return None
    text = str(value).strip()
    # Several council exports use compact calendar timestamps. They must be
    # parsed before the numeric Unix timestamp handling below.
    compact_formats = {8: "%Y%m%d", 12: "%Y%m%d%H%M", 14: "%Y%m%d%H%M%S"}
    if text.isdigit() and len(text) in compact_formats:
        try:
            return datetime.strptime(text, compact_formats[len(text)])
        except ValueError:
            return None
    if isinstance(value, (int, float)) or str(value).strip().lstrip("-").isdigit():
        number = float(value)
        if abs(number) > 10_000_000_000:
            number /= 1000
        if abs(number) > 100_000_000:
            try:
                return datetime.fromtimestamp(number, tz=timezone.utc).replace(
                    tzinfo=None
                )
            except (ValueError, OSError, OverflowError):
                return None
    text = text.replace("Z", "").split(".")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


COMMON_FIELDS = {
    "application_number": FIELD_ALIASES["reference"],
    "address": FIELD_ALIASES["address"],
    "status": ("application_status", "status_description", "status"),
    "type": FIELD_ALIASES["type"],
    "decision": FIELD_ALIASES["decision"],
    "received": FIELD_ALIASES["received"],
    "decision_date": FIELD_ALIASES["decided"],
    "description": FIELD_ALIASES["description"],
    "latitude": ("lat", "latitude"),
    "longitude": ("lng", "longitude"),
    "source_url": ("details_url", "link_app_details", "more_info"),
}


def normalise_record(record):
    def first(names):
        for name in names:
            value = (
                record.get(name)
                if isinstance(record, dict)
                else getattr(record, name, None)
            )
            if value not in (None, ""):
                return value
        return None

    row = {key: first(names) for key, names in COMMON_FIELDS.items()}
    for field in ("received", "decision_date"):
        parsed = parse_date(row[field])
        row[field] = parsed.date().isoformat() if parsed else None
    if row["latitude"] is None or row["longitude"] is None:
        east, north = first(("itm_easting",)), first(("itm_northing",))
        if east is not None and north is not None:
            from planning_permission.utils import itm_to_lat_lng

            row["latitude"], row["longitude"] = itm_to_lat_lng(east, north)
    return row
