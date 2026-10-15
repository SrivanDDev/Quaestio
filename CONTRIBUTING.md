# Contributing

Install Python 3.11+ and use a virtual environment:

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

Keep input parsing, domain models, analysis, and presentation separate. Add a parser
only when its input contract is explicit. Use generators for large inputs and
avoid converting the full event stream to a list. Exact error counting retains
one dictionary entry per distinct ERROR message; describe this honestly when
changing performance behavior.

Write regression tests for observable behavior, especially malformed input,
streaming, output schemas, and file failure handling. Preserve stdout as report
content and stderr as diagnostics. Update README, CHANGELOG, and relevant design
notes when behavior changes. Do not silently change the meaning of ERROR rate.

Before submitting changes:

```sh
python -m pytest -q
python -m pip wheel . --no-deps --wheel-dir dist
quaestio analyze examples/sample.log
quaestio analyze examples/sample.ndjson --format ndjson --output json
```

For performance work, compare repeated benchmark runs on the same machine,
interpreter, dataset, and distinct-error count. File generation is not part of the
benchmark. Tracemalloc adds overhead, so allocation measurement runs separately.

CI covers Python 3.11-3.14 on Linux. Windows and macOS are not verified here.
Do not commit real logs, credentials, virtual environments, or generated build
artifacts. Example logs must remain synthetic and should be tracked.
