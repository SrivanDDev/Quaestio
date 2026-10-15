from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from quaestio.analyzer import analyze
from quaestio.errors import LogParseError as SharedParseError
from quaestio.layouts import LayoutConfig, LayoutConfigError, build_layout_parser, load_layout
from quaestio.parser import LogParseError, parse_file, parse_lines
from quaestio.cli import app

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()
PATTERN = r'(?P<level>\w+)\|(?P<timestamp>[^|]+)\|(?P<message>.+)'


def config(**changes):
    return LayoutConfig(format='regex', pattern=PATTERN, **changes)


def test_exception_import_compatibility():
    assert LogParseError is SharedParseError


def test_regex_reorders_fields_and_defaults_source():
    entry = build_layout_parser(config())('warn|2026-10-07T10:30:00|High memory')
    assert entry.timestamp == datetime(2026, 10, 7, 10, 30)
    assert entry.level.value == 'WARNING'
    assert entry.source == 'unknown'
    assert entry.message == 'High memory'


def test_custom_date_and_alias():
    parser = build_layout_parser(config(timestamp_format='%d/%m/%Y %H:%M:%S',
                                        level_map={'severe': 'ERROR'}))
    entry = parser('SEVERE|07/10/2026 10:30:05|Failed')
    assert entry.timestamp == datetime(2026, 10, 7, 10, 30, 5)
    assert entry.level.value == 'ERROR'


def test_separate_date_and_time_groups():
    layout = LayoutConfig(format='regex', pattern=r'(?P<date>\S+) (?P<time>\S+) (?P<level>\w+) (?P<message>.+)')
    entry = build_layout_parser(layout)('2026-10-07 10:30:00 INFO Started')
    assert entry.timestamp == datetime(2026, 10, 7, 10, 30)


def test_explicit_default_level():
    layout = LayoutConfig(format='regex', pattern=r'(?P<timestamp>[^|]+)\|(?P<message>.+)',
                          defaults={'source': 'worker', 'level': 'INFO'})
    assert build_layout_parser(layout)('2026-10-07|Started').level.value == 'INFO'


def test_regex_fullmatch_not_substring():
    parser = build_layout_parser(config())
    with pytest.raises(LogParseError):
        parser('prefix: INFO|2026-10-07|Started')


@pytest.mark.parametrize('changes', [
    {'pattern': '('}, {'pattern': '(?P<message>.+)'},
    {'pattern': '(?P<timestamp>.+)'}, {'pattern': None},
    {'fields': {'message': 'msg'}}, {'defaults': {'timestamp': 'invented'}},
    {'defaults': {'source': ''}}, {'defaults': {'level': 'BAD'}},
    {'timestamp_format': '%Q'}, {'timestamp_format': 'nonsense'},
    {'timestamp_format': ''}, {'level_map': {'foo': 'BAD'}},
    {'level_map': {'': 'ERROR'}}, {'level_map': {'warn': 'ERROR', 'WARN': 'WARNING'}},
    {'surprise': True},
])
def test_invalid_regex_configuration(changes):
    values = dict(format='regex', pattern=PATTERN)
    values.update(changes)
    with pytest.raises(ValidationError):
        LayoutConfig(**values)


@pytest.mark.parametrize('fields', [
    {'timestamp': []}, {'timestamp': ['event', -1]}, {'timestamp': ['event', True]},
    {'timestamp': ''}, {'timestamp': ['']}, {'unexpected': 'foo'},
])
def test_invalid_field_paths(fields):
    with pytest.raises(ValidationError):
        LayoutConfig(format='ndjson', fields=fields)


