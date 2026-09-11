from quaestio.models import AnalysisResult,LogEntry, LogLevel


def analyze(entries):
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

    return AnalysisResult(
        total_entries=total_entries,
        debug_count=debug_count,
        info_count=info_count,
        warning_count=warning_count,
        error_count=error_count,
        critical_count=critical_count,
        error_rate=error_rate
)