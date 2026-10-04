"""One lazy registry for county adapters; importing it does not open databases."""

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

COUNTIES = (
    "dublin",
    "cork",
    "galway",
    "kildare",
    "meath",
    "limerick",
    "tipperary",
    "donegal",
    "wexford",
    "kerry",
    "wicklow",
    "louth",
    "mayo",
    "clare",
    "waterford",
    "kilkenny",
    "westmeath",
    "laois",
    "offaly",
    "cavan",
    "roscommon",
    "sligo",
    "monaghan",
    "carlow",
    "longford",
    "leitrim",
)


@dataclass(frozen=True)
class County:
    name: str

    @property
    def module(self):
        return import_module(f"planning_permission.{self.name}")

    @property
    def database(self):
        return getattr(self.module, f"{self.name}_db")

    @property
    def model(self):
        return getattr(self.module, f"{self.name.title()}Object")

    def download(self):
        from planning_permission.telemetry import fetch_stats

        token = fetch_stats.set({})
        try:
            return getattr(self.module, f"download_{self.name}")()
        finally:
            fetch_stats.reset(token)

    def database_path(self, data_dir):
        return Path(data_dir) / self.name / "db.sqlite"

    @property
    def sources(self):
        # Adapters retain endpoint-specific configuration, exposed here for inspection.
        return {
            key: value
            for key, value in vars(self.module).items()
            if key.endswith(("_URL", "_URLS", "_LAYERS"))
        }


REGISTRY = {name: County(name) for name in COUNTIES}
