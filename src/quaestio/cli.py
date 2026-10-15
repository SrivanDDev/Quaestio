"""Command interface for Quaestio's reusable streaming core."""

import os
from pathlib import Path
import sys
import tempfile
from typing import Annotated

import typer

from quaestio.analyzer import analyze as analyze_entries
from quaestio.analyzer import select_entries
from quaestio.models import LogLevel
from quaestio.layouts import load_layout
from quaestio.parser import InputFormat, LogParseError, parse_file, parse_lines
from quaestio.reporting import OutputFormat, render_report

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main():
    """Investigate what happened. Stream logs into useful summaries."""


def _write_report(path: Path, report: str) -> None:
    """Replace atomically so a failed write cannot truncate an existing report."""
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as file:
            temporary = file.name
            file.write(report)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


@app.command()
def analyze(
    path: Annotated[str, typer.Argument(help="UTF-8 log file, or - for stdin.")],
    format: Annotated[InputFormat | None, typer.Option("--format", help="Input format; defaults to text, or the profile format.")] = None,
    parser_config: Annotated[Path | None, typer.Option("--parser-config", help="JSON profile defining a custom regex or JSON field mapping.")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", help="Report format.")] = OutputFormat.TEXT,
    output_file: Annotated[Path | None, typer.Option("--output-file", help="Save report instead of printing it.")] = None,
    skip_invalid: Annotated[bool, typer.Option(help="Skip malformed records and report how many were skipped.")] = False,
    top: Annotated[int, typer.Option(min=1, max=1000, help="Number of frequent ERROR messages to show.")] = 5,
    source: Annotated[str | None, typer.Option(help="Include only this exact source.")] = None,
    level: Annotated[LogLevel | None, typer.Option(help="Include only this exact severity.")] = None,
):
    """Analyze a stream. Filters determine the counts and rate denominator."""
    skipped = 0

    def record_error(error: LogParseError) -> None:
        nonlocal skipped
        skipped += 1
        if skipped <= 3:
            typer.echo(f"Warning: {error}", err=True)

    try:
        if output_file is not None:
            inputs = ([Path(path)] if path != "-" else []) + ([parser_config] if parser_config else [])
            for input_path in inputs:
                if (input_path.resolve() == output_file.resolve()
                        or (output_file.exists() and input_path.samefile(output_file))):
                    raise ValueError("Output file must differ from the input log and parser configuration")
        layout = load_layout(parser_config) if parser_config is not None else None
        kwargs = dict(format=format, layout=layout, skip_invalid=skip_invalid, on_error=record_error)
        if path == "-":
            entries = parse_lines(sys.stdin, source="<stdin>", **kwargs)
        else:
            entries = parse_file(path, **kwargs)
        try:
            selected = select_entries(entries, source=source, level=level)
            result = analyze_entries(selected, top=top)
        finally:
            entries.close()
        report = render_report(result, output)
        if skipped:
            typer.echo(f"Skipped {skipped} invalid record(s); results cover valid selected entries only.", err=True)
        if output_file is None:
            typer.echo(report, nl=False)
        else:
            _write_report(output_file, report)
            typer.echo(f"Report saved to {output_file}", err=True)
    except BrokenPipeError:
        raise typer.Exit(0)
    except (LogParseError, OSError, UnicodeError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
