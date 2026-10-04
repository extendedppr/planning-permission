# Irish Planning Permission

Download, search, and analyse Irish planning applications from council sources.
Coverage and available fields vary by source; a missing date does not mean an
application is recent, and an empty search does not prove that no application exists.

## Setup

```bash
poetry install
```

## Download and refresh

```bash
poetry run download_planning_permission
poetry run download_planning_permission --county dublin --county cork
```

## Search

```bash
poetry run search --address-substr-csv main,street --county dublin --county meath
poetry run search --reference 24/123 --county cork
poetry run search --received-from 2024-01-01 --received-to 2024-12-31 --decision grant
poetry run search --status pending --output csv > applications.csv
poetry run search --all-features --output json
```

- `last_updated` is the last successful local refresh, not the council's record modification time. Older databases show `unknown` until refreshed.
- Table values are shortened unless `--all` is set. JSON and CSV retain full values.
