from quaestio.analyzer import analyze
from quaestio.parser import parse_file

def test_analyze_file():
    entries = parse_file("examples/sample.log")

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