@pytest.mark.parametrize('timestamp_format,value,expected', [
    ('unix', 0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
    ('unix_ms', 1500, datetime(1970, 1, 1, 0, 0, 1, 500000, tzinfo=timezone.utc)),
    ('iso', '2026-10-07T10:30:00Z', datetime(2026, 10, 7, 10, 30, tzinfo=timezone.utc)),
])
def test_timestamp_modes(timestamp_format, value, expected):
    layout = LayoutConfig(format='ndjson', timestamp_format=timestamp_format)
    entry = build_layout_parser(layout)(json.dumps(dict(timestamp=value, level='err', message='Failed')))
    assert entry.timestamp == expected
    assert entry.level.value == 'ERROR'


@pytest.mark.parametrize('timestamp', [True, 'nan', 'inf', 'not a date', 1e100])
def test_bad_epoch_is_a_parse_error(timestamp):
    parser = build_layout_parser(LayoutConfig(format='ndjson', timestamp_format='unix'))
    with pytest.raises(LogParseError):
        parser(json.dumps(dict(timestamp=timestamp, level='INFO', message='a')))


def test_nested_objects_and_array_paths():
    layout = LayoutConfig(format='json', fields={'timestamp': ['events', 0, 'at'],
                          'level': ['events', 0, 'severity'], 'message': 'msg'},
                          level_map={'40': 'ERROR'})
    entry = build_layout_parser(layout)(json.dumps({'events': [{'at': '2026-10-07', 'severity': 40}], 'msg': 'Failure'}))
    assert entry.level.value == 'ERROR'


def test_dotted_mapping_is_a_literal_key():
    layout = LayoutConfig(format='ndjson', fields={'message': 'log.message'})
    entry = build_layout_parser(layout)(json.dumps({'timestamp': '2026-10-07', 'level': 'INFO', 'log.message': 'Started'}))
    assert entry.message == 'Started'


@pytest.mark.parametrize('record', [
    {}, [], {'timestamp': '2026-10-07', 'level': 'INFO'},
    {'timestamp': '2026-10-07', 'level': 'INFO', 'message': {'object': 'bad'}},
    {'timestamp': '2026-10-07', 'level': 'INFO', 'message': ''},
    {'timestamp': '2026-10-07', 'level': 'INFO', 'source': [], 'message': 'a'},
    {'timestamp': '2026-10-07', 'level': True, 'message': 'a'},
])
def test_missing_or_wrong_fields_are_errors(record):
    parser = build_layout_parser(LayoutConfig(format='ndjson'))
    with pytest.raises(LogParseError):
        parser(json.dumps(record))


def test_missing_nested_path_uses_explicit_source_default():
    layout = LayoutConfig(format='ndjson', fields={'source': ['services', 3, 'name']},
                          defaults={'source': 'worker'})
    entry = build_layout_parser(layout)(json.dumps({'timestamp': '2026-10-07', 'level': 'INFO', 'message': 'Started', 'services': []}))
    assert entry.source == 'worker'


@pytest.mark.parametrize('line', [
    '2026-10-07 10:30:00 INFO server Started',
    '2026-10-07 10:30:00,123 info server Started',
    '[2026-10-07 10:30:00] [INFO] [server] Started',
    '[2026-10-07 10:30:00] [INFO] Started',
    '2026-10-07T10:30:00+00:00 INFO server Started',
    'INFO | server | 2026-10-07T10:30:00 | Started',
    '2026-10-07T10:30:00 | INFO | server | Started',
    '{"timestamp":"2026-10-07T10:30:00","level":"info","source":"server","message":"Started"}',
])
def test_auto_known_layouts(line):
    entry = list(parse_lines([line], format='auto'))[0]
    assert entry.level.value == 'INFO'
    assert entry.message == 'Started'


def test_auto_locks_format_and_reports_change():
    entries = parse_lines(['2026-10-07 10:30:00 INFO server Started',
                           '[2026-10-07 10:30:01] [ERROR] [server] Failed'], format='auto')
    next(entries)
    with pytest.raises(LogParseError, match='<stream>:2:'):
        next(entries)


def test_auto_skips_invalid_until_first_valid_then_keeps_lock():
    errors = []
    result = analyze(parse_lines(['bad', '[2026-10-07] [WARN] a',
                                  '2026-10-07 10:30:00 INFO server different',
                                  '[2026-10-07] [ERROR] b'], format='auto',
                                 skip_invalid=True, on_error=errors.append))
    assert result.total_entries == 2
    assert [error.line_number for error in errors] == [1, 3]


def test_invalid_configuration_is_not_skipped():
    with pytest.raises(LayoutConfigError):
        list(parse_lines([], format='regex', skip_invalid=True))
    with pytest.raises(LayoutConfigError):
        list(parse_lines([], format='auto', layout=config(), skip_invalid=True))


def test_json_alias_preserves_native_parser():
    line = '{"timestamp":"2026-10-07","level":"INFO","source":"a","message":"b"}'
    assert list(parse_lines([line], format='json')) == list(parse_lines([line], format='ndjson'))


def test_config_json_alias_matches_cli_json_format():
    layout = LayoutConfig(format='ndjson')
    assert len(list(parse_lines(['{"timestamp":"2026-10-07","level":"INFO","message":"a"}'], format='json', layout=layout))) == 1


def test_regex_profile_keeps_stream_lazy_and_located():
    def lines():
        yield 'INFO|2026-10-07|Started'
        yield 'wrong'
        pytest.fail('read beyond failed record')
    entries = parse_lines(lines(), layout=config(), source='custom.log')
    assert next(entries).source == 'unknown'
    with pytest.raises(LogParseError, match='custom.log:2:'):
        next(entries)


def test_profile_load_errors(tmp_path):
    path = tmp_path / 'profile.json'
    path.write_text('{"format":"regex","pattern":"("}')
    with pytest.raises(LayoutConfigError, match='Invalid parser configuration'):
        load_layout(path)
    path.write_text('invalid JSON')
    with pytest.raises(LayoutConfigError):
        load_layout(path)


@pytest.mark.parametrize('sample,profile,total', [
    ('custom-pipe.log', 'custom-pipe.json', 4), ('nested.ndjson', 'nested-json.json', 3),
])
def test_shipped_profiles_cli(sample, profile, total):
    result = runner.invoke(app, ['analyze', str(ROOT / 'examples' / sample), '--parser-config',
                                 str(ROOT / 'examples/layouts' / profile), '--output', 'json'])
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['total_entries'] == total
    assert data['top_errors'] == [['Connection refused', 2]]


def test_auto_cli():
    result = runner.invoke(app, ['analyze', str(ROOT / 'examples/bracketed.log'), '--format', 'auto', '--output', 'json'])
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['critical_count'] == 1
    assert data['warning_count'] == 1


def test_custom_stdin_and_skip(tmp_path):
    path = tmp_path / 'profile.json'
    path.write_text(config().model_dump_json())
    result = runner.invoke(app, ['analyze', '-', '--parser-config', str(path), '--skip-invalid', '--output', 'json'],
                           input='wrong\nERROR|2026-10-07|Failure\n')
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)['error_count'] == 1
    assert 'Skipped 1' in result.stderr


