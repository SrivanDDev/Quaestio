import json

import pytest

from quaestio.analyzer import analyze, select_entries
from quaestio.models import LogEntry, LogLevel
from quaestio.parser import LogParseError, parse_file, parse_json_line, parse_lines

VALID = "2026-08-27 21:30:15 ERROR database Connection refused"


def test_parser_is_lazy_and_locates_errors():
    def lines():
        yield VALID
        yield "\n"
        yield "broken"
        pytest.fail("parser read past a malformed record")

    entries = parse_lines(lines(), source="app.log")
    assert next(entries).message == "Connection refused"
    with pytest.raises(LogParseError, match=r"app.log:3:") as caught:
        next(entries)
    assert caught.value.line_number == 3
    assert caught.value.__cause__ is not None


def test_skip_callback_and_blank_lines():
    errors = []
    entries = parse_lines(["\n", "bad", VALID, "bad again"],
                          skip_invalid=True, on_error=errors.append)
    assert analyze(entries).total_entries == 1
    assert [e.line_number for e in errors] == [2, 4]


def test_utf8_bom_and_unicode(tmp_path):
    path = tmp_path / "unicode.log"
    path.write_text(VALID + " café\n", encoding="utf-8-sig")
    assert list(parse_file(path))[0].message.endswith("café")


def test_decoding_errors_are_not_skipped(tmp_path):
    path = tmp_path / "bad.log"
    path.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        list(parse_file(path, skip_invalid=True))


@pytest.mark.parametrize("record", ["{}", "[]", "null", "invalid", '{"timestamp":1}',
                                      '{"timestamp":"2026-08-27","level":"BAD","source":"a","message":"b"}'])
def test_invalid_ndjson(record):
    with pytest.raises(LogParseError):
        parse_json_line(record)


def test_ndjson_normalizes_event():
    entry = parse_json_line(json.dumps(dict(timestamp="2026-08-27T21:30:15+00:00",
                                          level="ERROR", source="db", message="café",
                                          request_id="ignored")))
    assert entry.level == LogLevel.ERROR
    assert entry.timestamp.utcoffset().total_seconds() == 0
    assert entry.message == "café"
    assert not hasattr(entry, "request_id")


def test_text_and_ndjson_equivalence(sample_log):
    assert analyze(parse_file(sample_log)) == analyze(parse_file(sample_log.with_suffix(".ndjson"), format="ndjson"))


def event(message, level="ERROR", source="db"):
    return LogEntry(timestamp="2026-08-27T21:30:15", level=level,
                    source=source, message=message)


def test_all_levels_and_critical_semantics():
    result = analyze(event(level.value, level) for level in LogLevel)
    assert result.total_entries == 5
    assert result.error_rate == 0.2
    assert result.critical_count == 1
    assert result.top_errors == [("ERROR", 1)]


def test_top_limit_and_ties():
    assert analyze(event(str(i)) for i in range(8)).top_errors == [(str(i), 1) for i in range(5)]
    assert analyze([event("first"), event("second"), event("second")], top=1).top_errors == [("second", 2)]
    with pytest.raises(ValueError, match="at least 1"):
        analyze([], top=0)


def test_filters_are_lazy_and_change_denominator():
    entries = iter([event("failure"), event("ok", "INFO"), event("other", source="web")])
    selected = select_entries(entries, source="db", level=LogLevel.ERROR)
    assert analyze(selected).error_rate == 1.0
    assert analyze(select_entries([event("a")], source="missing")).total_entries == 0


def test_large_one_pass_stream():
    entry = event("repeated")
    class OnePass:
        def __init__(self):
            self.used = False

        def __iter__(self):
            assert not self.used, "input consumed more than once"
            self.used = True
            yield from (entry for _ in range(50_000))

    result = analyze(OnePass())
    assert result.total_entries == 50_000
    assert result.top_errors == [("repeated", 50_000)]


@pytest.mark.parametrize("content", [VALID, "broken"])
def test_file_handle_closes_on_stop_or_error(tmp_path, monkeypatch, content):
    path = tmp_path / "input.log"
    path.write_text(content)
    file = path.open(encoding="utf-8")
    monkeypatch.setattr("quaestio.parser.open", lambda *args, **kwargs: file, raising=False)
    entries = parse_file(path)
    if content == VALID:
        next(entries)
        assert not file.closed
        entries.close()
    else:
        with pytest.raises(LogParseError):
            next(entries)
    assert file.closed


def test_invalid_timestamp_is_wrapped():
    with pytest.raises(LogParseError, match="Invalid timestamp") as caught:
        list(parse_lines(["2026-99-27 21:30:15 ERROR db Failure"]))
    assert isinstance(caught.value.__cause__.__cause__, ValueError)
