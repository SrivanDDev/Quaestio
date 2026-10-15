"""Declarative, reusable layout profiles that normalize records into LogEntry.

Profiles are data, not executable plugins. Regexes are compiled once per stream.
"""

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, model_validator

from quaestio.errors import LogParseError
from quaestio.models import LogEntry, LogLevel

RecordParser = Callable[[str], LogEntry]
FIELDS = frozenset({"timestamp", "level", "source", "message"})
ALIASES = {"WARN": "WARNING", "ERR": "ERROR", "FATAL": "CRITICAL"}


class LayoutConfigError(ValueError):
    """Invalid configuration; unlike malformed records, this cannot be skipped."""


class LayoutConfig(BaseModel):
    """A single-line regex or JSON mapping profile.

    JSON mapping strings are literal keys; lists navigate nested objects/arrays.
    Timestamps default to ISO 8601, or use a strptime format / unix / unix_ms.
    """

    model_config = ConfigDict(extra="forbid")

    format: Literal["regex", "ndjson", "json"]
    pattern: StrictStr | None = None
    fields: dict[str, StrictStr | list[StrictStr | StrictInt]] = Field(default_factory=dict)
    timestamp_format: StrictStr | None = None
    defaults: dict[str, StrictStr] = Field(default_factory=lambda: {"source": "unknown"})
    level_map: dict[str, LogLevel] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_layout(self) -> "LayoutConfig":
        if set(self.fields) - FIELDS:
            raise ValueError("fields may only map timestamp, level, source and message")
        if set(self.defaults) - {"source", "level"}:
            raise ValueError("defaults may only supply source and level")
        if "source" in self.defaults and not self.defaults["source"].strip():
            raise ValueError("default source must not be empty")
        if self.timestamp_format == "":
            raise ValueError("timestamp_format must not be empty")
        if self.timestamp_format not in (None, "iso", "unix", "unix_ms"):
            if "%" not in self.timestamp_format:
                raise ValueError("timestamp_format must be iso, unix, unix_ms or a strptime format")
            try:
                probe = datetime(2024, 11, 23, 14, 15, 16, tzinfo=timezone.utc)
                datetime.strptime(probe.strftime(self.timestamp_format), self.timestamp_format)
            except (ValueError, OverflowError) as error:
                raise ValueError(f"Invalid timestamp_format: {error}") from error
        for path in self.fields.values():
            if isinstance(path, str):
                if not path:
                    raise ValueError("mapped keys must not be empty")
            elif not path or any(isinstance(part, bool) or (isinstance(part, int) and part < 0)
                                 or (isinstance(part, str) and not part) for part in path):
                raise ValueError("nested paths need nonempty keys or nonnegative array indexes")
        normalized_keys = [key.strip().upper() for key in self.level_map]
        if any(not key for key in normalized_keys) or len(set(normalized_keys)) != len(normalized_keys):
            raise ValueError("level_map keys must be nonempty and unique ignoring case")
        if "level" in self.defaults:
            level = self.defaults["level"].strip().upper()
            mapping = {key.strip().upper(): value.value for key, value in self.level_map.items()}
            if mapping.get(level, ALIASES.get(level, level)) not in {item.value for item in LogLevel}:
                raise ValueError("default level must be a recognized severity or mapped alias")
        if self.format == "regex":
            if self.fields:
                raise ValueError("regex uses named groups, not fields mappings")
            if not self.pattern:
                raise ValueError("regex profiles require a pattern")
            try:
                groups = re.compile(self.pattern).groupindex
            except (re.error, RecursionError) as error:
                raise ValueError(f"Invalid regex: {error}") from error
            if "timestamp" not in groups and not {"date", "time"}.issubset(groups):
                raise ValueError("pattern needs a timestamp group, or both date and time groups")
            for name in ("level", "message", "source"):
                if name not in groups and name not in self.defaults:
                    raise ValueError(f"pattern needs a {name} group or an explicit default")
        elif self.pattern is not None:
            raise ValueError("JSON profiles use fields mappings, not a pattern")
        return self


def load_layout(path: str | Path) -> LayoutConfig:
    """Read and validate a UTF-8 JSON profile without importing any user code."""
    try:
        return LayoutConfig.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))
    except ValidationError as error:
        details = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'profile'}: {e['msg']}"
                            for e in error.errors(include_input=False, include_url=False))
        raise LayoutConfigError(f"Invalid parser configuration {path}: {details}") from error