def test_cli_config_conflict_and_config_cannot_be_output(tmp_path):
    path = tmp_path / 'profile.json'
    content = config().model_dump_json()
    path.write_text(content)
    result = runner.invoke(app, ['analyze', '-', '--format', 'text', '--parser-config', str(path)], input='anything')
    assert result.exit_code == 1
    assert 'conflicts' in result.stderr
    result = runner.invoke(app, ['analyze', '-', '--parser-config', str(path), '--output-file', str(path)], input='anything')
    assert result.exit_code == 1
    assert 'must differ' in result.stderr
    assert path.read_text() == content


def test_cli_invalid_config_is_fatal_even_with_skip(tmp_path):
    path = tmp_path / 'profile.json'
    path.write_text('{}')
    result = runner.invoke(app, ['analyze', '-', '--parser-config', str(path), '--skip-invalid'], input='bad')
    assert result.exit_code == 1
    assert result.stdout == ''
    assert 'Invalid parser configuration' in result.stderr
    assert 'Traceback' not in result.stderr


def test_custom_timestamp_trims_capture_whitespace():
    parser = build_layout_parser(config(timestamp_format='%d/%m/%Y'))
    assert parser('INFO| 07/10/2026 |Started').timestamp == datetime(2026, 10, 7)


def test_auto_state_is_independent_per_stream():
    first = parse_lines(['2026-10-07 10:30:00 INFO server Started'], format='auto')
    second = parse_lines(['[2026-10-07] [ERROR] Failed'], format='auto')
    assert next(first).level.value == 'INFO'
    assert next(second).level.value == 'ERROR'


@pytest.mark.parametrize('format,line', [
    ('text', '2026-10-07 10:30:00 info server Started'),
    ('ndjson', '{"timestamp":"2026-10-07","level":"info","source":"server","message":"Started"}'),
])
def test_native_validation_stays_strict(format, line):
    with pytest.raises(LogParseError):
        list(parse_lines([line], format=format))
    assert list(parse_lines([line], format='auto'))[0].level.value == 'INFO'
