# Irish Planning Permission

Scrape and interact with Irish planning permissions.

Note that so far we only fully cover Dublin, Cork and Galway with partial coverage elsewhere.

# Installation

```bash
poetry install
```

# Downloading / Scraping Data

```bash
poetry run download_planning_permission
```

# Usage

```bash
poetry run search --address-substr-csv 9,mal --exclude-address-substr-csv south
```
