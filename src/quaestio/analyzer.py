from collections.abc import Iterable
from heapq import nlargest

from quaestio.models import AnalysisResult, LogEntry, LogLevel


def select_entries(entries: Iterable[LogEntry], *, source: str | None = None,
                   level: LogLevel | None = None) -> Iterable[LogEntry]:
    """Lazily select normalized entries using exact source/severity matches."""
    return (entry for entry in entries
            if (source is None or entry.source == source)
            and (level is None or entry.level == level))


def analyze(entries: Iterable[LogEntry], *, top: int = 5) -> AnalysisResult:
    """Consume once; ERROR rate excludes CRITICAL. Ranking ties keep input order.

    Memory grows with distinct ERROR messages, not with total input entries.
    """
    if top < 1:
        raise ValueError("top must be at least 1")
    total_entries = 0
    debug_count = 0
    info_count = 0
    warning_count = 0
    error_count = 0
    critical_count = 0
    error_counts = {}

    for entry in entries:
        total_entries += 1

        if entry.level == LogLevel.DEBUG:
            debug_count += 1
        elif entry.level == LogLevel.INFO:
            info_count += 1
        elif entry.level == LogLevel.WARNING:
            warning_count += 1
        elif entry.level == LogLevel.ERROR:
            error_count += 1
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
        elif entry.level == LogLevel.CRITICAL:
            critical_count += 1

    if total_entries == 0:
        error_rate = 0.0
    else:
        error_rate = error_count / total_entries
    top_errors = nlargest(
        top,
        error_counts.items(),
        key=lambda item: item[1],
    )

    return AnalysisResult(
        total_entries=total_entries,
        debug_count=debug_count,
        info_count=info_count,
        warning_count=warning_count,
        error_count=error_count,
        critical_count=critical_count,
        error_rate=error_rate,
        top_errors=top_errors,
    )
