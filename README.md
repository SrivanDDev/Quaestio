# Quaestio

Investigate what happened.

Quaestio is a Python log-analysis toolkit with a streaming parser, reusable analyzer,
and command-line reports. Custom profiles support other single-line text layouts and
renamed or nested JSON fields. It counts severity levels, calculates the ERROR rate, and
ranks repeated error messages without loading the whole input into memory.

## Install

Python 3.11 or newer is required. From the project directory:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
quaestio --help
```

For a regular installation, use `python -m pip install .` instead.

## Quick start

```sh
quaestio analyze examples/sample.log
quaestio analyze examples/sample.log --output json
quaestio analyze examples/sample.log --output csv --output-file report.csv
quaestio analyze examples/sample.ndjson --format ndjson
quaestio analyze examples/bracketed.log --format auto
quaestio analyze examples/custom-pipe.log --parser-config examples/layouts/custom-pipe.json
cat examples/sample.log | quaestio analyze - --output json
quaestio analyze examples/sample.log --source database --level ERROR --top 10
```

`python -m quaestio` provides the same interface. The sample contains four events:
INFO=2, WARNING=1, ERROR=1, DEBUG=0, CRITICAL=0; error rate=25.0%.

## Input formats

Text is the default. Each nonblank line follows:

```text
DATE TIME LEVEL SOURCE MESSAGE
2026-08-27 21:32:45 ERROR database Connection refused
```

The timestamp uses `YYYY-MM-DD HH:MM:SS`; the source is one token; messages may
contain spaces. Levels are uppercase DEBUG, INFO, WARNING, ERROR, and CRITICAL.
Text timestamps have no timezone. Blank lines are ignored. Files must be UTF-8;
a leading UTF-8 BOM is accepted for file input.

Use `--format ndjson` for one JSON object per physical line:

```json
{"timestamp":"2026-08-27T21:32:45+00:00","level":"ERROR","source":"database","message":"Connection refused"}
```

All four fields are required. ISO timestamps may include timezones. Extra JSON
fields are ignored; this version does not retain metadata or raw records. A JSON
array, pretty-printed multi-line object, or stack trace is not NDJSON input.
Pydantic's existing timestamp coercion rules apply; ISO strings are recommended.

### Custom layouts and automatic detection

`--format auto` recognizes the original text shape, bracketed timestamps/levels,
ISO timestamps with `T`, two common pipe-delimited orders, and canonical NDJSON.
It locks onto the first valid layout and rejects subsequent incompatible layouts.
Auto mode is a small set of known grammars, not universal format inference.

For arbitrary field ordering, delimiters, dates, renamed JSON keys, or nested fields,
use a reusable JSON parser profile:

```sh
quaestio analyze examples/custom-pipe.log --parser-config examples/layouts/custom-pipe.json
quaestio analyze examples/nested.ndjson --parser-config examples/layouts/nested-json.json
```

The profile supplies its own input format; omit --format unless explicitly confirming
the same format. A conflicting --format is an error. `--format json` is an alias for
NDJSON; it still expects one JSON object per line, not a JSON array. `--format regex`
requires a profile. All profiles work with stdin, filters, exports, and --skip-invalid.

Configured and auto parsers normalize level casing and WARN/ERR/FATAL aliases. Native
text/NDJSON parsing retains its original strict uppercase-level behavior. Profiles can
map numeric severity codes and other aliases explicitly. Missing source defaults to
`unknown`; missing timestamp/message or an unmapped severity remains an error. A level
default is allowed only when explicitly configured. Unknown fields in profiles are
rejected rather than silently ignored.

See [the custom-layout walkthrough](docs/log-layouts.md) for profile examples, regex
capture groups, date formats, nested JSON mapping, design decisions, and limitations.

## Reliability and report semantics

Malformed records stop analysis by default with a file/line diagnostic and exit
code 1. No partial report is emitted. For a best-effort report:

```sh
quaestio analyze server.log --skip-invalid --output json
```

This skips malformed records, displays at most three individual warnings, and
reports the total skipped count on stderr. Blank lines do not count as skipped.
I/O and UTF-8 decoding failures still stop analysis. With skipping enabled, even
an entirely invalid stream produces a zero-entry report plus a warning; consumers
requiring complete data should keep strict mode. Skipped counts are diagnostic
stderr output, not fields in the analysis JSON.

- Counts and the rate denominator include only valid events matching the filters.
- `--level` matches exactly; it is not a minimum severity threshold.
- ERROR rate = ERROR count / analyzed entry count; CRITICAL is counted separately.
- Only ERROR messages appear in top errors; sources with identical messages merge.
- Top errors default to five (`--top` accepts 1 through 1000). Ties retain the order
  in which messages first appeared. Grouping is exact, not fuzzy or normalized.
- Empty input is valid and yields zero counts and a zero rate.
- Core JSON uses numeric ratios (0.25); the text report shows percentages (25.0%).
- CSV uses `section,name,value`, with summary rows followed by top-error rows.
  Message text is preserved and quoted correctly; treat it as untrusted text when
  importing it into spreadsheets, which may interpret formula-like strings.
- Reports go to stdout; errors, skip warnings, and file-save notices go to stderr.
- Exit codes: 0 for success (including explicit skip mode), 1 for input/output
  failures, 2 for invalid CLI usage. Normal ERROR log events do not make the command fail.
- `--output-file` replaces an existing report atomically after successful analysis.
  The parent directory must exist. Input aliases, symlinks, and hardlinks are
  checked to prevent writing a report over the input log. Atomic replacement is
  not a guarantee against concurrent path changes or power loss.

## Python API

```python
from quaestio.parser import parse_file
from quaestio.analyzer import analyze, select_entries

