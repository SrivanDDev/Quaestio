import csv
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from quaestio.cli import app

runner = CliRunner()
VALID = "2026-08-27 21:30:15 ERROR db Connection refused\n"


def test_help_keeps_analyze_subcommand():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.stdout


def test_sample_report(sample_log):
    result = runner.invoke(app, ["analyze", str(sample_log)])
    assert result.exit_code == 0
    assert "Total entries: 4" in result.stdout
    assert "25.0%" in result.stdout
    assert "Connection refused" in result.stdout


def test_stdin_json():
    result = runner.invoke(app, ["analyze", "-", "--output", "json"], input=VALID)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["top_errors"] == [["Connection refused", 1]]
    assert result.stderr == ""


def test_ndjson_cli(sample_log):
    result = runner.invoke(app, ["analyze", str(sample_log.with_suffix(".ndjson")),
                                 "--format", "ndjson", "--output", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["total_entries"] == 4


def test_csv_escapes_messages():
    message = 'Failure, "quoted" café'
    result = runner.invoke(app, ["analyze", "-", "--output", "csv"], input=VALID.replace("Connection refused", message))
    assert result.exit_code == 0
    rows = list(csv.DictReader(StringIO(result.stdout)))
    assert rows[-1] == {"section": "top_error", "name": message, "value": "1"}


def test_markup_is_literal():
    result = runner.invoke(app, ["analyze", "-"], input=VALID.replace("Connection refused", "[red]problem[/red]"))
    assert result.exit_code == 0
    assert "[red]problem[/red]" in result.stdout


def test_invalid_record_is_fail_fast():
    result = runner.invoke(app, ["analyze", "-", "--output", "json"], input=VALID + "broken\n")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "<stdin>:2:" in result.stderr
    assert "Traceback" not in result.stderr


def test_skipping_is_bounded_and_keeps_json_clean():
    result = runner.invoke(app, ["analyze", "-", "--skip-invalid", "--output", "json"], input="broken\n" * 10 + VALID)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["total_entries"] == 1
    assert result.stderr.count("Warning:") == 3
    assert "Skipped 10" in result.stderr


def test_all_invalid_reports_zero_with_warning():
    result = runner.invoke(app, ["analyze", "-", "--skip-invalid", "--output", "json"], input="bad\n")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["total_entries"] == 0
    assert "Skipped 1" in result.stderr


def test_missing_file(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path / "missing.log")])
    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_directory_input(tmp_path):
    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 1
    assert result.stdout == ""


def test_filters_and_top():
    result = runner.invoke(app, ["analyze", "-", "--source", "db", "--level", "ERROR", "--top", "1", "--output", "json"],
                           input=VALID + VALID.replace("ERROR db", "INFO web"))
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["total_entries"] == 1
    assert data["error_rate"] == 1.0


@pytest.mark.parametrize("options", [["--top", "0"], ["--top", "1001"], ["--format", "xml"],
                                     ["--output", "xml"], ["--level", "unknown"]])
def test_invalid_options(options):
    result = runner.invoke(app, ["analyze", "-", *options], input=VALID)
    assert result.exit_code == 2


def test_atomic_output(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("previous report")
    result = runner.invoke(app, ["analyze", "-", "--output", "json", "--output-file", str(output)], input=VALID)
    assert result.exit_code == 0
    assert json.loads(output.read_text())["total_entries"] == 1
    assert result.stdout == ""
    assert list(tmp_path.iterdir()) == [output]


def test_failed_parse_preserves_output(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("previous report")
    result = runner.invoke(app, ["analyze", "-", "--output-file", str(output)], input="bad")
    assert result.exit_code == 1
    assert output.read_text() == "previous report"


def test_failed_write_preserves_output_and_cleans_temp(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("previous report")
    def fail(*args):
        raise PermissionError("replacement denied")
    monkeypatch.setattr("quaestio.cli.os.replace", fail)
    result = runner.invoke(app, ["analyze", "-", "--output-file", str(output)], input=VALID)
    assert result.exit_code == 1
    assert output.read_text() == "previous report"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_input_cannot_be_output(tmp_path, alias):
    log = tmp_path / "input.log"
    log.write_text(VALID)
    output = tmp_path / "alias.log"
    if alias == "same":
        output = log
    elif alias == "symlink":
        output.symlink_to(log)
    else:
        output.hardlink_to(log)
    result = runner.invoke(app, ["analyze", str(log), "--output-file", str(output)])
    assert result.exit_code == 1
    assert "must differ" in result.stderr
    assert log.read_text() == VALID


def test_missing_output_directory(tmp_path):
    result = runner.invoke(app, ["analyze", "-", "--output-file", str(tmp_path / "missing" / "report")], input=VALID)
    assert result.exit_code == 1


def test_module_command_outside_repository(sample_log, tmp_path):
    result = subprocess.run([sys.executable, "-m", "quaestio", "analyze", str(sample_log), "--output", "json"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["total_entries"] == 4


def test_empty_input():
    result = runner.invoke(app, ["analyze", "-", "--output", "json"], input="\n")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["error_rate"] == 0.0
    assert data["top_errors"] == []


def test_decode_error_is_readable(tmp_path):
    log = tmp_path / "broken.log"
    log.write_bytes(b"\xff")
    result = runner.invoke(app, ["analyze", str(log), "--skip-invalid"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_permission_error_is_readable(monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("Permission denied")
    monkeypatch.setattr("quaestio.cli.parse_file", denied)
    result = runner.invoke(app, ["analyze", "restricted.log"])
    assert result.exit_code == 1
    assert "Permission denied" in result.stderr
