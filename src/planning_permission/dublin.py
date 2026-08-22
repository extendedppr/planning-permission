import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Iterable, List

import progressbar
import requests
from peewee import (
    Model,
    TextField,
    IntegerField,
    DateField,
    CharField,
    FloatField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import DUBLIN_DB_LOCATION, SLEEP_BETWEEN_REQUESTS
from planning_permission.utils import (
    clean_address_for_comparison,
    itm_to_lat_lng,
    write_to_db,
)

DUBLIN_FIELD_MAP = {
    "id": "objid",
    "reference": "application_reference",
    "location": "address",
    "proposal": "proposal",
    "applicantSurname": "applicant_surname",
    "applicantPropKey": "applicant_prop_key",
    "registrationDate": "registration_date",
    "decisionDate": "decision_date",
    "decisionText": "decision_text",
    "finalGrantDate": "final_grant_date",
    "extensionDate": "extension_date",
    "appealLodgedDate": "appeal_lodged_date",
    "appealDecisionDate": "appeal_decision_date",
    "appealNotifyDate": "appeal_notify_date",
    "abpReference": "abp_reference",
    "appealDecision": "appeal_decision",
    "postcode": "postcode",
    "fullProposal": "full_proposal",
    "registerDate": "register_date",
    "dispatchDate": "dispatch_date",
    "statusDescription": "status_description",
    "statusOwner": "status_owner",
    "statusNonOwner": "status_non_owner",
    "applicationTypeId": "application_type_id",
    "applicationType": "application_type",
    "statutoryExpiryDate": "statutory_expiry_date",
    "decisionExpiryDate": "decision_expiry_date",
    "agentSurname": "agent_surname",
    "agentName": "agent_surname",
    "officerName": "officer_name",
    "appealType": "appeal_type",
    "receivedDate": "received_date",
    "commentsMode": "comments_mode",
    "publicityEndDate": "publicity_end_date",
    "submissionExpiryDate": "submission_expiry_date",
    "applicationDate": "application_date",
    "decisionDueDate": "decision_due_date",
    "uprn": "uprn",
    "agentPropKey": "agent_prop_key",
    "propertyId": "property_id",
}

DUBLIN_DATE_FIELDS = {
    "registration_date",
    "decision_date",
    "final_grant_date",
    "extension_date",
    "appeal_lodged_date",
    "appeal_decision_date",
    "appeal_notify_date",
    "register_date",
    "dispatch_date",
    "statutory_expiry_date",
    "decision_expiry_date",
    "received_date",
    "publicity_end_date",
    "submission_expiry_date",
    "application_date",
    "decision_due_date",
}


DUBLIN_SEARCH_URL = "https://planningapi.agileapplications.ie/api/application/search"
DUBLIN_REQUEST_ATTEMPTS = 10
DUBLIN_REQUEST_WORKERS = 10
DUBLIN_FIRST_YEAR = 1990
DUBLIN_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "x-client": "DCC",
    "x-product": "CITIZENPORTAL",
    "x-service": "PA",
}
_DUBLIN_RATE_LOCK = threading.Lock()
_DUBLIN_NEXT_REQUEST_AT = 0.0


def _pace_dublin_requests():
    """Space request starts globally, not once per concurrent worker."""
    global _DUBLIN_NEXT_REQUEST_AT
    with _DUBLIN_RATE_LOCK:
        now = time.monotonic()
        wait = max(0.0, _DUBLIN_NEXT_REQUEST_AT - now)
        if wait:
            time.sleep(wait)
        _DUBLIN_NEXT_REQUEST_AT = max(now, _DUBLIN_NEXT_REQUEST_AT) + max(
            0.0, SLEEP_BETWEEN_REQUESTS
        )


def _pause_dublin_requests(delay):
    """Apply a server-requested/backoff pause to every worker."""
    global _DUBLIN_NEXT_REQUEST_AT
    with _DUBLIN_RATE_LOCK:
        _DUBLIN_NEXT_REQUEST_AT = max(_DUBLIN_NEXT_REQUEST_AT, time.monotonic() + delay)


def _dublin_request(session, url, **kwargs):
    """Make a Dublin API request with Mayo-style transient-error retries."""
    for attempt in range(DUBLIN_REQUEST_ATTEMPTS):
        try:
            _pace_dublin_requests()
            response = session.get(
                url,
                headers=DUBLIN_HEADERS,
                timeout=120,
                **kwargs,
            )
            status_code = response.status_code
            if status_code == 429:
                if attempt == DUBLIN_REQUEST_ATTEMPTS - 1:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                try:
                    retry_delay = float(retry_after)
                except (TypeError, ValueError):
                    retry_delay = 0
                delay = max(retry_delay, 2**attempt)
                _pause_dublin_requests(delay)
                time.sleep(delay)
                continue
            if isinstance(status_code, int) and status_code >= 500:
                response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == DUBLIN_REQUEST_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)


