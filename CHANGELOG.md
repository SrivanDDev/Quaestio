# Changelog

## Unreleased layout support

- Added reusable JSON profiles for named-group regex text layouts and renamed/nested
  NDJSON fields, custom timestamp formats, explicit defaults, and severity mappings.
- Added limited first-valid-record auto-detection with per-stream layout locking.
- Added --parser-config, --format regex/auto, and a json alias for NDJSON input.
- Kept native text/NDJSON behavior and the analysis/output schema compatible.
- Added profile validation, configuration overwrite protection, runnable examples,
  parser regression tests, and a usage/design guide.

## 0.1.0 - implementation completed October 7 2026

- Completed the Typer analyze command and Rich reports.
- Added NDJSON input, stdin, JSON/CSV output, source/severity selection, configurable
  top errors, and optional malformed-record skipping.
- Added located parser diagnostics, UTF-8 BOM handling, blank-line handling,
  atomic output saving, and input overwrite protection.
- Preserved the existing ERROR rate and exact-message grouping semantics.
- Added integration and regression tests, portable sample fixtures, a benchmark,
  package manifest, CI configuration, README, and design documentation.
- Made sample logs eligible for Git tracking; preserved the pre-existing analyzer
  ranking work and tests.

This is a local implementation milestone, not a published PyPI or GitHub release.