entries = parse_file('examples/sample.log')
result = analyze(select_entries(entries, source='database'), top=5)
print(result.model_dump_json(indent=2))
```

`parse_line`, `parse_json_line`, and `parse_lines` also work independently.
`parse_lines` accepts any iterable of strings; `analyze` accepts any iterable of
LogEntry objects. When consuming only part of a `parse_file` generator, explicitly
close it (or use `contextlib.closing`) to release the open file promptly.

Architecture: input adapter -> LogEntry -> optional selection -> analyzer ->
AnalysisResult -> reporting -> CLI. The core does not import Typer or Rich.

## Tests and benchmarks

```sh
python -m pytest -q
python scripts/benchmark.py --entries 100000 --format text
python scripts/benchmark.py --entries 100000 --format ndjson
python scripts/benchmark.py --entries 100000 --distinct-errors 10000
```

The benchmark creates a temporary synthetic file (10% ERROR events), excludes
file generation from timing, reports median parser-plus-analyzer throughput, and
measures peak Python allocations in a separate pass. It is not a process RSS
measurement or a performance promise. Memory is O(U) for U distinct ERROR messages,
plus one record and bounded file buffering; one enormous physical line can still
consume substantial memory. Exact counting necessarily retains all distinct
error messages, even if only the top five are displayed.

CI is configured for Python 3.11 through 3.14, tests, wheel building, and installed
CLI smoke checks. Local verification results and reasoning are recorded in
[the implementation report](docs/implementation-report.md).
The [original technical and design decision PDF](output/pdf/Quaestio_Implementation_and_Design_Decisions.pdf)
describes the initial MVP milestone. The [layout support guide](docs/log-layouts.md)
documents the subsequent parser extension, with a
[standalone PDF walkthrough](output/pdf/Quaestio_Custom_Log_Layouts_Guide.pdf).

## Scope and future work

The MVP is implemented: validated models, text parser, streaming analysis, severity
counts, ERROR rate, top errors, tested CLI, packaging, and documentation. NDJSON,
exports, filters, tolerant parsing, atomic output, benchmarks, CI, configured layouts,
and limited automatic detection are additions.
Dedicated syslog handling, multiline traces, watch mode, API/dashboard, SQLite,
anomaly detection, and Needle remain future work. No server, database, or AI
runtime is required.

MIT licensed. See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidance.