def parse_dublin_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()

    for date_format in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%a, %d %b %Y %H:%M:%S GMT",
    ):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass

    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def parse_dublin_application(data):
    if data.get("status_code") == 404:
        return None

    props = {}
    for old, new in DUBLIN_FIELD_MAP.items():
        value = data.get(old)
        if new in DUBLIN_DATE_FIELDS:
            value = parse_dublin_date(value)
        props[new] = value

    props["lat"], props["lng"] = itm_to_lat_lng(
        data.get("easting"),
        data.get("northing"),
    )
    if props["lat"] is None and data.get("gridReference"):
        try:
            easting, northing = data["gridReference"].split(",", 1)
            props["lat"], props["lng"] = itm_to_lat_lng(easting, northing)
        except (TypeError, ValueError):
            pass
    if not props.get("status_description"):
        props["status_description"] = data.get("status")

    if not props["objid"] or not props["address"]:
        return None

    return DublinObject.parse(props)


def _get_dublin_search_results(
    session,
    location,
    searched_terms,
    refinement_characters=string.ascii_lowercase,
    searched_terms_lock=None,
):
    if searched_terms_lock:
        with searched_terms_lock:
            if location in searched_terms:
                return []
            searched_terms.add(location)
    else:
        if location in searched_terms:
            return []
        searched_terms.add(location)
    response = _dublin_request(
        session,
        DUBLIN_SEARCH_URL,
        params={
            "location": location,
            "openApplications": "false",
        },
    )
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if response.status_code == 400:
        try:
            errors = response.json()
        except ValueError:
            errors = []
        message = " ".join(
            error.get("message", "") for error in errors if isinstance(error, dict)
        )
        if "Too many records have been found" in message:
            records = []
            refinements = [
                f"{location}{letter}" for letter in refinement_characters
            ] + [f"{letter}{location}" for letter in refinement_characters]
            for refinement in refinements:
                records.extend(
                    _get_dublin_search_results(
                        session,
                        refinement,
                        searched_terms,
                        refinement_characters,
                        searched_terms_lock,
                    )
                )
            return records
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "results" not in payload:
        raise RuntimeError(f"Unexpected Dublin search response for {location!r}")
    return payload["results"]


def _dublin_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        return response.text or ""
    if isinstance(payload, list):
        return " ".join(
            str(item.get("message", item)) if isinstance(item, dict) else str(item)
            for item in payload
        )
    if isinstance(payload, dict):
        return " ".join(str(value) for value in payload.values())
    return str(payload)


def _get_dublin_date_results(session, start, end):
    response = _dublin_request(
        session,
        DUBLIN_SEARCH_URL,
        params={
            "registrationDateFrom": start.isoformat(),
            "registrationDateTo": end.isoformat(),
            "openApplications": "false",
        },
    )
    if response.status_code == 400 and "Too many records" in _dublin_error_message(
        response
    ):
        if start >= end:
            response.raise_for_status()
        midpoint = start + (end - start) // 2
        return _get_dublin_date_results(
            session, start, midpoint
        ) + _get_dublin_date_results(session, midpoint + timedelta(days=1), end)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "results" not in payload:
        raise RuntimeError(
            f"Unexpected Dublin date-search response for {start} to {end}"
        )
    return payload["results"]


def _dublin_month_ranges(today=None):
    today = today or date.today()
    current = date(DUBLIN_FIRST_YEAR, 1, 1)
    ranges = []
    while current <= today:
        next_month = (
            date(current.year + 1, 1, 1)
            if current.month == 12
            else date(current.year, current.month + 1, 1)
        )
        ranges.append((current, min(today, next_month - timedelta(days=1))))
        current = next_month
    return ranges


