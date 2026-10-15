# Architecture

```text
file or stdin
  -> parse_file / parse_lines (native, configured profile, or detected layout)
  -> LogEntry stream
  -> select_entries (optional exact filters)
  -> analyze (single pass, exact message counts)
  -> AnalysisResult
  -> render_report (text / JSON / CSV)
  -> stdout or atomic report file
```

Models, parsing, and analysis are independent of the CLI. reporting depends on Rich;
cli depends on Typer and coordinates I/O. A future API should reuse the same core.

The parser ignores blanks and fails fast by default. Explicit skip mode invokes a
callback for rejected records. The CLI bounds individual warnings and maintains a total;
the analysis schema remains unchanged. I/O and encoding failures still fail.

layouts builds reusable record parsers from validated JSON configuration. Named regex
groups or JSON field paths normalize into the existing LogEntry schema. Compiled patterns
and level mappings are prepared once per stream. Auto mode tries known profiles until
one validates, then locks that parser for the stream. Configuration errors are fatal
even in skip mode. errors owns LogParseError; parser re-exports it for compatibility.

See [log-layouts.md](log-layouts.md) for profile contracts and extension decisions.

Filters are lazy and determine the analyzed population and rate denominator. ERROR rate
excludes CRITICAL. Error grouping uses exact message text across sources. Top-k ties
retain first appearance. The analyzer has O(U) counting memory for U distinct errors,
plus input record/buffering costs; it does not retain the full event stream.

Partial consumers of parse_file should close the generator explicitly. The CLI does so
in a finally block. Output is rendered before opening any destination, then saved with
same-directory temporary-file replacement. Alias checks prevent obvious input overwrite.

See [implementation-report.md](implementation-report.md) for design alternatives,
trade-offs, validation, benchmarks, and remaining work. See [../README.md](../README.md)
for exact input/output contracts and command usage.
