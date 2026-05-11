# Changelog

## 0.1.5 - 2026-05-11

- Added `export-dashboard` to convert saved audit JSON into compact dashboard-ready JSON or Markdown.
- Added score-band metadata, ranked top issues, top/attention file highlights, and deterministic verification metadata.
- Added tests for dashboard JSON, Markdown, and malformed input handling.
- Updated README usage and self-check commands for the new export path.

## 0.1.4 - 2026-05-11

- Added native per-file scoring to audit JSON reports under `files`, with `file_summary` rollups for dashboards and compare inputs.
- Added text/Markdown audit output for top and low-scoring files.
- Kept repository-level scoring unchanged while exposing file-level strengths, issues, matched readiness signals, size, and text status.
- Updated tests, README automation keys, and self-check expectations for richer real-project inputs.

## 0.1.3 - 2026-05-11

- Added `audit --baseline PATH` to suppress repeated findings from a previous JSON audit report while keeping scores unchanged.
- Added JSON baseline metadata with `baseline_path`, `suppressed_count`, `new_issue_count`, per-file counts when paths are available, and suppressed finding details.
- Added text output baseline counts and clear malformed-baseline errors.
- Added tests for no-baseline compatibility, repeated finding suppression, new finding visibility, malformed baselines, and unchanged compare behavior.

## 0.1.2 - 2026-05-10

- Added `compare` for deterministic JSON trend comparisons between two audit reports.
- Reported score deltas, changed/added/removed file counts, improved/regressed file scores, and rule issue count deltas when available.
- Added concise text comparison output and tests for improvement, regression, added/removed files, and malformed JSON input.

## 0.1.1 - 2026-05-09

- Added stable machine-readable JSON audit fields for dashboards and local automation.
- Documented JSON usage examples and automation score extraction.
- Preserved default Markdown audit output and exit-code behavior.

## 0.1.0 - 2026-05-03

- Initial CLI with `audit` and `pack` commands.
- Markdown and JSON audit output.
- AI-agent context readiness scoring.
- Paste-ready `AGENT_CONTEXT.md` generation.
- Unit tests and example report.
