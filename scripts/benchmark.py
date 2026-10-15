"""Reproducible streaming benchmark. Run after installing Quaestio."""

import argparse
import json
from pathlib import Path
import platform
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from quaestio.analyzer import analyze
from quaestio.parser import parse_file


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=positive, default=100_000)
    parser.add_argument("--distinct-errors", type=positive, default=100)
    parser.add_argument("--runs", type=positive, default=3)
    parser.add_argument("--format", choices=["text", "ndjson"], default="text")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="quaestio-benchmark-") as directory:
        path = Path(directory) / "synthetic.log"
        with path.open("w", encoding="utf-8") as file:
            for index in range(args.entries):
                error = index % 10 == 0
                level = "ERROR" if error else "INFO"
                message = f"Failure {index // 10 % args.distinct_errors}" if error else "Request completed"
                if args.format == "text":
                    file.write(f"2026-08-27 21:30:15 {level} server {message}\n")
                else:
                    file.write(json.dumps(dict(timestamp="2026-08-27T21:30:15", level=level,
                                               source="server", message=message)) + "\n")
        durations = []
        for _ in range(args.runs):
            start = perf_counter()
            result = analyze(parse_file(path, format=args.format))
            durations.append(perf_counter() - start)
            assert result.total_entries == args.entries
        # Measure allocations separately: tracing distorts throughput timings.
        tracemalloc.start()
        analyze(parse_file(path, format=args.format))
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        seconds = median(durations)
        print(json.dumps(dict(
            python=platform.python_version(), platform=platform.platform(),
            input_format=args.format, entries=args.entries, file_bytes=path.stat().st_size,
            distinct_error_limit=args.distinct_errors, runs=args.runs,
            median_seconds=seconds, entries_per_second=args.entries / seconds,
            peak_python_allocation_bytes=peak,
        ), indent=2))


if __name__ == "__main__":
    run()
