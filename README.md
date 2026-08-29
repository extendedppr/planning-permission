# Irish Planning Permission

Scrape and interact with Irish planning permissions.

Not all have associated dates as we get dates from the national database sometimes which only has data from 2016. There are probably ways to get all dates but will work on that at some other point.

# Installation

```bash
poetry install
```

# Downloading / Scraping Data

```bash
poetry run download_planning_permission
```

Download one county by passing its lowercase name from the list above:

```bash
poetry run download_planning_permission --county dublin
```

# Usage

```bash
poetry run search --address-substr-csv 9,mal --exclude-address-substr-csv south
```
