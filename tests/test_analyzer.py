from quaestio.analyzer import analyze
from quaestio.parser import parse_file
from quaestio.models import LogEntry, LogLevel

def test_analyze_file(sample_log):
    entries = parse_file(sample_log)

    result = analyze(entries)

    assert result.total_entries == 4
    assert result.info_count == 2
    assert result.warning_count == 1
    assert result.error_count == 1
    assert result.debug_count == 0
    assert result.critical_count == 0
    assert result.error_rate == 0.25

def test_analyze_empty():
    result = analyze([])

    assert result.total_entries == 0
    assert result.error_count == 0
    assert result.error_rate == 0.0

def test_analyze_repeated_errors():
    entries = [
        LogEntry(
            timestamp="2026-08-27 21:30:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
        LogEntry(
            timestamp="2026-08-27 21:31:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
        LogEntry(
            timestamp="2026-08-27 21:32:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
    ]

    result = analyze(entries)

    assert result.error_count == 3
    assert result.top_errors == [("Connection refused", 3)]

def test_analyze_error_ranking():
    entries = [
        LogEntry(
            timestamp="2026-08-27 21:30:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
        LogEntry(
            timestamp="2026-08-27 21:31:15",
            level=LogLevel.ERROR,
            source="database",
            message="Timeout",
        ),
        LogEntry(
            timestamp="2026-08-27 21:32:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
        LogEntry(
            timestamp="2026-08-27 21:33:15",
            level=LogLevel.ERROR,
            source="database",
            message="Disk full",
        ),
        LogEntry(
            timestamp="2026-08-27 21:34:15",
            level=LogLevel.ERROR,
            source="database",
            message="Timeout",
        ),
        LogEntry(
            timestamp="2026-08-27 21:35:15",
            level=LogLevel.ERROR,
            source="database",
            message="Connection refused",
        ),
    ]

    result = analyze(entries)

    assert result.top_errors == [
        ("Connection refused", 3),
        ("Timeout", 2),
        ("Disk full", 1),
    ]
