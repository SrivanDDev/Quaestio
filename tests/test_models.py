from datetime import datetime

from quaestio.models import LogLevel,LogEntry

def test_log_entry_creation():
    timestamp = datetime(2026, 8, 26, 10, 30, 0)

    entry = LogEntry(
        timestamp=timestamp,
        level=LogLevel.ERROR,
        source="database",
        message="Connection refused",
    )

    assert entry.timestamp == timestamp
    assert entry.level == LogLevel.ERROR
    assert entry.source == "database"
    assert entry.message == "Connection refused"

def test_log_values():
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.CRITICAL.value == "CRITICAL"

def test_log_entry_accepts_log_level_string():
    entry = LogEntry(
        timestamp=datetime(2026, 8, 26, 10, 30, 0),
        level="ERROR",
        source="database",
        message="Connection refused",
    )

    assert entry.level == LogLevel.ERROR