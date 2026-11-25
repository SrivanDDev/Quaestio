# Quaestio

**Investigate what happened.**

A Python toolkit and CLI for turning application logs into severity counts, ERROR rates, and ranked error messages. Parse logs as a stream, filter the events you need, and export reports without a database or AI runtime.

## Features

- Text and NDJSON input, including stdin
- Custom parser profiles for single-line text and renamed or nested JSON fields
- Automatic detection for a limited set of known layouts
- Source and exact-level filters, severity counts, and repeated ERROR messages
- Text, JSON, and CSV reports, with optional atomic file output
- Strict validation by default, with an explicit option to skip invalid records
- Reusable Python parser and analyzer APIs

## Install

Requires **Python 3.11+**. Clone the repository and install from source:

```sh
git clone https://github.com/SrivanDDev/Quaestio.git
cd Quaestio
python -m venv .venv
source .venv/bin/activate
python -m pip install .
quaestio --help
```

On Windows, activate with `.venv\Scripts\activate` instead of the source command.

## Quick start

```sh
quaestio analyze examples/sample.log
quaestio analyze examples/sample.log --output json
quaestio analyze examples/sample.log --output csv --output-file report.csv
quaestio analyze examples/sample.ndjson --format ndjson
quaestio analyze examples/custom-pipe.log --parser-config examples/layouts/custom-pipe.json
```

The included sample has four events. Its expected summary is:

| Metric | Value |
| --- | --- |
| Analyzed events | 4 |
| INFO | 2 |
| WARNING | 1 |
| ERROR | 1 |
| DEBUG / CRITICAL | 0 / 0 |
| ERROR rate | 25.0% |

This table summarizes the sample result; report formatting depends on the selected output format. `--level` matches an exact level, and the ERROR rate counts ERROR events separately from CRITICAL.

## Documentation

- [User guide](docs/user-guide.md): input formats, report semantics, Python API, and benchmarks
- [Custom log layouts](docs/log-layouts.md): parser profiles, examples, and limitations
- [Implementation report](docs/implementation-report.md): design and verification notes
- [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

CI is configured for Python 3.11–3.14, tests, wheel builds, and installed CLI smoke checks.

## Scope and limitations

Parsing is streaming, but exact error counts retain every distinct ERROR message: memory is O(U) in unique errors. Automatic detection covers known layouts; multiline traces, watch mode, dashboards, and anomaly detection remain future work. See the user guide for full behavior and constraints.

## License

[MIT](LICENSE)
