"""Streaming native, configured, and detected adapters for normalized events."""

from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from enum import Enum
from os import PathLike

from pydantic import ValidationError

from quaestio.models import LogEntry
from quaestio.errors import LogParseError
from quaestio.layouts import LayoutConfig, LayoutConfigError, build_auto_parser, build_layout_parser


class InputFormat(str, Enum):
    TEXT = "text"
    NDJSON = "ndjson"
    JSON = "json"
    REGEX = "regex"
    AUTO = "auto"


def parse_line(line: str) -> LogEntry:
    """Parse DATE TIME LEVEL SOURCE MESSAGE, preserving message spaces."""
    parts = line.strip().split(maxsplit=4)
    if len(parts) != 5:
        raise LogParseError("Expected DATE TIME LEVEL SOURCE MESSAGE")
    date, time, level, source, message = parts
    try:
        timestamp = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise LogParseError(f"Invalid timestamp: {date} {time}") from error
    try:
        return LogEntry(timestamp=timestamp, level=level, source=source, message=message)
    except ValidationError as error:
        raise LogParseError("Invalid log entry; level must be DEBUG, INFO, WARNING, ERROR or CRITICAL") from error


def parse_json_line(line: str) -> LogEntry:
    """Parse one JSON object; extra fields are ignored by the existing model."""
    try:
        return LogEntry.model_validate_json(line)
    except ValidationError as error:
        # Do not echo potentially sensitive raw records in diagnostics.
        raise LogParseError("Expected a JSON object with valid timestamp, level, source and message") from error


def _record_parser(format: InputFormat | str | None, layout: LayoutConfig | None):
    selected = InputFormat(format) if format is not None else (
        InputFormat(layout.format) if layout is not None else InputFormat.TEXT)
    if layout is not None:
        configured = InputFormat(layout.format)
        json_formats = {InputFormat.JSON, InputFormat.NDJSON}
        if selected != configured and not {selected, configured}.issubset(json_formats):
            raise LayoutConfigError("--format conflicts with the parser configuration format")
        return build_layout_parser(layout)
    if selected == InputFormat.REGEX:
        raise LayoutConfigError("regex input requires --parser-config with a named-group pattern")
    if selected == InputFormat.AUTO:
        return build_auto_parser()
    return parse_line if selected == InputFormat.TEXT else parse_json_line


def parse_lines(
    lines: Iterable[str], *, format: InputFormat | str | None = None,
    layout: LayoutConfig | None = None,
    source: str = "<stream>", skip_invalid: bool = False,
    on_error: Callable[[LogParseError], None] | None = None,
) -> Iterator[LogEntry]:
    """Ignore blanks; fail fast unless skipping is explicit.

    The callback exposes rejected records without retaining them in memory.
    I/O and decoding errors are never treated as malformed records.
    """
    parser = _record_parser(format, layout)
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield parser(line)
        except LogParseError as error:
            located = LogParseError(str(error), source=source, line_number=line_number)
            if not skip_invalid:
                raise located from error
            if on_error is not None:
                on_error(located)


def parse_file(
    path: str | PathLike[str], *, format: InputFormat | str | None = None,
    layout: LayoutConfig | None = None,
    skip_invalid: bool = False,
    on_error: Callable[[LogParseError], None] | None = None,
) -> Iterator[LogEntry]:
    """Open UTF-8 lazily and close when iteration ends; accept a leading BOM."""
    with open(path, encoding="utf-8-sig") as file:
        yield from parse_lines(file, format=format, layout=layout, source=str(path),
                               skip_invalid=skip_invalid, on_error=on_error)
