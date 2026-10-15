"""Presentation adapters. These functions do not perform analysis."""

import csv
from enum import Enum
from io import StringIO

from rich.console import Console
from rich.table import Table
from rich.text import Text

from quaestio.models import AnalysisResult


class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"


def render_report(result: AnalysisResult, format: OutputFormat | str = OutputFormat.TEXT,
                  *, width: int = 100) -> str:
    """Return a complete report; raw messages are rendered literally."""
    format = OutputFormat(format)
    if format == OutputFormat.JSON:
        return result.model_dump_json(indent=2) + "\n"
    buffer = StringIO()
    if format == OutputFormat.CSV:
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["section", "name", "value"])
        for name, value in result.model_dump(exclude={"top_errors"}).items():
            writer.writerow(["summary", name, value])
        for message, count in result.top_errors:
            writer.writerow(["top_error", message, count])
        return buffer.getvalue()
    console = Console(file=buffer, width=width, color_system=None)
    console.print("Quaestio - Log Analysis", style="bold")
    console.print(f"Total entries: {result.total_entries}")
    counts = Table("Level", "Count", box=None)
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        counts.add_row(level, str(getattr(result, f"{level.lower()}_count")))
    console.print(counts)
    console.print(f"Error rate (ERROR / total): {result.error_rate:.1%}")
    console.print("Top errors:")
    if not result.top_errors:
        console.print("  No ERROR entries.")
    else:
        errors = Table("Message", "Count", box=None)
        for message, count in result.top_errors:
            errors.add_row(Text(message), str(count))
        console.print(errors)
    return buffer.getvalue()
