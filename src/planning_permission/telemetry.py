"""Per-county counters collected by download adapters."""

from contextvars import ContextVar

fetch_stats = ContextVar("fetch_stats", default=None)


def record_fetch(count):
    stats = fetch_stats.get()
    if stats is not None:
        stats["records_fetched"] = stats.get("records_fetched", 0) + count
