# Agent Context Readiness Report

Repository: `examples/demo-python-service`
Score: **72/100 (B)**

## Signals

| Signal | Status | Weight | Evidence |
|---|---:|---:|---|
| readme | ✅ | 16 | README.md |
| license | ✅ | 8 | LICENSE |
| agent_instructions | ❌ | 18 | Add AGENTS.md/CLAUDE.md with coding style, test commands, and guardrails. |
| tests | ✅ | 14 | tests |
| ci | ❌ | 8 | Add CI so agent-created changes get repeatable feedback. |
| contributing | ❌ | 6 | Add CONTRIBUTING.md with PR, review, and local setup expectations. |
| changelog | ❌ | 5 | Add CHANGELOG.md so agents can understand release history. |
| architecture | ❌ | 10 | Add architecture notes or ADRs for module boundaries and design intent. |
| manifest | ✅ | 8 | pyproject.toml |
| lockfile | ❌ | 3 | Commit a lockfile when the ecosystem expects one. |
| examples | ✅ | 4 | examples |

## Detected commands

- `python -m unittest discover -s tests -v`

## Top fixes

1. Add AGENTS.md/CLAUDE.md with coding style, test commands, and guardrails.
2. Add architecture notes or ADRs for module boundaries and design intent.
3. Add CI so agent-created changes get repeatable feedback.
