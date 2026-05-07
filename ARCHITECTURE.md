# Architecture

`agent-context-audit` is intentionally small and standard-library only.

## Modules

- `agent_context_audit.cli`: argument parsing and exit-code behavior.
- `agent_context_audit.scanner`: filesystem scanning, scoring, renderers, and context-pack generation.
- `tests/`: unittest-based regression tests using temporary repositories.

## Scoring model

The scanner maps repository signals to weighted points. Signals are deliberately transparent so users can debate or customize them later. The score is not meant to be a universal quality metric; it is a practical proxy for whether an AI coding agent can orient itself, act, and verify changes.

## Safety choices

- Heavy/generated directories are skipped.
- Suspicious secret-bearing filenames are reported by path only; contents are never printed.
- Context packs include excerpts from known useful text files and are capped by `--max-bytes`.
