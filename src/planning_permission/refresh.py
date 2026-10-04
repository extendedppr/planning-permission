"""Validated, transactional dataset replacement and refresh metadata."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from peewee import Model, chunked
from planning_permission.schema import normalise_record
from planning_permission.telemetry import fetch_stats


def read_metadata(database):
    if not database.table_exists("refresh_metadata"):
        return {}
    row = database.execute_sql(
        "SELECT payload FROM refresh_metadata WHERE id = 1"
    ).fetchone()
    return json.loads(row[0]) if row else {}


def replace_dataset(database, model, objects, batch_size=500):
    objects = list(objects)
    if not objects:
        raise ValueError("Refusing to replace saved data with an empty download")
    fields = {field.name: field.clone() for field in model._meta.sorted_fields}
    stage = type(
        "RefreshStage",
        (Model,),
        {
            **fields,
            "Meta": type(
                "Meta",
                (),
                {"database": database, "table_name": "refresh_" + uuid4().hex},
            ),
        },
    )
    records = [normalise_record(obj) for obj in objects]
    references = [
        str(row["application_number"]).strip().casefold()
        for row in records
        if row["application_number"] not in (None, "")
    ]
    report = {
        "last_success": datetime.now(timezone.utc).isoformat(),
        "records_fetched": (fetch_stats.get() or {}).get("records_fetched"),
        "records_prepared": len(objects),
        "records_saved": len(objects),
        "unique_references": len(set(references)),
        "duplicate_references": len(references) - len(set(references)),
        "missing_pct": {
            key: round(
                100 * sum(row[key] in (None, "") for row in records) / len(records), 2
            )
            for key in (
                "application_number",
                "address",
                "received",
                "decision",
                "source_url",
            )
        },
    }
    # Some sources legitimately repeat application references for multiple sites.
    # Preserve those rows and report duplicates; source/model keys enforce identity.
    with model.bind_ctx(database):
        with database.atomic():
            stage.create_table()
            for batch in chunked(objects, batch_size):
                stage.insert_many([dict(obj.__data__) for obj in batch]).execute()
            if stage.select().count() != len(objects):
                raise ValueError("Staged record count differs from downloaded count")
            database.drop_tables([model], safe=True)
            database.create_tables([model])
            target_fields = model._meta.sorted_fields
            model.insert_from(
                stage.select(*[stage._meta.fields[f.name] for f in target_fields]),
                target_fields,
            ).execute()
            stage.drop_table()
            database.execute_sql(
                "CREATE TABLE IF NOT EXISTS refresh_metadata (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)"
            )
            database.execute_sql(
                "INSERT OR REPLACE INTO refresh_metadata (id, payload) VALUES (1, ?)",
                (json.dumps(report),),
            )
    return report
