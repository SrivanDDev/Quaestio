from datetime import datetime

import pytest

from quaestio.models import LogLevel
from quaestio.parser import LogParseError,parse_line,parse_file


def test_parse_valid_line():
    line = "2026-08-27 21:30:15 ERROR database Connection refused"

    entry = parse_line(line)

    assert entry.timestamp == datetime(2026, 8, 27, 21, 30, 15)
    assert entry.level == LogLevel.ERROR
    assert entry.source == "database"
    assert entry.message == "Connection refused"
def test_parse_invalid_line():
    line = "this is not a valid log line"

    with pytest.raises(LogParseError):
        parse_line(line)

def test_parse_invalid_level():
    line = "2026-08-27 21:30:15 WHATEVER database Connection refused"

    with pytest.raises(LogParseError):
        parse_line(line)

def test_parse_file():
    entries = list(parse_file("examples/sample.log"))

    assert len(entries) == 4
    assert entries[0].level == LogLevel.INFO
    assert entries[1].level == LogLevel.WARNING
    assert entries[2].level == LogLevel.ERROR
    assert entries[2].source == "database"
    assert entries[3].message == "Request completed"