def _normalize(values: dict[str, object], config: LayoutConfig,
               levels: dict[str, str]) -> LogEntry:
    values = dict(values)
    for name, default in config.defaults.items():
        if values.get(name) is None:
            values[name] = default
    for name in ("timestamp", "level", "source", "message"):
        if values.get(name) is None:
            raise LogParseError(f"Missing required field: {name}")
    raw_level = values["level"]
    if isinstance(raw_level, bool) or not isinstance(raw_level, (str, int)):
        raise LogParseError("Field level must be text or an integer severity code")
    level = str(raw_level).strip().upper()
    values["level"] = levels.get(level, level)
    timestamp = values["timestamp"]
    try:
        if config.timestamp_format in ("unix", "unix_ms"):
            if isinstance(timestamp, bool):
                raise ValueError("boolean is not an epoch")
            epoch = float(timestamp)
            if config.timestamp_format == "unix_ms":
                epoch /= 1000
            values["timestamp"] = datetime.fromtimestamp(epoch, tz=timezone.utc)
        elif config.timestamp_format not in (None, "iso"):
            values["timestamp"] = datetime.strptime(str(timestamp).strip(), config.timestamp_format)
        else:
            if not isinstance(timestamp, str):
                raise ValueError("ISO timestamp must be a string")
            values["timestamp"] = datetime.fromisoformat(timestamp.strip())
    except (ValueError, TypeError, OverflowError, OSError) as error:
        raise LogParseError("Invalid timestamp for the configured timestamp format") from error
    # Require real text; never stringify objects or invent an event message.
    for name in ("source", "message"):
        if not isinstance(values[name], str) or not values[name].strip():
            raise LogParseError(f"Field {name} must be nonempty text")
    values["source"] = values["source"].strip()
    try:
        return LogEntry.model_validate(values)
    except ValidationError as error:
        raise LogParseError("Invalid mapped event; check level and required fields") from error


def _lookup(record: dict, path: str | list[str | int]) -> object:
    parts = [path] if isinstance(path, str) else path
    value: object = record
    for part in parts:
        if isinstance(part, str) and isinstance(value, dict):
            if part not in value:
                return None
            value = value[part]
        elif isinstance(part, int) and not isinstance(part, bool) and isinstance(value, list):
            if part < 0 or part >= len(value):
                return None
            value = value[part]
        else:
            return None
    return value


def build_layout_parser(config: LayoutConfig) -> RecordParser:
    """Build one parser per stream; configuration errors are fatal."""
    levels = dict(ALIASES)
    levels.update({key.strip().upper(): value.value for key, value in config.level_map.items()})
    if config.format == "regex":
        pattern = re.compile(config.pattern)

        def parse_regex(line: str) -> LogEntry:
            match = pattern.fullmatch(line.rstrip("\r\n"))
            if match is None:
                raise LogParseError("Record does not match the configured regex layout")
            groups = match.groupdict()
            values = {name: groups.get(name) for name in FIELDS}
            if values["timestamp"] is None and groups.get("date") and groups.get("time"):
                values["timestamp"] = groups["date"] + " " + groups["time"]
            return _normalize(values, config, levels)
        return parse_regex

    def parse_mapped_json(line: str) -> LogEntry:
        try:
            record = json.loads(line)
        except (ValueError, RecursionError) as error:
            raise LogParseError("Invalid JSON record") from error
        if not isinstance(record, dict):
            raise LogParseError("Expected one JSON object per line")
        values = {name: _lookup(record, config.fields.get(name, name)) for name in FIELDS}
        return _normalize(values, config, levels)
    return parse_mapped_json


# Auto-detection is intentionally limited to documented grammars, not guesses.
AUTO_PROFILES = (
    LayoutConfig(format="regex", pattern=r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+(?P<level>\S+)\s+(?P<source>\S+)\s+(?P<message>.+)"),
    LayoutConfig(format="regex", pattern=r"\[(?P<timestamp>[^\]]+)\]\s+\[(?P<level>[^\]]+)\](?:\s+\[(?P<source>[^\]]+)\])?\s+(?P<message>.+)"),
    LayoutConfig(format="regex", pattern=r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\S+)\s+(?P<level>\S+)\s+(?P<source>\S+)\s+(?P<message>.+)"),
    LayoutConfig(format="regex", pattern=r"(?P<level>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|\s*(?P<timestamp>[^|]+?)\s*\|\s*(?P<message>.+)"),
    LayoutConfig(format="regex", pattern=r"(?P<timestamp>[^|]+?)\s*\|\s*(?P<level>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|\s*(?P<message>.+)"),
)


def build_auto_parser() -> RecordParser:
    """Lock to the first successfully validated grammar; do not buffer input."""
    candidates = [build_layout_parser(profile) for profile in AUTO_PROFILES]
    json_parser = build_layout_parser(LayoutConfig(format="ndjson"))
    selected: RecordParser | None = None

    def parse_auto(line: str) -> LogEntry:
        nonlocal selected
        if selected is not None:
            return selected(line)
        # JSON-looking records must be JSON objects; never guess a text fallback.
        parsers = [json_parser] if line.lstrip().startswith("{") else candidates
        for parser in parsers:
            try:
                entry = parser(line)
            except LogParseError:
                continue
            selected = parser
            return entry
        raise LogParseError("Could not detect a supported layout; use --parser-config for custom fields")
    return parse_auto
