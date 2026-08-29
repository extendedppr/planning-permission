import zlib

from peewee import CharField, FloatField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.utils import (
    arcgis_download,
    clean_address_for_comparison,
    write_to_db,
)


def _first(data, *names):
    return next(
        (
            data[name]
            for name in names
            if data.get(name) not in (None, "", "n/a", "n\\a")
        ),
        None,
    )


class LocalPlanningObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(unique=True)
    address = TextField(default="")
    searchable_address = TextField(default="", index=True)
    planning_authority = CharField(null=True)
    applicant_name = CharField(null=True)
    application_status = CharField(null=True)
    application_type = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    received_date = CharField(null=True)
    decision_date = CharField(null=True)
    decision_due_date = CharField(null=True)
    withdrawn_date = CharField(null=True)
    grant_date = CharField(null=True)
    expiry_date = CharField(null=True)
    appeal_reference = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = CharField(null=True)
    appeal_submitted_date = CharField(null=True)
    further_info_request_date = CharField(null=True)
    further_info_received_date = CharField(null=True)
    itm_easting = FloatField(null=True)
    itm_northing = FloatField(null=True)
    details_url = TextField(null=True)
    documents_url = TextField(null=True)

    class Meta:
        table_name = "planning_applications"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = " ".join((self.address or "").split())
        if not self.searchable_address:
            self.searchable_address = clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = clean_address_for_comparison(self.address)
        return super().save(*args, **kwargs)

    @classmethod
    def parse(cls, data, authority=None):
        if isinstance(data, cls):
            return data
        number = _first(
            data,
            "ApplicationNumber",
            "FILENUMBER",
            "FileNumber",
            "RefNo",
            "Planning_R",
            "Applicatio",
            "Plan_id",
            "Ref_Number",
            "RecordID",
            "File_numbe",
            "file_num",
            "FILENUMB_1",
        )
        if number is None:
            return None
        number = str(number).strip()
        if data.get("file_year") and number == str(data.get("file_num", "")).strip():
            number = f"{str(data['file_year']).strip()}/{number}"
        address_parts = [
            _first(data, "DevelopmentAddress", "Location", "ADDRESS"),
            _first(data, "Address1", "AddressLineA", "address_line_1"),
            _first(data, "Address2", "AddressLineB", "address_line_2"),
            _first(data, "AddressLineC", "address_line_3"),
        ]
        address = ", ".join(str(value).strip(" ,") for value in address_parts if value)
        source_id = _first(data, "OBJECTID_1", "OBJECTID", "FID")
        return cls(
            objid=zlib.crc32(f"{authority}:{number}:{source_id}".encode()),
            application_number=number,
            address=address,
            planning_authority=_first(data, "PlanningAuthority", "PlanningAu")
            or authority,
            applicant_name=_first(
                data, "ApplicantName", "APPLICANT", "APPLICANTS", "Name"
            ),
            application_status=_first(
                data,
                "ApplicationStatus",
                "Status",
                "STATUS",
                "Applicat_2",
                "App_Status",
            ),
            application_type=_first(
                data, "ApplicationType", "AppliType", "Applicat_1", "APPTYPE"
            ),
            description=_first(
                data,
                "DevelopmentDescription",
                "Description",
                "DevDescription",
                "DevDescr",
                "Descriptio",
                "DESCRIPTION",
                "Desc_",
                "DEVELOPMEN",
            ),
            decision=_first(data, "Decision", "DECISION"),
            received_date=_first(
                data,
                "ReceivedDate",
                "RecievedDate",
                "receiveddate",
                "received_date",
                "ReceivedDa",
                "DATERECEIV",
            ),
            decision_date=_first(
                data,
                "DecisionDate",
                "Decision_Date",
                "Decisiondate",
                "decision_date",
                "DecisionDa",
            ),
            decision_due_date=_first(
                data,
                "DecisionDueDate",
                "Decision_Due_Date",
                "DecisionDue",
                "DecisionDu",
            ),
            withdrawn_date=_first(
                data, "WithdrawnDate", "Withdrawn_Date", "WithdrawnD"
            ),
            grant_date=_first(data, "GrantDate", "Grant_Date"),
            expiry_date=_first(data, "ExpiryDate", "Expiry_Date"),
            appeal_reference=_first(data, "AppealRefNum", "AppealRefN"),
            appeal_decision=_first(data, "AppealDecision", "AppealDeci"),
            appeal_decision_date=_first(
                data, "AppealDecisionDate", "Appeal_Decision_Date", "AppealDe_1"
            ),
            appeal_submitted_date=_first(
                data, "AppealSubmittedDate", "Appeal_Submitted_Date", "AppealSubm"
            ),
            further_info_request_date=_first(data, "FIRequestDate"),
            further_info_received_date=_first(data, "FIRecDate"),
            itm_easting=_first(data, "ITMEasting", "XCoord"),
            itm_northing=_first(data, "ITMNorthing", "ITMNorthin", "YCoord"),
            details_url=_first(
                data, "LinkAppDetails", "MoreInfo", "More_Infor", "EPLANLINK", "Link"
            ),
            documents_url=_first(data, "LinkDocs", "LinkAppScanDetails", "IPLANLINK"),
        )


class LocalPlanningDB:
    def __init__(self, database, model):
        self.db, self.model = database, model
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([model])

    def __len__(self):
        return self.model.select().count()

    def __iter__(self):
        return self.model.select().iterator()

    def recreate(self):
        self.db.drop_tables([self.model], safe=True)
        self.db.create_tables([self.model])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ):
        query = self.model.select()
        if address:
            value = clean_address_for_comparison(address)
            query = query.where(
                self.model.searchable_address.contains(value)
                if partial
                else self.model.searchable_address == value
            )
        for value in address_substrs or []:
            query = query.where(
                self.model.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~self.model.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


def create_local_download(county, authority, database_path, urls):
    database = SqliteDatabase(database_path)
    model = type(
        f"{county.title()}Object",
        (LocalPlanningObject,),
        {
            "Meta": type(
                "Meta",
                (),
                {"database": database, "table_name": "planning_applications"},
            )
        },
    )
    db = LocalPlanningDB(database, model)

    def download():
        by_number = {}
        for label, url in urls:
            for record in arcgis_download(
                url, skip_sort=True, prefix=f"{county.title()} {label}: "
            ):
                parsed = model.parse(record, authority)
                if parsed is not None:
                    by_number[parsed.application_number.casefold()] = parsed
        write_to_db(db, model, list(by_number.values()))

    download.__name__ = f"download_{county}"
    return model, db, download