def get_all_dublin_applications(session=None, search_terms=None):
    if search_terms is None:
        date_ranges = _dublin_month_ranges()
        if session is not None:
            records_by_id = {}
            for start, end in progressbar.progressbar(date_ranges, prefix="Dublin: "):
                for record in _get_dublin_date_results(session, start, end):
                    if record.get("id") is not None:
                        records_by_id[record["id"]] = record
            return list(records_by_id.values())

        local = threading.local()

        def search_dates(date_range):
            if not hasattr(local, "session"):
                local.session = requests.Session()
            return _get_dublin_date_results(local.session, *date_range)

        records_by_id = {}
        bar = progressbar.ProgressBar(max_value=len(date_ranges), prefix="Dublin: ")
        with ThreadPoolExecutor(max_workers=DUBLIN_REQUEST_WORKERS) as executor:
            futures = [executor.submit(search_dates, value) for value in date_ranges]
            for completed, future in enumerate(as_completed(futures), 1):
                for record in future.result():
                    if record.get("id") is not None:
                        records_by_id[record["id"]] = record
                bar.update(completed)
        bar.finish()
        return [
            records_by_id[objid]
            for objid in sorted(records_by_id, key=lambda value: str(value))
        ]

    root_search_terms = list(search_terms)
    if session is not None:
        records_by_id = {}
        searched_terms = set()
        for location in progressbar.progressbar(root_search_terms, prefix="Dublin: "):
            for record in _get_dublin_search_results(session, location, searched_terms):
                if record.get("id") is not None:
                    records_by_id[record["id"]] = record
        return list(records_by_id.values())

    local = threading.local()
    searched_terms = set()
    searched_terms_lock = threading.Lock()

    def search(location):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        return _get_dublin_search_results(
            local.session,
            location,
            searched_terms,
            searched_terms_lock=searched_terms_lock,
        )

    records_by_id = {}
    bar = progressbar.ProgressBar(max_value=len(root_search_terms), prefix="Dublin: ")
    with ThreadPoolExecutor(max_workers=DUBLIN_REQUEST_WORKERS) as executor:
        futures = [executor.submit(search, location) for location in root_search_terms]
        for completed, future in enumerate(as_completed(futures), 1):
            for record in future.result():
                if record.get("id") is not None:
                    records_by_id[record["id"]] = record
            bar.update(completed)
    bar.finish()
    return [
        records_by_id[objid]
        for objid in sorted(records_by_id, key=lambda value: str(value))
    ]


def download_dublin():
    objects = [
        obj
        for record in get_all_dublin_applications()
        if (obj := parse_dublin_application(record)) is not None
    ]

    write_to_db(dublin_db, DublinObject, objects)


class DublinObject(Model):
    objid = IntegerField()
    application_reference = CharField(null=True, index=True)
    address = CharField()
    searchable_address = CharField()

    proposal = TextField(null=True)
    applicant_surname = CharField(null=True)
    applicant_prop_key = CharField(null=True)

    registration_date = DateField(null=True)
    decision_date = DateField(null=True)
    final_grant_date = DateField(null=True)
    extension_date = DateField(null=True)
    appeal_lodged_date = DateField(null=True)
    appeal_decision_date = DateField(null=True)
    appeal_notify_date = DateField(null=True)
    register_date = DateField(null=True)
    dispatch_date = DateField(null=True)
    statutory_expiry_date = DateField(null=True)
    decision_expiry_date = DateField(null=True)
    received_date = DateField(null=True)
    publicity_end_date = DateField(null=True)
    submission_expiry_date = DateField(null=True)
    application_date = DateField(null=True)
    decision_due_date = DateField(null=True)

    decision_text = CharField(null=True)
    abp_reference = CharField(null=True)
    appeal_decision = CharField(null=True)
    postcode = CharField(null=True)

    lat = FloatField(null=True)
    lng = FloatField(null=True)

    full_proposal = TextField(null=True)
    status_description = CharField(null=True)
    status_owner = CharField(null=True)
    status_non_owner = CharField(null=True)
    application_type_id = IntegerField(null=True)
    application_type = CharField(null=True)
    agent_surname = CharField(null=True)
    officer_name = CharField(null=True)
    appeal_type = CharField(null=True)
    comments_mode = CharField(null=True)
    uprn = CharField(null=True)
    agent_prop_key = CharField(null=True)
    property_id = IntegerField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(DUBLIN_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(DublinObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.objid}: {self.address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.address)

    @staticmethod
    def parse(data):
        if isinstance(data, DublinObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return DublinObject(**data)


class DublinDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return DublinObject.select().count()

    def __iter__(self) -> Iterable[DublinObject]:
        return DublinObject.select().iterator()

    def drop_data(self) -> None:
        DublinObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([DublinObject], safe=True)
        self.db.create_tables([DublinObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(DUBLIN_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([DublinObject])

    def close(self):
        self.db.close()

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        county=None,
        eircode=None,
        eircode_routing_key=None,
        partial: bool = False,
    ) -> List[DublinObject]:
        filters = {}

        query = DublinObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(DublinObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(DublinObject.searchable_address.contains(address))
            else:
                query = query.where(DublinObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    DublinObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        DublinObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


dublin_db = DublinDB()
