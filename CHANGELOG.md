# Changelog

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
