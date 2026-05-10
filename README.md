# Agent Context Audit

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

**Score whether a repository is ready for AI coding agents, then generate a paste-ready AGENT_CONTEXT.md bundle.**

A tiny zero-dependency CLI that tells you whether a repository is ready for AI coding agents — and generates a compact `AGENT_CONTEXT.md` bundle you can paste into Claude Code, Codex, Cursor, Copilot Chat, or any terminal agent.

> Context is the bottleneck for AI coding agents. This tool turns that vague problem into a quick repo score, concrete fixes, and a reusable context pack.

## Why this exists

AI coding agents often fail not because they cannot code, but because they lack the project conventions, test commands, architecture notes, and change boundaries humans keep in their heads. `agent-context-audit` helps maintainers make that context explicit.

It checks for:

- repo purpose and setup docs (`README`, examples, usage)
- agent instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.github/copilot-instructions.md`)
- test/lint commands and CI signals
- dependency manifests and lockfiles
- architecture notes, changelog, contribution docs
- risky omissions like missing license or secrets-looking files

Then it can generate:

- a Markdown readiness report
- JSON output for automation
- a compact `AGENT_CONTEXT.md` bundle with tree, detected commands, key excerpts, and suggested next edits


## Who is this for?

- Developers using Codex, Claude Code, Cursor, GitHub Copilot, Gemini CLI, or custom coding agents.
- Maintainers who want repositories to be easier for AI agents and human contributors to understand.
- Teams building repeatable context-engineering workflows without sending entire repositories to a model.

## Why it can earn stars

- It solves a concrete, recurring AI-coding pain: bad context causes bad agent output.
- It is tiny, auditable, and dependency-light.
- It works locally and can be added to CI.
- It produces artifacts maintainers can inspect before handing work to an AI agent.

## Install

No external dependencies. Python 3.9+ is enough.

```bash
git clone <this-repo>
cd agent-context-audit
python -m agent_context_audit audit .
```

Optional editable install:

```bash
python -m pip install -e .
agent-context-audit audit .
```

## Usage

Audit a repository:

```bash
python -m agent_context_audit audit /path/to/repo
```

Write a report:

```bash
python -m agent_context_audit audit . --write CONTEXT_READINESS.md
```

Generate a paste-ready agent context pack:

```bash
python -m agent_context_audit pack . --out AGENT_CONTEXT.md --max-bytes 24000
```

Machine-readable output:

```bash
python -m agent_context_audit audit . --format json
```

The default `audit` output remains human-readable text; `--format markdown` is also supported for the original spelling.

Write JSON for an asset dashboard or local automation:

```bash
python -m agent_context_audit audit . --format json --write /tmp/agent-context-audit.json
```

Suppress known findings from a previous audit while keeping the current score and new findings visible:

```bash
python -m agent_context_audit audit . --format json --baseline /tmp/agent-context-audit.json
```

With `--baseline`, repeated findings are moved to `suppressed_findings`, current-only findings remain in `findings`, and text output reports new versus suppressed issue counts. A malformed baseline JSON fails clearly with a non-zero exit.

Compare two JSON audit reports:

```bash
python -m agent_context_audit compare /tmp/baseline.json /tmp/current.json
```

The `compare` command prints deterministic JSON by default for automation. It includes baseline/current scores when present, score delta, added/removed/changed file counts, files improved or regressed by score, and rule issue count deltas when the reports include findings, categories, rules, or `rule_issues`.

For a concise human-readable summary:

```bash
python -m agent_context_audit compare /tmp/baseline.json /tmp/current.json --format text
```

Read the score from JSON in a script or shell pipeline:

```bash
python -c "import json,sys; print(json.load(open(sys.argv[1]))['overall_score'])" /tmp/agent-context-audit.json
```

Useful stable JSON keys include `tool`, `scanned_root`, `overall_score`, `grade`, `status`, `categories`, `findings`, `recommendations`, `generated_context_pack_path`, `counts`, and `summary`. When `--baseline` is supplied, output also includes `baseline` and `suppressed_findings`; `baseline` contains `baseline_path`, `suppressed_count`, `new_issue_count`, and per-file counts when findings include paths.

Useful stable comparison keys include `baseline`, `current`, `score_delta`, `changed_file_count`, `added_file_count`, `removed_file_count`, `added_files`, `removed_files`, `files_improved`, `files_regressed`, and `rule_issue_count_deltas`.

## Example output

```text
Agent Context Readiness: 72/100 (B)

Top fixes:
1. Add AGENTS.md with repo-specific coding, test, and style instructions.
2. Document the default test command in README or pyproject/package scripts.
3. Add architecture notes for the main modules.
```

See [`examples/sample_report.md`](examples/sample_report.md) for a longer sample.

## What makes a repo agent-ready?

A good AI-agent-ready repo has:

1. **Orientation**: what the project does, where the important files live.
2. **Operating commands**: install, test, lint, build, run demo.
3. **Conventions**: style, naming, architecture boundaries, generated files.
4. **Guardrails**: security notes, forbidden actions, review checklist.
5. **Feedback loops**: fast tests or self-check scripts the agent can run.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run self-check on this repo:

```bash
python -m agent_context_audit audit . --write /tmp/agent-context-audit-report.md
python -m agent_context_audit pack . --out /tmp/AGENT_CONTEXT.md
python -m agent_context_audit audit . --format json --write /tmp/agent-context-audit-current.json
python -m agent_context_audit audit . --format json --baseline /tmp/agent-context-audit-current.json
python -m agent_context_audit compare /tmp/agent-context-audit-current.json /tmp/agent-context-audit-current.json
```

## License

MIT
## Roadmap

- GitHub Action packaging for one-line CI adoption.
- More ecosystem-specific command detection.
- Optional autofix/init commands for common agent context files.
- Richer examples from real-world Python, Node, and docs-only repositories.
