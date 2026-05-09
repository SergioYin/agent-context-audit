# Changelog

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
