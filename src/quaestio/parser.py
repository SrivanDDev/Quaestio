from datetime import datetime
from pydantic import ValidationError
from quaestio.models import LogEntry


class LogParseError(Exception):
    """Raised when a log line cannot be parsed."""


def parse_line(line: str) -> LogEntry:
    parts = line.strip().split(maxsplit=4)
    if len(parts) != 5:
        raise LogParseError(f"Invalid log line: {line}")
    date = parts[0]
    time = parts[1]
    level = parts[2]
    try:
        timestamp = datetime.strptime(
            f"{date} {time}",
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError as error:
        raise LogParseError(f"Invalid timestamp: {date} {time}") from error
    source = parts[3]
    message = parts[4]
    try:
        return LogEntry( timestamp=timestamp, level=level,source=source, message=message)
    except ValidationError as error:
        raise LogParseError(f"Invalid log entry: {line}") from error
def parse_file(path : str):
    with open(path , encoding="utf-8") as file:
        for line in file:
            yield parse_line(line)

